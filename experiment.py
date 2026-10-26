"""Experiment logic shared by the GUI: running algorithms, checking results, CSV export."""
import contextlib
import csv
import io
import time
from collections import Counter
from datetime import datetime

import numpy as np

import naive_owd_ideal_point
import naive_owd_with_filtration
import naive_owd_without_filtration

# name -> (module, function name). Every algorithm minimises all criteria, takes a list of points
# and returns (nondominated, n_comparisons); maximised criteria are negated before the call.
# The module must compare points through its module-level `dominates(a, b)` function –
# the app wraps it to record which points took part in comparisons.
ALGORITHMS = {
    "Algorytm bez filtracji": (naive_owd_without_filtration, "naive_owd_without_filtration"),
    "Algorytm z filtracją": (naive_owd_with_filtration, "owd_z_filtracja"),
    "Algorytm punktu idealnego": (naive_owd_ideal_point, "owd_ideal_point"),
}

# History table: key -> column header
HISTORY_COLUMNS = {
    "run": "#",
    "timestamp": "czas uruchomienia",
    "algorithm": "algorytm",
    "distribution": "rozkład",
    "n_alternatives": "N",
    "n_criteria": "k",
    "criteria": "kryteria",
    "directions": "kierunek",
    "means": "średnia",
    "stds": "odchylenie",
    "seed": "seed",
    "rounded": "zaokrąglanie",
    "n_nondominated": "|P|",
    "n_comparisons": "porównania",
    "time_ms": "czas [ms]",
    "correct": "poprawny",
}


def format_directions(signs):
    return ";".join("min" if s == 1 else "max" for s in signs)


def format_numbers(values):
    return ";".join(f"{v:g}" for v in values)


@contextlib.contextmanager
def track_comparisons(module, compared):
    """Temporarily replace module.dominates with a version that counts compared points."""
    original = module.dominates

    def counting_dominates(a, b):
        compared[a] += 1
        compared[b] += 1
        return original(a, b)

    module.dominates = counting_dominates
    try:
        yield
    finally:
        module.dominates = original


def _dominated_by_any(targets, dominators, chunk=256):
    """Boolean mask: is targets[i] Pareto-dominated (minimisation) by any row of dominators?"""
    result = np.zeros(len(targets), dtype=bool)
    if len(dominators) == 0:
        return result
    for start in range(0, len(targets), chunk):
        t = targets[start:start + chunk, None, :]
        d = dominators[None, :, :]
        result[start:start + chunk] = ((d <= t).all(axis=2) & (d < t).any(axis=2)).any(axis=1)
    return result


def verify_pareto(data, mask):
    """Check the reported nondominated set against the Pareto definition (minimisation).

    Returns (n_extra, n_missing): reported points that are dominated, and nondominated
    points that were not reported. Costs O(N * |P|) instead of O(N^2).
    """
    n_extra = int(_dominated_by_any(data[mask], data).sum())
    rest = data[~mask]
    # A dominated point is always dominated by some nondominated one, so if P is correct
    # every remaining point is dominated by P; only the exceptions need a full check.
    suspects = rest[~_dominated_by_any(rest, data[mask])]
    n_missing = int((~_dominated_by_any(suspects, data)).sum())
    return n_extra, n_missing


def format_correctness(n_extra, n_missing):
    if n_extra == 0 and n_missing == 0:
        return "tak"
    return f"NIE (+{n_extra} zbędne, -{n_missing} brak)"


def ideal_point(data, signs):
    """Best value of every criterion (min for minimised, max for maximised ones)."""
    return np.array([data[:, i].min() if s == 1 else data[:, i].max() for i, s in enumerate(signs)])


def run_algorithm(name, points, signs):
    """Run one algorithm on `points` (list of tuples) with criterion directions `signs` (+1 min / -1 max)."""
    # Algorithms minimise, so maximised criteria are negated (f -> -f)
    points_min = [tuple(s * v for s, v in zip(signs, x)) for x in points]
    module, function_name = ALGORITHMS[name]
    algorithm = getattr(module, function_name)

    # Debug prints of the algorithms are swallowed, so they do not flood the console
    with contextlib.redirect_stdout(io.StringIO()):
        # Timed run without comparison tracking, so the bookkeeping does not distort the time
        start = time.perf_counter()
        algorithm(points_min)
        elapsed_ms = (time.perf_counter() - start) * 1000

        compared = Counter()
        with track_comparisons(module, compared):
            nondominated, n_comparisons = algorithm(points_min)
    nondominated = set(nondominated)
    mask = np.array([x in nondominated for x in points_min], dtype=bool)
    return {
        "algorithm": name,
        "signs": list(signs),
        "nondominated_mask": mask,
        "compared_counts": np.array([compared[x] for x in points_min], dtype=int),
        "n_comparisons": n_comparisons,
        "time_ms": elapsed_ms,
        "correctness": verify_pareto(np.array(points_min, dtype=float), mask),
    }


def history_row(run_number, params, result, names):
    return {
        "run": run_number,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "algorithm": result["algorithm"],
        "distribution": params["distribution"],
        "n_alternatives": params["n_alternatives"],
        "n_criteria": params["n_criteria"],
        "criteria": "; ".join(names),
        "directions": format_directions(result["signs"]),
        "means": format_numbers(params["means"]),
        "stds": format_numbers(params["stds"]),
        "seed": params["seed"],
        "rounded": int(params["round_values"]),
        "n_nondominated": int(result["nondominated_mask"].sum()),
        "n_comparisons": result["n_comparisons"],
        "time_ms": round(result["time_ms"], 3),
        "correct": format_correctness(*result["correctness"]),
    }


def result_csv(points, params, result, names):
    """CSV with every point, its status and comparison count; metadata as '#' comment lines.

    Read back with pandas.read_csv(path, comment="#").
    """
    out = io.StringIO()
    out.write(f"# algorytm: {result['algorithm']}\n")
    out.write(f"# rozklad: {params['distribution']}; srednia: {format_numbers(params['means'])}; "
              f"odchylenie: {format_numbers(params['stds'])}\n")
    out.write(f"# N: {params['n_alternatives']}; k: {params['n_criteria']}; seed: {params['seed']}; "
              f"zaokraglanie: {params['round_values']}; kierunek: {format_directions(result['signs'])}\n")
    out.write(f"# liczba_porownan: {result['n_comparisons']}; czas_ms: {result['time_ms']:.3f}; "
              f"poprawny: {format_correctness(*result['correctness'])}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["id"] + list(names) + ["status", "udzial_w_porownaniach"])
    for i, x in enumerate(points):
        status = "niezdominowany" if result["nondominated_mask"][i] else "zdominowany"
        writer.writerow([i] + list(x) + [status, int(result["compared_counts"][i])])
    return out.getvalue()

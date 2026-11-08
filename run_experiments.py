"""Batch experiments: many random data sets, every algorithm run on each of them.

The experiment is described by a TOML file (see experiments/eksperyment_B.toml).

Usage:
    python run_experiments.py experiments/eksperyment_B.toml
    python run_experiments.py experiments/eksperyment_B.toml --quick     # 2 repetitions, smoke test
    python run_experiments.py experiments/eksperyment_B.toml --workers 4 # data sets in parallel
    python run_experiments.py --resume results/eksperyment_B_2026-10-26_1200
    python run_experiments.py --summarize results/eksperyment_B_2026-10-26_1200

Output directory (results/<name>_<date>/):
    config.toml         copy of the configuration (with resolved defaults)
    raw.csv             one row per (data set, algorithm) – written as soon as it is computed
    summary.csv         mean / std / min / max per (N, k, algorithm)
    comparisons.csv     mean number of comparisons: rows (N, k), columns algorithms
    time_ms.csv         mean time [ms]: rows (N, k), columns algorithms
    report.html         charts of the summary
"""
import argparse
import csv
import sys
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data_generator import DISTRIBUTIONS, generate_points
from experiment import (ALGORITHMS, format_correctness, measure_algorithm, nondominated_mask,
                        to_minimisation, verify_pareto)

RAW_COLUMNS = ["n_alternatives", "n_criteria", "repetition", "seed", "algorithm",
               "n_nondominated", "n_comparisons", "time_ms", "correct"]
METRICS = {
    "n_comparisons": "liczba porównań",
    "time_ms": "czas [ms]",
    "n_nondominated": "liczba punktów niezdominowanych |P|",
}
DEFAULTS = {
    "base_seed": 0,
    "algorithms": list(ALGORITHMS),
    "distribution": "normal",
    "mean": 10.0,
    "std": 3.0,
    "directions": "min",
    "round_values": False,
    "verify": True,
}


# ---------------------------------------------------------------- config
def load_config(path):
    with open(path, "rb") as f:
        config = {**DEFAULTS, "name": Path(path).stem, **tomllib.load(f)}
    errors = []
    unknown = [a for a in config["algorithms"] if a not in ALGORITHMS]
    if unknown:
        errors.append(f"nieznane algorytmy {unknown}; dostępne: {list(ALGORITHMS)}")
    if config["distribution"] not in DISTRIBUTIONS:
        errors.append(f"nieznany rozkład „{config['distribution']}”; dostępne: {list(DISTRIBUTIONS)}")
    if not config.get("sizes"):
        errors.append("brak sekcji [[sizes]]")
    for size in config.get("sizes", []):
        if "n_alternatives" not in size or "repetitions" not in size:
            errors.append(f"[[sizes]] wymaga n_alternatives i repetitions: {size}")
        criteria = size.get("criteria", config.get("criteria"))
        if not criteria:
            errors.append(f"brak listy criteria dla N = {size.get('n_alternatives')}")
            continue
        size["criteria"] = list(criteria)
        for k in criteria:
            try:
                directions_for(config, k)
            except ValueError as error:
                errors.append(str(error))
    if errors:
        raise SystemExit("Błędy w konfiguracji:\n  - " + "\n  - ".join(errors))
    return config


def directions_for(config, k):
    """Signs (+1 min / -1 max) for k criteria: 'min', 'max' or a list with one entry per criterion."""
    directions = config["directions"]
    if isinstance(directions, str):
        directions = [directions] * k
    if len(directions) != k or any(d not in ("min", "max") for d in directions):
        raise ValueError(f"directions = {config['directions']!r} nie pasuje do k = {k}")
    return [1 if d == "min" else -1 for d in directions]


def save_config(config, path):
    """Write the resolved configuration back as TOML (simple values only)."""
    def value(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, list):
            return "[" + ", ".join(value(x) for x in v) + "]"
        return str(v)

    lines = [f"{key} = {value(v)}" for key, v in config.items() if key != "sizes"]
    for size in config["sizes"]:
        lines += ["", "[[sizes]]"] + [f"{key} = {value(v)}" for key, v in size.items()]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------- tasks
def dataset_seed(base_seed, n_alternatives, n_criteria, repetition):
    """Deterministic seed of one data set – the same configuration always gives the same data."""
    return int(np.random.SeedSequence([base_seed, n_alternatives, n_criteria, repetition]).generate_state(1)[0])


def build_tasks(config, done):
    """One task = one data set; `done` holds (N, k, repetition, algorithm) already in raw.csv."""
    tasks = []
    for size in config["sizes"]:
        for k in size["criteria"]:
            for repetition in range(size["repetitions"]):
                key = (size["n_alternatives"], k, repetition)
                algorithms = [a for a in config["algorithms"] if key + (a,) not in done]
                if algorithms:
                    tasks.append({"n_alternatives": size["n_alternatives"], "n_criteria": k,
                                  "repetition": repetition, "algorithms": algorithms})
    return tasks


def run_task(task, config):
    """Generate one data set and run the selected algorithms on it (same data for every algorithm)."""
    n, k, repetition = task["n_alternatives"], task["n_criteria"], task["repetition"]
    seed = dataset_seed(config["base_seed"], n, k, repetition)
    points = generate_points(config["distribution"], config["mean"], config["std"], n, k,
                             seed=seed, round_values=config["round_values"])
    points_min = to_minimisation(points, directions_for(config, k))
    data = np.array(points_min, dtype=float) if config["verify"] else None
    rows = []
    for name in task["algorithms"]:
        nondominated, n_comparisons, time_ms = measure_algorithm(name, points_min)
        mask = nondominated_mask(points_min, nondominated)
        correct = format_correctness(*verify_pareto(data, mask)) if config["verify"] else ""
        rows.append({"n_alternatives": n, "n_criteria": k, "repetition": repetition, "seed": seed,
                     "algorithm": name, "n_nondominated": int(mask.sum()), "n_comparisons": n_comparisons,
                     "time_ms": round(time_ms, 4), "correct": correct})
    return rows


def run(config, output_dir, workers):
    raw_path = output_dir / "raw.csv"
    done = set()
    if raw_path.exists():
        previous = pd.read_csv(raw_path)
        done = set(zip(previous.n_alternatives, previous.n_criteria, previous.repetition, previous.algorithm))
    tasks = build_tasks(config, done)
    total = len(tasks)
    if done:
        print(f"Wznawianie: {len(done)} wyników już jest, zostało {total} zbiorów danych.")
    if not total:
        return

    new_file = not raw_path.exists()
    started = time.perf_counter()
    with open(raw_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_COLUMNS)
        if new_file:
            writer.writeheader()

        def save(rows, finished):
            writer.writerows(rows)
            f.flush()  # every result is on disk at once, so an interrupted run can be resumed
            elapsed = time.perf_counter() - started
            remaining = elapsed / finished * (total - finished)
            first = rows[0]
            comparisons = ", ".join(f"{r['algorithm'].removeprefix('Algorytm ')}: {r['n_comparisons']}" for r in rows)
            print(f"[{finished}/{total}] N={first['n_alternatives']} k={first['n_criteria']} "
                  f"powt.={first['repetition']} | porównania – {comparisons} | "
                  f"upłynęło {format_duration(elapsed)}, zostało ~{format_duration(remaining)}", flush=True)

        if workers == 1:
            for finished, task in enumerate(tasks, start=1):
                save(run_task(task, config), finished)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run_task, task, config) for task in tasks]
                for finished, future in enumerate(as_completed(futures), start=1):
                    save(future.result(), finished)


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


# --------------------------------------------------------------- summary
def summarize(output_dir):
    raw = pd.read_csv(output_dir / "raw.csv")
    groups = raw.groupby(["n_alternatives", "n_criteria", "algorithm"], sort=True)
    summary = groups[list(METRICS)].agg(["mean", "std", "min", "max"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary["repetitions"] = groups.size()
    summary["correct_share"] = groups["correct"].apply(lambda c: (c == "tak").mean() if c.notna().any() else np.nan)
    summary = summary.reset_index()
    summary.to_csv(output_dir / "summary.csv", index=False)

    for metric, file_name in [("n_comparisons", "comparisons.csv"), ("time_ms", "time_ms.csv")]:
        table = summary.pivot_table(index=["n_alternatives", "n_criteria"], columns="algorithm",
                                    values=f"{metric}_mean")[list(raw["algorithm"].unique())]  # config order
        table.round(3).to_csv(output_dir / file_name)

    write_report(summary, output_dir)
    incorrect = summary[summary["correct_share"] < 1]
    print(f"\nPodsumowanie zapisane w {output_dir}/ (summary.csv, comparisons.csv, time_ms.csv, report.html)")
    print("\nŚrednia liczba porównań:")
    print(pd.read_csv(output_dir / "comparisons.csv", index_col=[0, 1]).round(1).to_string())
    if len(incorrect):
        print("\nUWAGA – niepoprawne wyniki (udział poprawnych < 100%):")
        print(incorrect[["n_alternatives", "n_criteria", "algorithm", "correct_share"]].to_string(index=False))


def write_report(summary, output_dir):
    try:
        import plotly.express as px
    except ImportError:
        print("Brak pakietu plotly – pomijam report.html")
        return
    parts = []
    for i, (metric, label) in enumerate(METRICS.items()):
        fig = px.line(summary, x="n_criteria", y=f"{metric}_mean", error_y=f"{metric}_std", color="algorithm",
                      facet_col="n_alternatives", markers=True, log_y=metric != "n_nondominated",
                      labels={"n_criteria": "liczba kryteriów k", f"{metric}_mean": label,
                              "algorithm": "algorytm", "n_alternatives": "N"},
                      title=f"{label.capitalize()} – średnia ± odchylenie standardowe")
        fig.update_yaxes(matches=None, showticklabels=True)
        fig.update_xaxes(tickvals=sorted(summary["n_criteria"].unique()))
        parts.append(fig.to_html(full_html=False, include_plotlyjs=(i == 0)))
    html = ("<html><head><meta charset='utf-8'><title>Raport eksperymentu</title></head><body>"
            f"<h1>Raport eksperymentu: {output_dir.name}</h1>" + "".join(parts) + "</body></html>")
    (output_dir / "report.html").write_text(html, encoding="utf-8")


# ------------------------------------------------------------------ main
def main():
    parser = argparse.ArgumentParser(description="Seria eksperymentów z algorytmami OWD.")
    parser.add_argument("config", nargs="?", help="plik konfiguracji TOML")
    parser.add_argument("--output", type=Path, default=Path("results"), help="katalog na wyniki (domyślnie results/)")
    parser.add_argument("--workers", type=int, default=1,
                        help="liczba procesów (>1 przyspiesza, ale czasy są mniej porównywalne)")
    parser.add_argument("--quick", action="store_true", help="tylko 2 powtórzenia na rozmiar – test konfiguracji")
    parser.add_argument("--resume", type=Path, help="dokończ przerwany eksperyment z tego katalogu")
    parser.add_argument("--summarize", type=Path, help="tylko przelicz podsumowanie i raport z raw.csv")
    args = parser.parse_args()

    if args.summarize:
        summarize(args.summarize)
        return
    if args.resume:
        output_dir = args.resume
        config = load_config(output_dir / "config.toml")
    elif args.config:
        config = load_config(args.config)
        if args.quick:
            config["name"] += "_quick"
            for size in config["sizes"]:
                size["repetitions"] = min(size["repetitions"], 2)
        output_dir = args.output / f"{config['name']}_{datetime.now():%Y-%m-%d_%H%M%S}"
        output_dir.mkdir(parents=True)
        save_config(config, output_dir / "config.toml")
    else:
        parser.error("podaj plik konfiguracji albo --resume / --summarize")

    n_datasets = sum(size["repetitions"] * len(size["criteria"]) for size in config["sizes"])
    print(f"Eksperyment „{config['name']}”: {n_datasets} zbiorów danych × {len(config['algorithms'])} algorytmy "
          f"→ {output_dir}/", flush=True)
    try:
        run(config, output_dir, args.workers)
    except KeyboardInterrupt:
        print(f"\nPrzerwano. Wznów poleceniem:  python run_experiments.py --resume {output_dir}")
        sys.exit(1)
    summarize(output_dir)


if __name__ == "__main__":
    main()

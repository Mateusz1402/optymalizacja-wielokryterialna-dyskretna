"""GUI for running experiments with multi-criteria (Pareto) optimisation algorithms.

Run with:  python app.py
"""
import csv
import random
import re
import time
import tkinter as tk
from collections import Counter
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

from data_browser import DataBrowser
from data_generator import DISTRIBUTIONS, generate_points
from owd_filtracja_punktow import algorytm_z_filtracja
from owd_punkt_idealny import algorytm_punkt_idealny

# Every algorithm minimises all criteria: it takes (points, compared=Counter)
# and returns (nondominated, n_comparisons). Maximised criteria are negated before the call.
ALGORITHMS = {
    "Algorytm z filtracją": algorytm_z_filtracja,
    "Algorytm punktu idealnego": algorytm_punkt_idealny,
}

# Plot layers: key -> (label, enabled by default)
LAYERS = {
    "all": ("Zbiór punktów", True),
    "dominated": ("Zdominowane", True),
    "compared": ("Porównywane", False),
    "nondominated": ("Niezdominowane", True),
    "front": ("Linia frontu Pareto (2D)", True),
    "ideal": ("Punkt idealny", False),
}

HISTORY_COLUMNS = [
    ("run", "#", 40),
    ("timestamp", "czas uruchomienia", 130),
    ("algorithm", "algorytm", 170),
    ("distribution", "rozkład", 90),
    ("means", "średnia", 70),
    ("stds", "odchylenie", 75),
    ("n_alternatives", "N", 60),
    ("n_criteria", "k", 35),
    ("criteria", "kryteria", 120),
    ("seed", "seed", 90),
    ("rounded", "zaokr.", 50),
    ("directions", "kierunek", 80),
    ("n_nondominated", "|P|", 50),
    ("n_comparisons", "porównania", 85),
    ("time_ms", "czas [ms]", 80),
]


def parse_numbers(text):
    """Parse '10' or '10; 20; 30' (comma accepted as decimal separator)."""
    parts = [p for p in re.split(r"[;\s]+", text.strip()) if p]
    if not parts:
        raise ValueError("Podaj co najmniej jedną liczbę")
    return [float(p.replace(",", ".")) for p in parts]


def parse_directions(text, n_criteria):
    """Parse 'min', 'max' or 'min; max; ...' into a list of +1 (min) / -1 (max) signs."""
    parts = [p.lower() for p in re.split(r"[;,\s]+", text.strip()) if p]
    if not parts or any(p not in ("min", "max") for p in parts):
        raise ValueError("Kierunek: podaj „min”, „max” albo listę np. „min; max”")
    if len(parts) == 1:
        parts *= n_criteria
    if len(parts) != n_criteria:
        raise ValueError(f"Liczba kierunków ({len(parts)}) nie zgadza się z liczbą kryteriów ({n_criteria})")
    return [1 if p == "min" else -1 for p in parts]


def format_directions(signs):
    return ";".join("min" if s == 1 else "max" for s in signs)


class DebouncedCanvas(FigureCanvasTkAgg):
    """Tk canvas that redraws the figure only after the window stops being resized.

    The stock canvas re-renders the whole figure on every <Configure> event,
    which makes dragging the window edge very choppy (especially on macOS).
    """
    RESIZE_DELAY_MS = 120

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resize_job = None

    def resize(self, event):
        widget = self.get_tk_widget()
        if self._resize_job is not None:
            widget.after_cancel(self._resize_job)
        self._resize_job = widget.after(self.RESIZE_DELAY_MS, lambda: self._do_resize(event))

    def _do_resize(self, event):
        self._resize_job = None
        super().resize(event)


class ExperimentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Optymalizacja wielokryterialna – eksperymenty")
        self.geometry("1350x880")

        self.points = []          # current data set (list of tuples)
        self.points_array = None  # the same data as a numpy array (for plotting)
        self.layer_artists = {}   # plot layer key -> matplotlib artist
        self.criteria_names = []  # custom criterion names (missing ones default to f1, f2, ...)
        self.data_browser = None  # DataBrowser window, if open
        self.selected_ids = []    # points selected in the data browser (highlighted on the plot)
        self.selection_artist = None
        self.data_params = None   # parameters the current data set was generated with
        self.result = None        # last algorithm result (dict)
        self.history = []         # summary rows of all runs
        self.run_counter = 0

        self._build_controls()
        self._build_plot()
        self._build_history()
        self._update_axis_choices()

    # ------------------------------------------------------------------ GUI
    def _build_controls(self):
        panel = ttk.Frame(self, padding=8)
        panel.grid(row=0, column=0, sticky="ns")

        algo_box = ttk.LabelFrame(panel, text="Algorytm", padding=6)
        algo_box.pack(fill="x", pady=4)
        self.algorithm_var = tk.StringVar(value=next(iter(ALGORITHMS)))
        ttk.Combobox(algo_box, textvariable=self.algorithm_var, values=list(ALGORITHMS),
                     state="readonly", width=28).pack(fill="x")

        data_box = ttk.LabelFrame(panel, text="Dane wejściowe", padding=6)
        data_box.pack(fill="x", pady=4)
        self.distribution_var = tk.StringVar(value=DISTRIBUTIONS["normal"])
        self.means_var = tk.StringVar(value="10")
        self.stds_var = tk.StringVar(value="3")
        self.n_alternatives_var = tk.StringVar(value="100")
        self.n_criteria_var = tk.StringVar(value="2")
        self.seed_var = tk.StringVar(value="42")
        self.round_var = tk.BooleanVar(value=False)
        self.directions_var = tk.StringVar(value="min")

        row = 0
        ttk.Label(data_box, text="Rozkład").grid(row=row, column=0, sticky="w")
        ttk.Combobox(data_box, textvariable=self.distribution_var, values=list(DISTRIBUTIONS.values()),
                     state="readonly", width=26).grid(row=row, column=1, columnspan=2, sticky="ew")
        for label, var in [("Średnia", self.means_var), ("Odchylenie std.", self.stds_var),
                           ("Liczba alternatyw N", self.n_alternatives_var),
                           ("Liczba kryteriów k", self.n_criteria_var)]:
            row += 1
            ttk.Label(data_box, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(data_box, textvariable=var, width=14).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(data_box, text="Seed").grid(row=row, column=0, sticky="w")
        ttk.Entry(data_box, textvariable=self.seed_var, width=10).grid(row=row, column=1, sticky="ew")
        ttk.Button(data_box, text="Losuj", width=6, command=self._random_seed).grid(row=row, column=2)
        row += 1
        ttk.Label(data_box, text="Kierunek").grid(row=row, column=0, sticky="w")
        ttk.Combobox(data_box, textvariable=self.directions_var, values=["min", "max"],
                     width=12).grid(row=row, column=1, columnspan=2, sticky="ew")
        row += 1
        ttk.Label(data_box, text="Nazwy kryteriów").grid(row=row, column=0, sticky="w")
        self.names_var = tk.StringVar()
        names_entry = ttk.Entry(data_box, textvariable=self.names_var, width=14)
        names_entry.grid(row=row, column=1, columnspan=2, sticky="ew")
        names_entry.bind("<Return>", lambda _: self._apply_names_from_entry())
        names_entry.bind("<FocusOut>", lambda _: self._apply_names_from_entry())
        row += 1
        ttk.Checkbutton(data_box, text="Zaokrąglaj do liczb całkowitych",
                        variable=self.round_var).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        ttk.Label(data_box, text="Średnią, odchylenie i kierunek można podać\nosobno dla każdego kryterium, "
                                 "np. „10; 20”,\n„min; max”. Nazwy kryteriów rozdzielaj „;”\n(Enter zatwierdza). Pusty seed = losowy.",
                  foreground="gray").grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 0))
        data_box.columnconfigure(1, weight=1)
        self.n_criteria_var.trace_add("write", lambda *_: self._update_axis_choices())

        actions = ttk.Frame(panel)
        actions.pack(fill="x", pady=4)
        ttk.Button(actions, text="Generuj dane", command=self.on_generate).pack(fill="x", pady=1)
        ttk.Button(actions, text="Uruchom algorytm", command=self.on_run).pack(fill="x", pady=1)
        ttk.Button(actions, text="Uruchom wszystkie algorytmy", command=self.on_run_all).pack(fill="x", pady=1)
        ttk.Button(actions, text="Przeglądaj dane", command=self.open_data_browser).pack(fill="x", pady=1)

        plot_box = ttk.LabelFrame(panel, text="Wykres", padding=6)
        plot_box.pack(fill="x", pady=4)
        self.axis_combos = []
        for i, name in enumerate(["Oś X", "Oś Y", "Oś Z"]):
            ttk.Label(plot_box, text=name).grid(row=i, column=0, sticky="w")
            combo = ttk.Combobox(plot_box, state="readonly", width=14)
            combo.grid(row=i, column=1, sticky="w")
            combo.bind("<<ComboboxSelected>>", lambda _: self.redraw())
            self.axis_combos.append(combo)
        self.plot_3d_var = tk.BooleanVar(value=False)
        self.plot_3d_check = ttk.Checkbutton(plot_box, text="Wykres 3D", variable=self.plot_3d_var,
                                             command=self.redraw)
        self.plot_3d_check.grid(row=3, column=0, columnspan=2, sticky="w")
        self.layer_vars = {}
        for i, (key, (label, default)) in enumerate(LAYERS.items()):
            var = tk.BooleanVar(value=default)
            self.layer_vars[key] = var
            ttk.Checkbutton(plot_box, text=label, variable=var, command=self._apply_layers).grid(
                row=4 + i, column=0, columnspan=2, sticky="w")

        result_box = ttk.LabelFrame(panel, text="Wynik", padding=6)
        result_box.pack(fill="x", pady=4)
        self.result_var = tk.StringVar(value="Brak wyników")
        ttk.Label(result_box, textvariable=self.result_var, justify="left").pack(anchor="w")

        save_box = ttk.LabelFrame(panel, text="Zapis do CSV", padding=6)
        save_box.pack(fill="x", pady=4)
        ttk.Button(save_box, text="Zapisz wynik (punkty)", command=self.save_result_csv).pack(fill="x", pady=1)
        ttk.Button(save_box, text="Zapisz historię eksperymentów", command=self.save_history_csv).pack(fill="x", pady=1)
        ttk.Button(save_box, text="Wyczyść historię", command=self.clear_history).pack(fill="x", pady=1)

    def _build_plot(self):
        frame = ttk.Frame(self)
        frame.grid(row=0, column=1, sticky="nsew")
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = DebouncedCanvas(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        NavigationToolbar2Tk(self.canvas, frame).update()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

    def _build_history(self):
        frame = ttk.LabelFrame(self, text="Historia eksperymentów", padding=4)
        frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        self.history_tree = ttk.Treeview(frame, columns=[c[0] for c in HISTORY_COLUMNS],
                                         show="headings", height=7)
        for key, label, width in HISTORY_COLUMNS:
            self.history_tree.heading(key, text=label)
            self.history_tree.column(key, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # -------------------------------------------------------------- helpers
    def _random_seed(self):
        self.seed_var.set(str(random.randint(0, 2**31 - 1)))

    def _n_criteria(self):
        try:
            return max(1, int(self.n_criteria_var.get()))
        except ValueError:
            return 2

    def _names(self, k):
        """Names of the first k criteria (default fi when not given)."""
        return [self.criteria_names[i] if i < len(self.criteria_names) and self.criteria_names[i]
                else f"f{i + 1}" for i in range(k)]

    def _update_axis_choices(self):
        k = self._n_criteria()
        names = self._names(k)
        self.names_var.set("; ".join(names))
        # Axes are tracked by index, so renaming a criterion keeps the selection
        current = [combo.current() for combo in self.axis_combos]
        for i, combo in enumerate(self.axis_combos):
            combo["values"] = names
            index = current[i]
            if index < 0 or index >= k or index in current[:i]:
                index = min(i, k - 1)
                current[i] = index
            combo.current(index)
        self.plot_3d_check.state(["!disabled"] if k >= 3 else ["disabled"])
        if k < 3:
            self.plot_3d_var.set(False)

    def _set_names(self, names):
        """Validate and apply criterion names; empty names fall back to f1, f2, ..."""
        names = [name.strip() or f"f{i + 1}" for i, name in enumerate(names)]
        if len(set(names)) != len(names):
            messagebox.showerror("Nazwy kryteriów", "Nazwy kryteriów muszą być różne.")
            self._update_axis_choices()  # restore the entry
            return
        extra = self.criteria_names[len(names):]
        self.criteria_names = names + extra
        self._update_axis_choices()
        self.redraw()
        if self.data_browser is not None:
            self.data_browser.set_names(self._names(self._data_k()))

    def _apply_names_from_entry(self):
        k = self._n_criteria()
        parts = self.names_var.get().split(";")
        names = [parts[i] if i < len(parts) else "" for i in range(k)]
        if names != self._names(k):
            self._set_names(names)

    def rename_criterion(self, index, name):
        names = self._names(max(self._n_criteria(), index + 1))
        names[index] = name
        self._set_names(names)

    def _data_k(self):
        return len(self.points[0]) if self.points else self._n_criteria()

    def _read_params(self):
        """Read and validate the data-generation parameters from the form."""
        distribution = next(k for k, v in DISTRIBUTIONS.items() if v == self.distribution_var.get())
        seed_text = self.seed_var.get().strip()
        if not seed_text:
            self._random_seed()
            seed_text = self.seed_var.get()
        return {
            "distribution": distribution,
            "means": parse_numbers(self.means_var.get()),
            "stds": parse_numbers(self.stds_var.get()),
            "n_alternatives": int(self.n_alternatives_var.get()),
            "n_criteria": int(self.n_criteria_var.get()),
            "seed": int(seed_text),
            "round_values": self.round_var.get(),
            "directions": parse_directions(self.directions_var.get(), int(self.n_criteria_var.get())),
        }

    def _generate(self):
        params = self._read_params()
        self.points = generate_points(params["distribution"], params["means"], params["stds"],
                                      params["n_alternatives"], params["n_criteria"],
                                      seed=params["seed"], round_values=params["round_values"])
        self.points_array = np.array(self.points)
        self.data_params = params
        self.result = None

    def _run_algorithm(self, name):
        signs = self.data_params["directions"]
        # Algorithms minimise, so maximised criteria are negated (f -> -f)
        points_min = [tuple(s * v for s, v in zip(signs, x)) for x in self.points]
        algorithm = ALGORITHMS[name]

        # Timed run without comparison tracking, so the bookkeeping does not distort the time
        start = time.perf_counter()
        algorithm(points_min)
        elapsed_ms = (time.perf_counter() - start) * 1000

        compared = Counter()
        nondominated, n_comparisons = algorithm(points_min, compared=compared)
        nondominated = set(nondominated)
        self.result = {
            "algorithm": name,
            "nondominated_mask": np.array([x in nondominated for x in points_min], dtype=bool),
            "compared_counts": np.array([compared[x] for x in points_min], dtype=int),
            "n_comparisons": n_comparisons,
            "time_ms": elapsed_ms,
        }
        self._add_history_row()

    def _add_history_row(self):
        p, r = self.data_params, self.result
        self.run_counter += 1
        row = {
            "run": self.run_counter,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "algorithm": r["algorithm"],
            "distribution": p["distribution"],
            "means": ";".join(f"{v:g}" for v in p["means"]),
            "stds": ";".join(f"{v:g}" for v in p["stds"]),
            "n_alternatives": p["n_alternatives"],
            "n_criteria": p["n_criteria"],
            "criteria": "; ".join(self._names(p["n_criteria"])),
            "seed": p["seed"],
            "rounded": int(p["round_values"]),
            "directions": format_directions(p["directions"]),
            "n_nondominated": int(r["nondominated_mask"].sum()),
            "n_comparisons": r["n_comparisons"],
            "time_ms": round(r["time_ms"], 3),
        }
        self.history.append(row)
        self.history_tree.insert("", "end", values=[row[c[0]] for c in HISTORY_COLUMNS])
        self.history_tree.yview_moveto(1)

    def _update_result_label(self):
        if self.result is None:
            self.result_var.set(f"Wygenerowano {len(self.points)} punktów\n(algorytm nie uruchomiony)")
            return
        r = self.result
        n_nondominated = int(r["nondominated_mask"].sum())
        n_compared = int((r["compared_counts"] > 0).sum())
        self.result_var.set(
            f"{r['algorithm']}\n"
            f"Kierunek: {format_directions(self.data_params['directions'])}\n"
            f"Punkty: {len(self.points)}\n"
            f"Niezdominowane: {n_nondominated}\n"
            f"Zdominowane: {len(self.points) - n_nondominated}\n"
            f"Porównywane: {n_compared}\n"
            f"Liczba porównań: {r['n_comparisons']}\n"
            f"Czas: {r['time_ms']:.3f} ms"
        )

    # -------------------------------------------------------------- actions
    def _guarded(self, action):
        try:
            action()
        except (ValueError, StopIteration) as error:
            messagebox.showerror("Błąd danych", str(error))
            return False
        return True

    def _after_data_change(self):
        self.selected_ids = []
        self._update_result_label()
        self._refresh_browser()
        self.redraw()

    def on_generate(self):
        if self._guarded(self._generate):
            self._after_data_change()

    def on_run(self):
        # Data are regenerated from the form each time, so every run is reproducible from the seed
        if self._guarded(lambda: (self._generate(), self._run_algorithm(self.algorithm_var.get()))):
            self._after_data_change()

    def on_run_all(self):
        def run_all():
            self._generate()
            results = {}
            for name in ALGORITHMS:
                self._run_algorithm(name)
                results[name] = self.result
            # Show the result of the algorithm selected in the combobox
            self.result = results[self.algorithm_var.get()]
        if self._guarded(run_all):
            self._after_data_change()

    # ---------------------------------------------------------- data view
    def open_data_browser(self):
        if self.data_browser is not None:
            self.data_browser.lift()
            return
        self.data_browser = DataBrowser(self, on_select=self._set_selection, on_rename=self.rename_criterion,
                                        on_close=self._data_browser_closed)
        self._refresh_browser()

    def _refresh_browser(self):
        if self.data_browser is None:
            return
        r = self.result
        self.data_browser.set_data(self.points, r["nondominated_mask"] if r else None,
                                   r["compared_counts"] if r else None, self._names(self._data_k()))

    def _data_browser_closed(self):
        self.data_browser = None
        self._set_selection([])

    def _set_selection(self, ids):
        if ids == self.selected_ids:
            return
        self.selected_ids = ids
        self._draw_selection()
        self._apply_layers()

    # ---------------------------------------------------------------- plot
    def redraw(self):
        """Rebuild the whole figure (new data, result, axes or 2D/3D switch).

        Every layer is drawn once; the layer checkboxes only toggle visibility (_apply_layers).
        """
        self.figure.clear()
        self.layer_artists = {}
        if not self.points:
            self.canvas.draw_idle()
            return
        data = self.points_array
        k = data.shape[1]
        signs = self.data_params["directions"]
        names = self._names(k)
        axis_indices = [min(max(combo.current(), 0), k - 1) for combo in self.axis_combos]
        use_3d = self.plot_3d_var.get() and k >= 3
        dims = axis_indices if use_3d else axis_indices[:2]
        ax = self.figure.add_subplot(111, projection="3d" if use_3d else None)

        self.plot_dims = dims

        def coords(rows):
            return [rows[:, d] for d in dims]

        def markers(rows, **style):
            # ax.plot with markers renders ~6x faster than ax.scatter (single style for all points)
            line, = ax.plot(*coords(rows), linestyle="none", **style)
            return line

        artists = self.layer_artists
        artists["all"] = markers(data, marker="o", ms=3.5, color="lightgray", label=f"Zbiór punktów ({len(data)})")
        result = self.result
        if result is not None:
            mask = result["nondominated_mask"]
            nondominated, dominated = data[mask], data[~mask]
            compared = data[result["compared_counts"] > 0]
            if len(dominated):
                artists["dominated"] = markers(dominated, marker="x", ms=4.2, color="tab:red",
                                               label=f"Zdominowane ({len(dominated)})")
            if len(compared):
                artists["compared"] = markers(compared, marker="o", ms=8.4, mfc="none", mec="tab:orange",
                                              mew=1.2, label=f"Porównywane ({len(compared)})")
            if k == 2 and not use_3d and len(nondominated):
                front = nondominated[np.lexsort((nondominated[:, dims[1]], nondominated[:, dims[0]]))]
                # The staircase hugs the dominated region: it depends on the direction of the X criterion
                where = "post" if signs[dims[0]] == 1 else "pre"
                artists["front"], = ax.step(*coords(front), where=where, c="tab:green", alpha=0.6, linewidth=1)
            if len(nondominated):
                artists["nondominated"] = markers(nondominated, marker="o", ms=6.3, mfc="tab:green", mec="black",
                                                  mew=0.5, zorder=5, label=f"Niezdominowane ({len(nondominated)})")
            title = f"{result['algorithm']} – porównań: {result['n_comparisons']}"
        else:
            title = "Wygenerowane dane"
        ideal = np.array([[data[:, i].min() if signs[i] == 1 else data[:, i].max() for i in range(k)]])
        artists["ideal"] = markers(ideal, marker="*", ms=11, color="tab:blue", zorder=6, label="Punkt idealny")

        def axis_label(d):
            return f"{names[d]} ({'min' if signs[d] == 1 else 'max'})"
        ax.set_xlabel(axis_label(dims[0]))
        ax.set_ylabel(axis_label(dims[1]))
        if use_3d:
            ax.set_zlabel(axis_label(dims[2]))
        else:
            ax.grid(True, alpha=0.3)
        if k > 2 and not use_3d:
            title += f"\n(rzut na kryteria {names[dims[0]]}, {names[dims[1]]}; k = {k})"
        ax.set_title(title)
        self.figure.tight_layout()
        self.selection_artist = None
        self._draw_selection()
        self._apply_layers()

    def _draw_selection(self):
        """Highlight the points selected in the data browser."""
        if self.selection_artist is not None:
            self.selection_artist.remove()
            self.selection_artist = None
        if not self.selected_ids or not self.figure.axes:
            return
        rows = self.points_array[self.selected_ids]
        self.selection_artist, = self.figure.axes[0].plot(
            *[rows[:, d] for d in self.plot_dims], linestyle="none", marker="o", ms=13, mfc="none",
            mec="magenta", mew=2, zorder=7, label=f"Zaznaczone ({len(rows)})")

    def _apply_layers(self):
        """Show/hide already drawn layers – much cheaper than rebuilding the figure."""
        if not self.layer_artists:
            return
        visible = []
        for key, artist in self.layer_artists.items():
            artist.set_visible(self.layer_vars[key].get())
            if artist.get_visible() and not artist.get_label().startswith("_"):
                visible.append(artist)
        if self.selection_artist is not None:
            visible.append(self.selection_artist)
        ax = self.figure.axes[0]
        if visible:
            # A fixed location – loc="best" scans all points on every draw
            ax.legend(handles=visible, loc="upper right", fontsize=8)
        elif ax.get_legend():
            ax.get_legend().remove()
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ CSV
    def save_result_csv(self):
        if self.result is None:
            messagebox.showinfo("Brak wyniku", "Najpierw uruchom algorytm.")
            return
        p, r = self.data_params, self.result
        default_name = f"wynik_{r['algorithm'].split()[-1]}_{p['distribution']}_N{p['n_alternatives']}_seed{p['seed']}.csv"
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=default_name,
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        k = len(self.points[0])
        with open(path, "w", newline="", encoding="utf-8") as f:
            # Metadata as comment lines – read with pandas.read_csv(path, comment="#")
            f.write(f"# algorytm: {r['algorithm']}\n")
            f.write(f"# rozklad: {p['distribution']}; srednia: {p['means']}; odchylenie: {p['stds']}\n")
            f.write(f"# N: {p['n_alternatives']}; k: {p['n_criteria']}; seed: {p['seed']}; "
                    f"zaokraglanie: {p['round_values']}; kierunek: {format_directions(p['directions'])}\n")
            f.write(f"# liczba_porownan: {r['n_comparisons']}; czas_ms: {r['time_ms']:.3f}\n")
            writer = csv.writer(f)
            writer.writerow(["id"] + self._names(k) + ["status", "udzial_w_porownaniach"])
            for i, x in enumerate(self.points):
                status = "niezdominowany" if r["nondominated_mask"][i] else "zdominowany"
                writer.writerow([i] + list(x) + [status, int(r["compared_counts"][i])])
        messagebox.showinfo("Zapisano", f"Zapisano wynik do:\n{path}")

    def save_history_csv(self):
        if not self.history:
            messagebox.showinfo("Brak danych", "Historia eksperymentów jest pusta.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="historia_eksperymentow.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[c[0] for c in HISTORY_COLUMNS])
            writer.writeheader()
            writer.writerows(self.history)
        messagebox.showinfo("Zapisano", f"Zapisano historię ({len(self.history)} wierszy) do:\n{path}")

    def clear_history(self):
        self.history.clear()
        self.run_counter = 0
        self.history_tree.delete(*self.history_tree.get_children())


if __name__ == "__main__":
    ExperimentApp().mainloop()

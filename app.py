"""Streamlit app for experiments with multi-criteria (Pareto) optimisation algorithms.

Run with:  streamlit run app.py
"""
import random

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_generator import DISTRIBUTIONS, generate_points
from experiment import (ALGORITHMS, HISTORY_COLUMNS, format_correctness, format_directions,
                        history_row, ideal_point, result_csv, run_algorithm)

DEFAULT_MEAN, DEFAULT_STD = 10.0, 3.0
CRITERIA_COLUMNS = ["name", "direction", "mean", "std"]
RESERVED_NAMES = {"id", "status", "porównania"}

LAYERS = {
    "all": "Zbiór punktów",
    "dominated": "Zdominowane",
    "compared": "Porównywane",
    "nondominated": "Niezdominowane",
    "front": "Front Pareto (2D)",
    "ideal": "Punkt idealny",
}
DEFAULT_LAYERS = ["all", "dominated", "nondominated", "front"]

STATUS_FILTERS = {
    "all": "Wszystkie",
    "nondominated": "Niezdominowane",
    "dominated": "Zdominowane",
    "compared": "Porównywane",
}


# ------------------------------------------------------------------ state
def criteria_frame(k, previous=None):
    """Criteria table with k rows; rows of `previous` are kept, new ones get defaults."""
    rows = []
    for i in range(k):
        if previous is not None and i < len(previous):
            rows.append(previous.iloc[i][CRITERIA_COLUMNS].to_dict())
        else:
            rows.append({"name": f"f{i + 1}", "direction": "min", "mean": DEFAULT_MEAN, "std": DEFAULT_STD})
    return pd.DataFrame(rows, columns=CRITERIA_COLUMNS)


def init_state():
    defaults = {
        "points": None,           # current data set (list of tuples)
        "params": None,           # parameters the current data set was generated with
        "results": {},            # algorithm name -> result on the current data set
        "history": [],            # summary rows of all runs
        "run_counter": 0,
        "data_version": 0,        # bumped on new data – resets the table selection and plot zoom
        "criteria_base": criteria_frame(2),
        "criteria_version": 0,    # bumped when the criteria table is rebuilt (k changed, "all min/max")
        "seed": 42,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def randomize_seed():
    st.session_state.seed = random.randint(0, 2**31 - 1)


def set_all_directions(direction):
    table = st.session_state.get("criteria_edited", st.session_state.criteria_base).copy()
    table["direction"] = direction
    st.session_state.criteria_base = table
    st.session_state.criteria_version += 1


def clear_history():
    st.session_state.history = []
    st.session_state.run_counter = 0


# --------------------------------------------------------------- helpers
def criteria_editor(k):
    """Editable table with name, direction, mean and std of every criterion."""
    if len(st.session_state.criteria_base) != k:
        previous = st.session_state.get("criteria_edited", st.session_state.criteria_base)
        st.session_state.criteria_base = criteria_frame(k, previous)
        st.session_state.criteria_version += 1
    edited = st.data_editor(
        st.session_state.criteria_base,
        key=f"criteria_{st.session_state.criteria_version}",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        column_config={
            "name": st.column_config.TextColumn("nazwa", width=90),
            "direction": st.column_config.SelectboxColumn("kier.", options=["min", "max"], required=True,
                                                          width=55, help="Kierunek optymalizacji"),
            "mean": st.column_config.NumberColumn("μ", format="%.2f", width=55, help="Średnia"),
            "std": st.column_config.NumberColumn("σ", format="%.2f", min_value=0.0, width=55,
                                                 help="Odchylenie standardowe"),
        },
    )
    st.session_state.criteria_edited = edited
    return edited


def criterion_names(criteria, k):
    """Names of the first k criteria; empty ones default to f1, f2, ..."""
    names = []
    for i in range(k):
        name = criteria["name"].iloc[i] if i < len(criteria) else None
        name = "" if name is None or pd.isna(name) else str(name).strip()
        names.append(name or f"f{i + 1}")
    return names


def read_params(distribution, n_alternatives, n_criteria, seed, round_values, criteria):
    means, stds = criteria["mean"].tolist(), criteria["std"].tolist()
    if any(pd.isna(v) for v in means + stds):
        raise ValueError("Uzupełnij średnią i odchylenie dla każdego kryterium.")
    return {
        "distribution": distribution,
        "means": [float(v) for v in means],
        "stds": [float(v) for v in stds],
        "n_alternatives": int(n_alternatives),
        "n_criteria": int(n_criteria),
        "seed": int(seed),
        "round_values": bool(round_values),
        "directions": [-1 if d == "max" else 1 for d in criteria["direction"]],
    }


def axis_label(names, signs, d):
    return f"{names[d]} ({'min' if signs[d] == 1 else 'max'})"


def build_figure(data, names, signs, dims, use_3d, layers, result, selected_ids, title, revision):
    fig = go.Figure()
    trace_type = go.Scatter3d if use_3d else go.Scattergl  # WebGL keeps large data sets smooth
    scale = 0.6 if use_3d else 1.0
    axes = list(zip("xyz", dims))
    values_hover = "<br>".join(f"{names[d]}: %{{{axis}:.4g}}" for axis, d in axes)
    hover = "id: %{customdata}<br>" + values_hover + "<extra>%{fullData.name}</extra>"

    def add_points(indices, label, **marker):
        indices = np.asarray(indices, dtype=int)
        if len(indices) == 0:
            return
        marker["size"] = marker.get("size", 6) * scale
        fig.add_trace(trace_type(mode="markers", name=f"{label} ({len(indices)})", customdata=indices,
                                 hovertemplate=hover, marker=marker,
                                 **{axis: data[indices, d] for axis, d in axes}))

    all_ids = np.arange(len(data))
    if "all" in layers:
        add_points(all_ids, LAYERS["all"], size=5, color="#b0b0b0")
    if result is not None:
        mask = result["nondominated_mask"]
        if "dominated" in layers:
            add_points(all_ids[~mask], LAYERS["dominated"], symbol="x", size=6, color="#d62728")
        if "compared" in layers:
            add_points(all_ids[result["compared_counts"] > 0], LAYERS["compared"], symbol="circle-open",
                       size=12, color="#ff7f0e", line={"width": 1.5})
        if "front" in layers and data.shape[1] == 2 and not use_3d and mask.any():
            front = data[mask][np.lexsort((data[mask][:, dims[1]], data[mask][:, dims[0]]))]
            # The staircase hugs the dominated region: it depends on the direction of the X criterion
            fig.add_trace(go.Scatter(x=front[:, dims[0]], y=front[:, dims[1]], mode="lines",
                                     line={"shape": "hv" if signs[dims[0]] == 1 else "vh",
                                           "color": "#2ca02c", "width": 1},
                                     opacity=0.6, name=LAYERS["front"], hoverinfo="skip"))
        if "nondominated" in layers:
            add_points(all_ids[mask], LAYERS["nondominated"], size=9, color="#2ca02c",
                       line={"color": "black", "width": 0.7})
    if "ideal" in layers:
        point = ideal_point(data, signs)[None, :]
        fig.add_trace(trace_type(mode="markers", name=LAYERS["ideal"],
                                 hovertemplate=values_hover + "<extra>%{fullData.name}</extra>",
                                 marker={"symbol": "diamond" if use_3d else "star", "size": 16 * scale,
                                         "color": "#1f77b4"},
                                 **{axis: point[:, d] for axis, d in axes}))
    if selected_ids:
        add_points(selected_ids, "Zaznaczone", symbol="circle-open", size=18, color="magenta",
                   line={"width": 2.5})

    layout = {
        "title": {"text": title},
        "height": 640,
        "margin": {"l": 10, "r": 10, "t": 90, "b": 10},
        "legend": {"orientation": "h", "y": 1.0, "yanchor": "bottom", "x": 0},
        "uirevision": revision,  # keeps zoom / 3D rotation when only layers or selection change
    }
    if use_3d:
        layout["scene"] = {f"{axis}axis_title": axis_label(names, signs, d) for axis, d in axes}
    else:
        layout["xaxis_title"] = axis_label(names, signs, dims[0])
        layout["yaxis_title"] = axis_label(names, signs, dims[1])
    fig.update_layout(**layout)
    return fig


def axis_select(column, label, key, k, names, default):
    default = min(default, k - 1)
    if st.session_state.get(key, default) >= k:
        st.session_state[key] = default  # the chosen criterion no longer exists
    return column.selectbox(label, range(k), index=default, format_func=lambda i: names[i], key=key)


# ------------------------------------------------------------------ page
st.set_page_config(page_title="OWD – eksperymenty", page_icon="📈", layout="wide")
init_state()

with st.sidebar:
    st.header("Algorytm")
    algorithm = st.selectbox("Algorytm", list(ALGORITHMS), key="algorithm", label_visibility="collapsed")

    st.header("Dane wejściowe")
    distribution = st.selectbox("Rozkład", list(DISTRIBUTIONS), format_func=DISTRIBUTIONS.get)
    n_alternatives = st.number_input("Liczba alternatyw N", min_value=1, max_value=200_000, value=100, step=50)
    n_criteria = int(st.number_input("Liczba kryteriów k", min_value=1, max_value=50, value=2))
    seed_column, button_column = st.columns([4, 1], vertical_alignment="bottom")
    seed = seed_column.number_input("Seed", min_value=0, max_value=2**31 - 1, key="seed")
    button_column.button("🎲", on_click=randomize_seed, help="Losuj seed")
    round_values = st.checkbox("Zaokrąglaj do liczb całkowitych")

    st.header("Kryteria")
    criteria = criteria_editor(n_criteria)
    min_column, max_column = st.columns(2)
    min_column.button("Wszystkie min", on_click=set_all_directions, args=("min",), width="stretch")
    max_column.button("Wszystkie max", on_click=set_all_directions, args=("max",), width="stretch")
    st.caption("Kierunek, średnia i odchylenie działają od następnego uruchomienia, nazwy – od razu.")

    st.divider()
    generate_clicked = st.button("Generuj dane", width="stretch")
    run_clicked = st.button("Uruchom algorytm", type="primary", width="stretch")
    run_all_clicked = st.button("Uruchom wszystkie algorytmy", width="stretch")

names_now = criterion_names(criteria, n_criteria)
if len(set(names_now)) != len(names_now) or RESERVED_NAMES & set(names_now):
    st.sidebar.warning("Nazwy kryteriów muszą być różne i inne niż „id” / „status” – używam nazw domyślnych.")
    criteria = criteria.assign(name=[f"f{i + 1}" for i in range(n_criteria)])

if generate_clicked or run_clicked or run_all_clicked:
    try:
        params = read_params(distribution, n_alternatives, n_criteria, seed, round_values, criteria)
        points = generate_points(params["distribution"], params["means"], params["stds"],
                                 params["n_alternatives"], params["n_criteria"],
                                 seed=params["seed"], round_values=params["round_values"])
    except ValueError as error:
        st.sidebar.error(str(error))
    else:
        # Data are regenerated on every run, so each run is reproducible from the seed
        st.session_state.points = points
        st.session_state.params = params
        st.session_state.results = {}
        st.session_state.data_version += 1
        to_run = list(ALGORITHMS) if run_all_clicked else [algorithm] if run_clicked else []
        for name in to_run:
            with st.spinner(f"{name}…"):
                result = run_algorithm(name, points, params["directions"])
            st.session_state.results[name] = result
            st.session_state.run_counter += 1
            st.session_state.history.append(history_row(st.session_state.run_counter, params, result,
                                                        criterion_names(criteria, n_criteria)))

st.title("Optymalizacja wielokryterialna – eksperymenty")
points = st.session_state.points
if points is None:
    st.info("Ustaw parametry w panelu bocznym i kliknij „Generuj dane” albo „Uruchom algorytm”.")
    st.stop()

params = st.session_state.params
data = np.array(points, dtype=float)
k = data.shape[1]
names = criterion_names(criteria, k)
result = st.session_state.results.get(algorithm)
signs = result["signs"] if result else params["directions"]

# ---------------------------------------------------------------- summary
if result:
    mask = result["nondominated_mask"]
    n_extra, n_missing = result["correctness"]
    st.caption(f"**{algorithm}** · kierunek: {format_directions(signs)} · N = {len(data)} · k = {k} · "
               f"rozkład: {DISTRIBUTIONS[params['distribution']]} · seed: {params['seed']}")
    metrics = st.columns(6)
    metrics[0].metric("Niezdominowane", int(mask.sum()))
    metrics[1].metric("Zdominowane", int((~mask).sum()))
    metrics[2].metric("Porównywane punkty", int((result["compared_counts"] > 0).sum()))
    metrics[3].metric("Liczba porównań", result["n_comparisons"])
    metrics[4].metric("Czas [ms]", f"{result['time_ms']:.3f}")
    metrics[5].metric("Poprawny wynik", "tak" if n_extra == n_missing == 0 else "NIE")
    if n_extra or n_missing:
        st.error(f"Wynik niezgodny z definicją dominacji Pareto: {format_correctness(n_extra, n_missing)}.")
else:
    st.caption(f"Wygenerowano {len(data)} punktów (k = {k}). Algorytm „{algorithm}” nie był jeszcze "
               "uruchomiony na tych danych.")

experiment_tab, history_tab = st.tabs(["Wykres i dane",
                                       f"Historia eksperymentów ({len(st.session_state.history)})"])

with experiment_tab:
    # The table is prepared first – its selection is needed to highlight points on the plot
    table = pd.DataFrame(data, columns=names)
    table.insert(0, "id", np.arange(len(data)))
    if result:
        table["status"] = np.where(result["nondominated_mask"], "niezdominowany", "zdominowany")
        table["porównania"] = result["compared_counts"]
    status_filter = st.session_state.get("status_filter", "all") if result else "all"
    if status_filter == "nondominated":
        shown = table[result["nondominated_mask"]]
    elif status_filter == "dominated":
        shown = table[~result["nondominated_mask"]]
    elif status_filter == "compared":
        shown = table[result["compared_counts"] > 0]
    else:
        shown = table
    table_key = f"table_{st.session_state.data_version}_{algorithm}_{status_filter}"
    selection = st.session_state.get(table_key)
    selected_rows = selection["selection"]["rows"] if selection else []
    selected_ids = shown["id"].iloc[selected_rows].tolist()

    plot_column, table_column = st.columns([3, 2], gap="medium")
    with plot_column:
        controls = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
        use_3d = controls[3].toggle("3D", key="plot_3d", disabled=k < 3) and k >= 3
        dims = [axis_select(controls[0], "Oś X", "x_dim", k, names, 0),
                axis_select(controls[1], "Oś Y", "y_dim", k, names, 1)]
        if use_3d:
            dims.append(axis_select(controls[2], "Oś Z", "z_dim", k, names, 2))
        layers = st.pills("Warstwy", list(LAYERS), selection_mode="multi", default=DEFAULT_LAYERS,
                          format_func=LAYERS.get, key="layers") or []

        title = f"{algorithm} – porównań: {result['n_comparisons']}" if result else "Wygenerowane dane"
        if k > 2 and not use_3d:
            title += f"<br><sup>rzut na kryteria {names[dims[0]]}, {names[dims[1]]} (k = {k})</sup>"
        figure = build_figure(data, names, signs, dims, use_3d, layers, result, selected_ids, title,
                              revision=f"{st.session_state.data_version}-{dims}-{use_3d}")
        # No wheel zoom: scrolling the page over a 3D plot would zoom it by accident (use the toolbar)
        st.plotly_chart(figure, width="stretch", config={"scrollZoom": False})

    with table_column:
        st.radio("Pokaż", list(STATUS_FILTERS), format_func=STATUS_FILTERS.get, horizontal=True,
                 key="status_filter", disabled=result is None)
        st.dataframe(shown, key=table_key, on_select="rerun", selection_mode="multi-row", hide_index=True,
                     height=560, width="stretch",
                     column_config={**{name: st.column_config.NumberColumn(format="%.4f") for name in names},
                                    "porównania": st.column_config.NumberColumn(
                                        help="W ilu porównaniach brał udział punkt")})
        st.caption(f"Wierszy: {len(shown)} / {len(table)}. Zaznacz wiersze (pole po lewej), "
                   "aby wyróżnić punkty na wykresie; kliknięcie nagłówka sortuje.")
        if result:
            st.download_button(
                "Pobierz wynik (CSV)", result_csv(points, params, result, names).encode("utf-8"),
                file_name=f"wynik_{algorithm.split()[-1]}_{params['distribution']}_N{len(data)}"
                          f"_seed{params['seed']}.csv",
                mime="text/csv", width="stretch")
        else:
            st.download_button("Pobierz dane (CSV)", table.to_csv(index=False).encode("utf-8"),
                               file_name=f"dane_{params['distribution']}_N{len(data)}_seed{params['seed']}.csv",
                               mime="text/csv", width="stretch")

with history_tab:
    history = st.session_state.history
    if history:
        history_frame = pd.DataFrame(history, columns=list(HISTORY_COLUMNS))
        st.dataframe(history_frame.rename(columns=HISTORY_COLUMNS), hide_index=True, width="stretch")
        download_column, clear_column = st.columns(2)
        download_column.download_button("Pobierz historię (CSV)",
                                        history_frame.to_csv(index=False).encode("utf-8"),
                                        file_name="historia_eksperymentow.csv", mime="text/csv",
                                        width="stretch")
        clear_column.button("Wyczyść historię", on_click=clear_history, width="stretch")
    else:
        st.info("Historia jest pusta – uruchom algorytm.")

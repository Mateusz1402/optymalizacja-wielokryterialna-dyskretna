"""Page: browse results of batch experiments run with run_experiments.py (results/<name>_<date>/raw.csv)."""
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
UPLOAD = "__upload__"

METRICS = {
    "n_comparisons": "Liczba porównań",
    "time_ms": "Czas [ms]",
    "n_nondominated": "Liczba niezdominowanych |P|",
}
METRIC_FORMATS = {"n_comparisons": "%.1f", "time_ms": "%.3f", "n_nondominated": "%.1f"}
STATISTICS = {
    "mean": "średnia",
    "std": "odchylenie std.",
    "median": "mediana",
    "min": "minimum",
    "max": "maksimum",
}
AXES = {"n_criteria": "liczba kryteriów k", "n_alternatives": "liczba alternatyw N"}
LABELS = {"n_criteria": "k", "n_alternatives": "N", "algorithm": "algorytm", **METRICS}
DATASET_KEY = ["n_alternatives", "n_criteria", "repetition"]


# --------------------------------------------------------------- loading
def experiment_dirs():
    if not RESULTS_DIR.exists():
        return []
    dirs = [d for d in RESULTS_DIR.iterdir() if (d / "raw.csv").exists()]
    return sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)


@st.cache_data
def load_raw(path, modified):
    """`modified` is part of the cache key, so a file that is still being written is re-read."""
    return pd.read_csv(path)


def load_config(directory):
    path = directory / "config.toml"
    if not path.exists():
        return None, None
    text = path.read_text(encoding="utf-8")
    try:
        return text, tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return text, None


def expected_results(config):
    """Number of rows raw.csv will have once the experiment is complete."""
    datasets = sum(size["repetitions"] * len(size.get("criteria", config.get("criteria", [])))
                   for size in config.get("sizes", []))
    return datasets * len(config.get("algorithms", []))


def has_verification(raw):
    return raw["correct"].notna().any()


def nondominated_per_dataset(raw):
    """|P| of every data set – taken from correct results (it does not depend on the algorithm)."""
    rows = raw[raw["correct"] == "tak"] if has_verification(raw) else raw
    return rows.drop_duplicates(DATASET_KEY)[DATASET_KEY + ["n_nondominated"]]


def number_columns(frame, number_format):
    return {column: st.column_config.NumberColumn(format=number_format) for column in frame.columns
            if pd.api.types.is_numeric_dtype(frame[column])}


def download(frame, label, file_name, index=True):
    st.download_button(label, frame.to_csv(index=index).encode("utf-8"), file_name=file_name, mime="text/csv")


# ------------------------------------------------------------------ page
st.title("Wyniki eksperymentów")

dirs = experiment_dirs()
with st.sidebar:
    st.header("Eksperyment")
    options = [str(d) for d in dirs] + [UPLOAD]
    if st.session_state.get("results_experiment") not in options:
        st.session_state.results_experiment = options[0]
    choice = st.selectbox("Eksperyment", options, key="results_experiment", label_visibility="collapsed",
                          format_func=lambda o: "Wczytaj plik raw.csv…" if o == UPLOAD else Path(o).name)
    if choice == UPLOAD:
        uploaded = st.file_uploader("Plik raw.csv z wynikami", type="csv")
    st.button("Odśwież", width="stretch", help="Wczytuje plik ponownie – przydatne, gdy eksperyment nadal trwa")

if choice == UPLOAD:
    if uploaded is None:
        st.info("Wybierz plik raw.csv utworzony przez run_experiments.py.")
        st.stop()
    raw, config_text, config, source_name = pd.read_csv(uploaded), None, None, uploaded.name
else:
    directory = Path(choice)
    raw = load_raw(str(directory / "raw.csv"), (directory / "raw.csv").stat().st_mtime)
    config_text, config = load_config(directory)
    source_name = directory.name

missing_columns = {"n_alternatives", "n_criteria", "repetition", "algorithm", *METRICS, "correct"} - set(raw.columns)
if missing_columns:
    st.error(f"To nie jest plik raw.csv z run_experiments.py – brak kolumn: {sorted(missing_columns)}")
    st.stop()
if raw.empty:
    st.info("Plik nie zawiera jeszcze żadnych wyników.")
    st.stop()

algorithms_all = list(raw["algorithm"].unique())  # order of the configuration
with st.sidebar:
    st.header("Filtry")
    algorithms = st.multiselect("Algorytmy", algorithms_all, default=algorithms_all)
    sizes = st.multiselect("Liczba alternatyw N", sorted(raw["n_alternatives"].unique()),
                           default=sorted(raw["n_alternatives"].unique()))
    criteria = st.multiselect("Liczba kryteriów k", sorted(raw["n_criteria"].unique()),
                              default=sorted(raw["n_criteria"].unique()))
    only_correct = st.checkbox("Tylko poprawne wyniki", disabled=not has_verification(raw),
                               help="Pomija wyniki niezgodne z definicją dominacji Pareto")

data = raw[raw["algorithm"].isin(algorithms) & raw["n_alternatives"].isin(sizes) & raw["n_criteria"].isin(criteria)]
if only_correct:
    data = data[data["correct"] == "tak"]
algorithms = [a for a in algorithms_all if a in algorithms]
if data.empty:
    st.warning("Brak wyników dla wybranych filtrów.")
    st.stop()

# ---------------------------------------------------------------- header
st.caption(f"**{source_name}** · zbiorów danych: {raw.drop_duplicates(DATASET_KEY).shape[0]} · "
           f"wyników: {len(raw)} · algorytmy: {', '.join(algorithms_all)}")
if config:
    expected = expected_results(config)
    if expected and len(raw) < expected:
        st.warning(f"Eksperyment niedokończony: {len(raw)} / {expected} wyników. Jeśli został przerwany, "
                   f"dokończysz go poleceniem `python run_experiments.py --resume results/{source_name}`.")
if has_verification(raw):
    incorrect = raw[raw["correct"] != "tak"]
    if len(incorrect):
        per_algorithm = incorrect.groupby("algorithm").size()
        details = ", ".join(f"{name}: {count}" for name, count in per_algorithm.items())
        st.warning(f"{len(incorrect)} z {len(raw)} wyników jest niezgodnych z definicją dominacji Pareto "
                   f"({details}). Ich liczba porównań i |P| nie są wiarygodne – zaznacz „Tylko poprawne wyniki”, "
                   "aby je pominąć, albo zobacz zakładkę „Poprawność”.")
if config_text:
    with st.expander("Konfiguracja eksperymentu (config.toml)"):
        st.code(config_text, language="toml")

charts_tab, tables_tab, pareto_tab, correctness_tab, raw_tab = st.tabs(
    ["Wykresy", "Tabele", "Liczba niezdominowanych", "Poprawność", "Dane surowe"])

# ---------------------------------------------------------------- charts
with charts_tab:
    controls = st.columns([2, 2, 2, 1.3, 1.3], vertical_alignment="bottom")
    metric = controls[0].selectbox("Miara", list(METRICS), format_func=METRICS.get, key="chart_metric")
    x_axis = controls[1].radio("Oś X", list(AXES), format_func=AXES.get, horizontal=True)
    chart_type = controls[2].radio("Wykres", ["line", "box"], horizontal=True,
                                   format_func={"line": "średnia ± odchylenie", "box": "rozkład (pudełkowy)"}.get)
    log_y = controls[3].toggle("Skala log", value=metric != "n_nondominated")
    shared_y = controls[4].toggle("Wspólna Y", value=False, help="Ta sama skala osi Y we wszystkich panelach")
    facet = "n_alternatives" if x_axis == "n_criteria" else "n_criteria"
    order = {"algorithm": algorithms}

    if chart_type == "line":
        stats = data.groupby([x_axis, facet, "algorithm"])[metric].agg(["mean", "std"]).reset_index()
        figure = px.line(stats, x=x_axis, y="mean", error_y="std", color="algorithm", symbol="algorithm",
                         facet_col=facet, facet_col_wrap=3, markers=True, log_y=log_y,
                         log_x=x_axis == "n_alternatives", category_orders=order,
                         labels={**LABELS, "mean": METRICS[metric]})
        # Equal results (e.g. |P| of correct algorithms) lie exactly on top of each other. A series
        # covered by identical series drawn later gets a wider line, so it stays visible as an outline;
        # all other series keep the normal width.
        for i, trace in enumerate(figure.data):
            covering = sum(1 for later in figure.data[i + 1:]
                           if later.xaxis == trace.xaxis and np.array_equal(later.x, trace.x)
                           and np.allclose(later.y, trace.y))
            trace.update(line_width=2 + 2.5 * covering, marker_size=7 + 4 * covering)
        figure.update_xaxes(tickvals=sorted(data[x_axis].unique()))
        figure.update_layout(hovermode="x unified")  # hover lists every algorithm, also overlapping ones
    else:
        boxes = data.assign(**{x_axis: data[x_axis].astype(str)})
        figure = px.box(boxes, x=x_axis, y=metric, color="algorithm", facet_col=facet, facet_col_wrap=3,
                        log_y=log_y, points=False, labels=LABELS,
                        category_orders={**order, x_axis: [str(v) for v in sorted(data[x_axis].unique())]})
    if not shared_y:
        figure.update_yaxes(matches=None, showticklabels=True)
    rows = (data[facet].nunique() + 2) // 3
    figure.update_layout(height=max(420, 360 * rows), margin={"t": 40}, legend_title_text=None)
    st.plotly_chart(figure, width="stretch")
    st.caption("Każdy panel to jedna wartość " + LABELS[facet] + ". Słupki błędów: odchylenie standardowe "
               "z powtórzeń. W skali logarytmicznej słupki mogą być niesymetryczne.")
    if metric == "n_nondominated":
        st.info("|P| zależy tylko od zbioru danych, więc dla poprawnych algorytmów linie pokrywają się "
                "(linia zasłonięta przez identyczną jest rysowana grubiej, więc widać wszystkie). Zestawienie |P| na zbiór danych "
                "jest w zakładce „Liczba niezdominowanych”.")

# ---------------------------------------------------------------- tables
with tables_tab:
    controls = st.columns(3)
    metric = controls[0].selectbox("Miara", list(METRICS), format_func=METRICS.get, key="table_metric")
    statistic = controls[1].selectbox("Statystyka", list(STATISTICS), format_func=STATISTICS.get)
    reference = controls[2].selectbox("Porównaj względem", [None] + algorithms,
                                      format_func=lambda a: "— (wartości bezwzględne)" if a is None else a,
                                      help="Iloraz: algorytm / wybrany algorytm. Wartość < 1 = mniej niż odniesienie.")

    groups = data.groupby(["n_alternatives", "n_criteria"])
    table = data.pivot_table(index=["n_alternatives", "n_criteria"], columns="algorithm", values=metric,
                             aggfunc=statistic)[algorithms]
    table.columns.name = None
    if reference is not None:
        table = table.div(table[reference], axis=0)
        number_format = "%.2f×"
    else:
        number_format = METRIC_FORMATS[metric]
    table.insert(0, "zbiorów danych", groups["repetition"].nunique())
    table.index.names = ["N", "k"]
    st.dataframe(table, width="stretch",
                 column_config={**number_columns(table[algorithms], number_format),
                                "zbiorów danych": st.column_config.NumberColumn(format="%d")})
    file_suffix = "_wzgledne" if reference is not None else ""
    download(table, "Pobierz tabelę (CSV)", f"{source_name}_{metric}_{statistic}{file_suffix}.csv")

    st.subheader("Wszystkie statystyki")
    full = data.groupby(["n_alternatives", "n_criteria", "algorithm"])[list(METRICS)].agg(list(STATISTICS))
    full.columns = [f"{METRICS[m]} – {STATISTICS[s]}" for m, s in full.columns]
    full = full.reset_index().rename(columns={"n_alternatives": "N", "n_criteria": "k", "algorithm": "algorytm"})
    st.dataframe(full, hide_index=True, width="stretch", column_config=number_columns(full, "%.3f"))
    download(full, "Pobierz statystyki (CSV)", f"{source_name}_statystyki.csv", index=False)

# ------------------------------------------------------- nondominated
with pareto_tab:
    pareto = nondominated_per_dataset(data)
    if has_verification(raw):
        st.caption("|P| nie zależy od algorytmu, więc liczony jest raz na zbiór danych – z poprawnych wyników.")
    else:
        st.caption("Eksperyment bez weryfikacji wyników (verify = false) – |P| wzięte z pierwszego algorytmu.")
    if pareto.empty:
        st.warning("Brak poprawnych wyników dla wybranych filtrów.")
    else:
        as_share = st.toggle("Jako odsetek N", help="|P| / N – jaka część alternatyw jest niezdominowana")
        values = pareto.assign(n_nondominated=pareto["n_nondominated"] / pareto["n_alternatives"] * 100
                               if as_share else pareto["n_nondominated"])
        value_label = "|P| / N [%]" if as_share else "|P|"
        summary = values.groupby(["n_alternatives", "n_criteria"])["n_nondominated"].agg(
            ["count", "mean", "std", "min", "max"])
        summary.columns = ["zbiorów danych", "średnia", "odchylenie std.", "minimum", "maksimum"]
        summary.index.names = ["N", "k"]

        left, right = st.columns([2, 3], gap="medium")
        with left:
            st.markdown(f"**Średnie {value_label}** (wiersze N, kolumny k)")
            means = summary["średnia"].unstack("k")
            st.dataframe(means, width="stretch", column_config=number_columns(means, "%.1f"))
            st.markdown(f"**Statystyki {value_label}**")
            st.dataframe(summary, width="stretch", column_config={
                **number_columns(summary, "%.1f"), "zbiorów danych": st.column_config.NumberColumn(format="%d")})
            download(summary, "Pobierz (CSV)", f"{source_name}_niezdominowane.csv")
        with right:
            stats = summary.reset_index()
            figure = px.line(stats, x="k", y="średnia", error_y="odchylenie std.", color=stats["N"].astype(str),
                             markers=True, log_y=not as_share, labels={"średnia": value_label, "color": "N"})
            figure.update_xaxes(tickvals=sorted(stats["k"].unique()))
            figure.update_layout(height=460, legend_title_text="N")
            st.plotly_chart(figure, width="stretch")

# ---------------------------------------------------------- correctness
with correctness_tab:
    if not has_verification(raw):
        st.info("Ten eksperyment był uruchomiony bez weryfikacji wyników (verify = false).")
    else:
        checked = raw[raw["algorithm"].isin(algorithms) & raw["n_alternatives"].isin(sizes)
                      & raw["n_criteria"].isin(criteria)]
        share = checked.assign(ok=checked["correct"] == "tak").pivot_table(
            index=["n_alternatives", "n_criteria"], columns="algorithm", values="ok", aggfunc="mean")[algorithms]
        share.columns.name = None
        share.index.names = ["N", "k"]
        st.markdown("**Odsetek poprawnych wyników** (100% = każdy wynik zgodny z definicją dominacji Pareto)")
        styled = share.style.format("{:.0%}").map(lambda v: "color: #d62728; font-weight: bold" if v < 1 else "")
        st.dataframe(styled, width="stretch")
        wrong = checked[checked["correct"] != "tak"]
        if len(wrong):
            st.markdown(f"**Niepoprawne wyniki ({len(wrong)})** – „+” punkty zdominowane w P, „−” brakujące")
            st.dataframe(wrong, hide_index=True, width="stretch")
        else:
            st.success("Wszystkie wyniki są poprawne.")

# ------------------------------------------------------------------ raw
with raw_tab:
    st.caption(f"Wierszy po filtrach: {len(data)} / {len(raw)}. Seed pozwala odtworzyć zbiór danych "
               "na stronie „Pojedynczy eksperyment” (te same N, k, rozkład i parametry).")
    st.dataframe(data, hide_index=True, width="stretch")
    download(data, "Pobierz dane (CSV)", f"{source_name}_raw_filtrowane.csv", index=False)

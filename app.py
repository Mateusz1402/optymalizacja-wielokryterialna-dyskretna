"""Streamlit app for experiments with multi-criteria (Pareto) optimisation algorithms.

Run with:  streamlit run app.py
"""
import streamlit as st

# Streamlit drops the state of widgets that are not on the current page. Re-assigning their values
# at the start of every run keeps the settings of a page when the user switches to another one.
PERSISTENT_WIDGET_KEYS = [
    # single_experiment.py
    "algorithm", "distribution", "n_alternatives", "n_criteria", "seed", "round_values",
    "plot_3d", "x_dim", "y_dim", "z_dim", "layers", "status_filter",
    # experiment_results.py
    "results_experiment",
]

st.set_page_config(page_title="OWD – eksperymenty", page_icon="📈", layout="wide")
for key in PERSISTENT_WIDGET_KEYS:
    if key in st.session_state:
        st.session_state[key] = st.session_state[key]

page = st.navigation([
    st.Page("app_pages/single_experiment.py", title="Pojedynczy eksperyment", icon="📈", default=True),
    st.Page("app_pages/experiment_results.py", title="Wyniki eksperymentów", icon="📊"),
])
page.run()

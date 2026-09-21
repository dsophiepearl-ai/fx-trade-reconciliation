"""
Streamlit dashboard for the FX Trade Reconciliation Engine.

Two ways to get trade data in:
  - Generate sample data (default) - configurable seed and trade count, so
    the app works immediately with no upload required
  - Upload your own internal blotter + Prime Broker statement CSVs

Run with:  streamlit run src/dashboard.py
"""

import random
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from generate_sample_data import generate_internal_blotter, inject_breaks
from reconcile import load_trades, reconcile
from report import write_report

STATUS_LABELS = {
    "matched": "Matched",
    "break": "Break",
    "missing_external": "Missing (Prime Broker)",
    "missing_internal": "Missing (Internal)",
    "duplicate_entry": "Duplicate",
}
# Status colors: green = good, amber = warning, red = critical, gray = neutral -
# reserved status meanings, kept distinct from any categorical series color.
STATUS_COLORS = {
    "Matched": "#1f9d55",
    "Break": "#d97706",
    "Missing (Prime Broker)": "#dc2626",
    "Missing (Internal)": "#b91c1c",
    "Duplicate": "#6b7280",
}

st.set_page_config(page_title="FX Trade Reconciliation", layout="wide")
st.title("FX Trade Reconciliation Engine")
st.caption("Matches an internal trade blotter against a Prime Broker statement and flags every discrepancy.")

with st.sidebar:
    st.header("Data source")
    source = st.radio("Where should the trade data come from?",
                       ["Generate sample data", "Upload my own files"])

    internal_file = external_file = None
    if source == "Generate sample data":
        seed = st.number_input("Random seed", min_value=1, max_value=9999, value=11, step=1)
        n_trades = st.slider("Number of internal trades", 30, 150, 60, 10)
    else:
        internal_file = st.file_uploader("Internal blotter CSV", type="csv")
        external_file = st.file_uploader("Prime Broker statement CSV", type="csv")

    st.header("Matching tolerances")
    price_tol = st.slider("Price tolerance (%)", 0.0, 1.0, 0.1, 0.01)
    volume_tol = st.slider("Volume tolerance (lots)", 0.0, 0.5, 0.01, 0.01)
    time_tol = st.slider("Timing tolerance (minutes)", 0, 60, 15, 1)

    run = st.button("Run reconciliation", type="primary")

if not run:
    st.info("Configure your data source and tolerances in the sidebar, then click **Run reconciliation**.")
    st.stop()

if source == "Generate sample data":
    rng = random.Random(int(seed))
    internal = generate_internal_blotter(rng, n_trades=int(n_trades))
    external = inject_breaks(internal, rng)
    internal["timestamp"] = pd.to_datetime(internal["timestamp"])
    external["timestamp"] = pd.to_datetime(external["timestamp"])
    for df in (internal, external):
        df["symbol"] = df["symbol"].str.upper().str.strip()
        df["side"] = df["side"].str.upper().str.strip()
else:
    if not internal_file or not external_file:
        st.warning("Upload both files to run the reconciliation.")
        st.stop()
    internal = load_trades(internal_file)
    external = load_trades(external_file)

results_df, duplicates_df = reconcile(
    internal, external,
    time_tolerance_minutes=time_tol,
    price_tolerance_pct=price_tol,
    volume_tolerance=volume_tol,
)

counts = results_df["status"].value_counts().to_dict()
counts["duplicate_entry"] = len(duplicates_df)
total = len(results_df)
missing_total = counts.get("missing_external", 0) + counts.get("missing_internal", 0)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total trades", total)
col2.metric("Matched", counts.get("matched", 0))
col3.metric("Breaks", counts.get("break", 0))
col4.metric("Missing", missing_total)
col5.metric("Duplicates", counts.get("duplicate_entry", 0))

chart_df = pd.DataFrame([
    {"Status": STATUS_LABELS[key], "Trades": value}
    for key, value in counts.items() if key in STATUS_LABELS and value > 0
])
if not chart_df.empty:
    fig = px.bar(chart_df, x="Status", y="Trades", color="Status",
                 color_discrete_map=STATUS_COLORS, text="Trades")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Number of trades",
                       margin=dict(t=10, b=10))
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch")

tab_all, tab_breaks, tab_missing, tab_dup = st.tabs(["All trades", "Breaks", "Missing", "Duplicates"])

with tab_all:
    st.dataframe(results_df, width="stretch")

with tab_breaks:
    breaks = results_df[results_df["status"] == "break"]
    if breaks.empty:
        st.success("No breaks detected.")
    else:
        st.dataframe(breaks, width="stretch")

with tab_missing:
    missing = results_df[results_df["status"].isin(["missing_internal", "missing_external"])]
    if missing.empty:
        st.success("No missing trades detected.")
    else:
        st.dataframe(missing, width="stretch")

with tab_dup:
    if duplicates_df.empty:
        st.success("No duplicate entries detected.")
    else:
        st.dataframe(duplicates_df, width="stretch")

buffer = BytesIO()
write_report(results_df, duplicates_df, buffer)
st.download_button(
    "Download the full Excel report",
    data=buffer.getvalue(),
    file_name="reconciliation_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

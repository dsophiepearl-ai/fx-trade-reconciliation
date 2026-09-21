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

def _fmt(value, spec: str = "") -> str:
    """Format a value for display, showing '—' for missing data instead of 'nan'."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M")
    return format(value, spec) if spec else str(value)


def render_field_check(label: str, internal_val, external_val, diff_label: str, diff_val,
                        tolerance_label: str, tolerance_val, exceeded: bool, unit: str = ""):
    """
    One row of the flag card: the internal value, the external value, and the
    actual math that decided pass or fail — not just a status word.
    """
    icon = "🔴" if exceeded else "🟢"
    verdict = "exceeds tolerance" if exceeded else "within tolerance"
    c1, c2, c3 = st.columns([1, 1, 1.6])
    c1.markdown(f"**Internal**\n\n{_fmt(internal_val)}")
    c2.markdown(f"**Prime Broker**\n\n{_fmt(external_val)}")
    c3.markdown(
        f"**{label}: {icon} {verdict}**\n\n"
        f"{diff_label} = {_fmt(diff_val)}{unit} — {tolerance_label} is {_fmt(tolerance_val)}{unit}"
    )


def render_break_card(row, price_tol, volume_tol, time_tol):
    with st.expander(f"🚩 {row['trade_id']} — {row['symbol']} — {row['detail']}", expanded=False):
        if row["price_exceeded"]:
            render_field_check("Price", row["price_internal"], row["price_external"],
                                "Difference", row["price_diff_pct"], "the tolerance", price_tol,
                                row["price_exceeded"], unit="%")
            st.divider()
        if row["volume_exceeded"]:
            render_field_check("Volume", row["volume_internal"], row["volume_external"],
                                "Difference", row["volume_diff"], "the tolerance", volume_tol,
                                row["volume_exceeded"], unit=" lots")
            st.divider()
        if row["time_exceeded"]:
            render_field_check("Timestamp", row["timestamp_internal"], row["timestamp_external"],
                                "Gap", row["time_diff_minutes"], "the tolerance", time_tol,
                                row["time_exceeded"], unit=" min")
        st.caption(
            "Reasoning: every field is compared independently against its own tolerance. "
            "A field only turns red when the internal and Prime Broker values disagree by more "
            "than what's normal for two independent systems recording the same trade — that's "
            "what separates a genuine break from routine noise."
        )


def render_missing_card(row):
    if row["status"] == "missing_external":
        headline = "Present in the internal blotter — never reported by the Prime Broker"
        left_label, right_label = "Internal (recorded)", "Prime Broker (absent)"
    else:
        headline = "Reported by the Prime Broker — not in the internal blotter"
        left_label, right_label = "Internal (absent)", "Prime Broker (recorded)"

    with st.expander(f"🚩 {row['trade_id']} — {row['symbol']} — {headline}", expanded=False):
        c1, c2 = st.columns(2)
        if row["status"] == "missing_external":
            c1.markdown(f"**{left_label}**\n\n"
                        f"Price: {_fmt(row['price_internal'])}\n\n"
                        f"Volume: {_fmt(row['volume_internal'])}\n\n"
                        f"Time: {_fmt(row['timestamp_internal'])}")
            c2.markdown(f"**{right_label}**\n\n🔴 No matching record found")
        else:
            c1.markdown(f"**{left_label}**\n\n🔴 No matching record found")
            c2.markdown(f"**{right_label}**\n\n"
                        f"Price: {_fmt(row['price_external'])}\n\n"
                        f"Volume: {_fmt(row['volume_external'])}\n\n"
                        f"Time: {_fmt(row['timestamp_external'])}")
        st.caption(
            "Reasoning: this trade_id only appears on one side after matching by ID, so there is "
            "nothing to compare field-by-field — the discrepancy itself *is* the missing record, "
            "which is why it's flagged as unaccounted-for exposure rather than a value mismatch."
        )


tab_all, tab_breaks, tab_missing, tab_dup = st.tabs(["All trades", "Breaks", "Missing", "Duplicates"])

with tab_all:
    st.caption("Full reconciliation output, one row per trade_id, for reference or export.")
    st.dataframe(results_df, width="stretch")

with tab_breaks:
    st.caption(
        "Every trade below exists on both sides but at least one field disagrees beyond tolerance. "
        "Expand a trade to see the exact internal vs. Prime Broker values, the computed difference, "
        "and the tolerance it was measured against — the same comparison an ops desk would walk "
        "through before escalating a break for same-day correction."
    )
    breaks = results_df[results_df["status"] == "break"]
    if breaks.empty:
        st.success("No breaks detected.")
    else:
        for _, row in breaks.iterrows():
            render_break_card(row, price_tol, volume_tol, time_tol)

with tab_missing:
    st.caption(
        "Every trade below appears on only one side once matched by trade_id — there's no field "
        "to compare, the absence itself is the flag. A trade missing from the Prime Broker side "
        "usually means it wasn't confirmed or was rejected on their end; missing from the internal "
        "blotter more often points to a booking gap on our own side. This is the category most "
        "likely to represent real, unaccounted-for exposure if left unresolved."
    )
    missing = results_df[results_df["status"].isin(["missing_internal", "missing_external"])]
    if missing.empty:
        st.success("No missing trades detected.")
    else:
        for _, row in missing.iterrows():
            render_missing_card(row)

with tab_dup:
    st.caption(
        "A duplicate almost always means a system replay or a resent confirmation, not a genuine "
        "second trade — the fix is deduplicating the record, not investigating a live discrepancy. "
        "Still worth flagging separately from a break, since treating it as a break would double-count "
        "real exposure in any downstream risk figure."
    )
    if duplicates_df.empty:
        st.success("No duplicate entries detected.")
    else:
        for _, row in duplicates_df.iterrows():
            with st.expander(f"🚩 {row['trade_id']} — reported {row['occurrences']}x in {row['source']}", expanded=False):
                st.markdown(row["detail"])
                st.caption(
                    "Reasoning: the same trade_id appears more than once on one side only — the "
                    "other side reports it exactly once, which is what tells us this is a repeated "
                    "confirmation rather than two genuinely separate trades that happen to disagree."
                )

buffer = BytesIO()
write_report(results_df, duplicates_df, buffer)
st.download_button(
    "Download the full Excel report",
    data=buffer.getvalue(),
    file_name="reconciliation_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

"""
Core trade reconciliation logic: matches an internal trade blotter against a
Prime Broker statement, and classifies every trade as matched, a specific
kind of break, or a duplicate entry.
"""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["trade_id", "account_id", "symbol", "side", "volume", "price", "timestamp"]


def load_trades(path: str) -> pd.DataFrame:
    """Load and normalize a trade CSV (internal blotter or Prime Broker statement)."""
    df = pd.read_csv(path)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["symbol"] = df["symbol"].str.upper().str.strip()
    df["side"] = df["side"].str.upper().str.strip()
    return df


def _find_duplicates(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    counts = df["trade_id"].value_counts()
    dup_ids = counts[counts > 1].index.tolist()
    rows = [{
        "trade_id": tid,
        "source": source_label,
        "occurrences": int(counts[tid]),
        "detail": f"trade_id {tid} appears {int(counts[tid])} times in the {source_label} file",
    } for tid in dup_ids]
    return pd.DataFrame(rows, columns=["trade_id", "source", "occurrences", "detail"])


def reconcile(internal: pd.DataFrame, external: pd.DataFrame,
              time_tolerance_minutes: float = 15.0,
              price_tolerance_pct: float = 0.1,
              volume_tolerance: float = 0.01):
    """
    Reconciles two trade DataFrames on trade_id and returns:
        results_df    - one row per trade_id, with status in
                         {"matched", "break", "missing_internal", "missing_external"}
                         and a human-readable detail of what didn't match
        duplicates_df - trade_ids that appear more than once on either side
                         (flagged separately, before de-duplication for the 1:1 comparison)
    """
    duplicates_df = pd.concat([
        _find_duplicates(internal, "internal"),
        _find_duplicates(external, "prime_broker"),
    ], ignore_index=True)

    internal_dedup = internal.drop_duplicates(subset="trade_id", keep="first")
    external_dedup = external.drop_duplicates(subset="trade_id", keep="first")

    merged = pd.merge(internal_dedup, external_dedup, on="trade_id", how="outer",
                       suffixes=("_internal", "_external"), indicator=True)

    results = []
    for _, row in merged.iterrows():
        trade_id = row["trade_id"]

        if row["_merge"] == "left_only":
            results.append({"trade_id": trade_id, "status": "missing_external",
                             "detail": "Present in the internal blotter, not found in the Prime Broker statement."})
            continue

        if row["_merge"] == "right_only":
            results.append({"trade_id": trade_id, "status": "missing_internal",
                             "detail": "Present in the Prime Broker statement, not found in the internal blotter."})
            continue

        issues = []

        price_i, price_e = row["price_internal"], row["price_external"]
        if price_i and abs(price_i - price_e) / price_i * 100 > price_tolerance_pct:
            issues.append(f"price break (internal={price_i}, prime_broker={price_e})")

        vol_i, vol_e = row["volume_internal"], row["volume_external"]
        if abs(vol_i - vol_e) > volume_tolerance:
            issues.append(f"volume break (internal={vol_i}, prime_broker={vol_e})")

        ts_i, ts_e = row["timestamp_internal"], row["timestamp_external"]
        delta_minutes = abs((ts_i - ts_e).total_seconds()) / 60
        if delta_minutes > time_tolerance_minutes:
            issues.append(f"timing break ({delta_minutes:.0f} min apart, tolerance {time_tolerance_minutes:.0f} min)")

        if issues:
            results.append({"trade_id": trade_id, "status": "break", "detail": "; ".join(issues)})
        else:
            results.append({"trade_id": trade_id, "status": "matched", "detail": ""})

    results_df = pd.DataFrame(results, columns=["trade_id", "status", "detail"])
    return results_df, duplicates_df

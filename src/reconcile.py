"""
Core trade reconciliation logic: matches an internal trade blotter against a
Prime Broker statement, and classifies every trade as matched, a specific
kind of break, or a duplicate entry.

Every row in the returned DataFrame carries the raw internal/external values
being compared (not just a text summary), so a caller - the CLI, the Excel
report, or the dashboard - can show exactly which field triggered a flag,
by how much, and against what tolerance, instead of just a pass/fail label.
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
        results_df    - one row per trade_id. Always includes trade_id, status,
                         detail (text summary), symbol, account_id, and the raw
                         internal/external price, volume, and timestamp values
                         plus the computed diff and exceeded flag for each field
                         (NaN/False where not applicable, e.g. a missing trade).
        duplicates_df - trade_ids that appear more than once on either side
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
        symbol = row["symbol_internal"] if pd.notna(row.get("symbol_internal")) else row.get("symbol_external")
        account_id = row["account_id_internal"] if pd.notna(row.get("account_id_internal")) else row.get("account_id_external")

        common = {
            "trade_id": trade_id,
            "symbol": symbol,
            "account_id": account_id,
            "price_internal": row.get("price_internal"),
            "price_external": row.get("price_external"),
            "volume_internal": row.get("volume_internal"),
            "volume_external": row.get("volume_external"),
            "timestamp_internal": row.get("timestamp_internal"),
            "timestamp_external": row.get("timestamp_external"),
            "price_diff_pct": None,
            "price_exceeded": False,
            "volume_diff": None,
            "volume_exceeded": False,
            "time_diff_minutes": None,
            "time_exceeded": False,
        }

        if row["_merge"] == "left_only":
            results.append({**common, "status": "missing_external",
                             "detail": "Present in the internal blotter, not found in the Prime Broker statement."})
            continue

        if row["_merge"] == "right_only":
            results.append({**common, "status": "missing_internal",
                             "detail": "Present in the Prime Broker statement, not found in the internal blotter."})
            continue

        issues = []

        price_i, price_e = row["price_internal"], row["price_external"]
        price_diff_pct = abs(price_i - price_e) / price_i * 100 if price_i else 0.0
        price_exceeded = bool(price_i) and price_diff_pct > price_tolerance_pct
        common["price_diff_pct"] = round(price_diff_pct, 4)
        common["price_exceeded"] = price_exceeded
        if price_exceeded:
            issues.append(f"price break (internal={price_i}, prime_broker={price_e})")

        vol_i, vol_e = row["volume_internal"], row["volume_external"]
        volume_diff = abs(vol_i - vol_e)
        volume_exceeded = volume_diff > volume_tolerance
        common["volume_diff"] = round(volume_diff, 4)
        common["volume_exceeded"] = volume_exceeded
        if volume_exceeded:
            issues.append(f"volume break (internal={vol_i}, prime_broker={vol_e})")

        ts_i, ts_e = row["timestamp_internal"], row["timestamp_external"]
        delta_minutes = abs((ts_i - ts_e).total_seconds()) / 60
        time_exceeded = delta_minutes > time_tolerance_minutes
        common["time_diff_minutes"] = round(delta_minutes, 1)
        common["time_exceeded"] = time_exceeded
        if time_exceeded:
            issues.append(f"timing break ({delta_minutes:.0f} min apart, tolerance {time_tolerance_minutes:.0f} min)")

        status = "break" if issues else "matched"
        results.append({**common, "status": status, "detail": "; ".join(issues)})

    results_df = pd.DataFrame(results)
    return results_df, duplicates_df

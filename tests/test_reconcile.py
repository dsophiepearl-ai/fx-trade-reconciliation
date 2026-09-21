import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reconcile import reconcile


COLUMNS = ["trade_id", "account_id", "symbol", "side", "volume", "price", "timestamp"]


def make_df(rows):
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


BASE_ROW = dict(account_id="ACC-1", symbol="EURUSD", side="BUY", volume=1.0, price=1.0850,
                 timestamp="2026-09-18T07:00:00")


def test_identical_trade_is_matched():
    internal = make_df([{**BASE_ROW, "trade_id": "T1"}])
    external = make_df([{**BASE_ROW, "trade_id": "T1"}])

    results, duplicates = reconcile(internal, external)

    assert results.loc[0, "status"] == "matched"
    assert duplicates.empty


def test_trade_missing_from_prime_broker_is_flagged():
    internal = make_df([{**BASE_ROW, "trade_id": "T1"}])
    external = make_df([])

    results, _ = reconcile(internal, external)

    assert results.loc[0, "status"] == "missing_external"


def test_trade_missing_from_internal_blotter_is_flagged():
    internal = make_df([])
    external = make_df([{**BASE_ROW, "trade_id": "T1"}])

    results, _ = reconcile(internal, external)

    assert results.loc[0, "status"] == "missing_internal"


def test_price_break_is_detected():
    internal = make_df([{**BASE_ROW, "trade_id": "T1", "price": 1.0850}])
    external = make_df([{**BASE_ROW, "trade_id": "T1", "price": 1.1000}])  # well outside 0.1% tolerance

    results, _ = reconcile(internal, external, price_tolerance_pct=0.1)

    assert results.loc[0, "status"] == "break"
    assert "price break" in results.loc[0, "detail"]


def test_price_within_tolerance_is_matched():
    internal = make_df([{**BASE_ROW, "trade_id": "T1", "price": 1.08500}])
    external = make_df([{**BASE_ROW, "trade_id": "T1", "price": 1.08501}])  # tiny rounding difference

    results, _ = reconcile(internal, external, price_tolerance_pct=0.1)

    assert results.loc[0, "status"] == "matched"


def test_volume_break_is_detected():
    internal = make_df([{**BASE_ROW, "trade_id": "T1", "volume": 1.0}])
    external = make_df([{**BASE_ROW, "trade_id": "T1", "volume": 1.5}])

    results, _ = reconcile(internal, external, volume_tolerance=0.01)

    assert results.loc[0, "status"] == "break"
    assert "volume break" in results.loc[0, "detail"]


def test_timing_break_beyond_tolerance_is_detected():
    internal = make_df([{**BASE_ROW, "trade_id": "T1", "timestamp": "2026-09-18T07:00:00"}])
    external = make_df([{**BASE_ROW, "trade_id": "T1", "timestamp": "2026-09-18T07:45:00"}])

    results, _ = reconcile(internal, external, time_tolerance_minutes=15)

    assert results.loc[0, "status"] == "break"
    assert "timing break" in results.loc[0, "detail"]


def test_timing_within_tolerance_is_matched():
    internal = make_df([{**BASE_ROW, "trade_id": "T1", "timestamp": "2026-09-18T07:00:00"}])
    external = make_df([{**BASE_ROW, "trade_id": "T1", "timestamp": "2026-09-18T07:05:00"}])

    results, _ = reconcile(internal, external, time_tolerance_minutes=15)

    assert results.loc[0, "status"] == "matched"


def test_duplicate_entry_is_flagged():
    internal = make_df([{**BASE_ROW, "trade_id": "T1"}])
    external = make_df([{**BASE_ROW, "trade_id": "T1"}, {**BASE_ROW, "trade_id": "T1"}])

    _, duplicates = reconcile(internal, external)

    assert len(duplicates) == 1
    assert duplicates.loc[0, "trade_id"] == "T1"
    assert duplicates.loc[0, "source"] == "prime_broker"
    assert duplicates.loc[0, "occurrences"] == 2

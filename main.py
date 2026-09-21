"""
CLI entry point.

    python main.py
    python main.py --internal data/internal_blotter.csv --external data/prime_broker_statement.csv --output reconciliation_report.xlsx
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from reconcile import load_trades, reconcile  # noqa: E402
from report import write_report  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Reconcile an internal trade blotter against a Prime Broker statement.")
    parser.add_argument("--internal", default="data/internal_blotter.csv")
    parser.add_argument("--external", default="data/prime_broker_statement.csv")
    parser.add_argument("--output", default="reconciliation_report.xlsx")
    parser.add_argument("--time-tolerance-minutes", type=float, default=15)
    parser.add_argument("--price-tolerance-pct", type=float, default=0.1)
    parser.add_argument("--volume-tolerance", type=float, default=0.01)
    args = parser.parse_args()

    internal = load_trades(args.internal)
    external = load_trades(args.external)

    results_df, duplicates_df = reconcile(
        internal, external,
        time_tolerance_minutes=args.time_tolerance_minutes,
        price_tolerance_pct=args.price_tolerance_pct,
        volume_tolerance=args.volume_tolerance,
    )

    write_report(results_df, duplicates_df, args.output)

    print("=" * 64)
    print("RECONCILIATION SUMMARY")
    print("=" * 64)
    print(results_df["status"].value_counts().to_string())

    breaks = results_df[results_df["status"] == "break"]
    if not breaks.empty:
        print(f"\nBREAKS DETECTED ({len(breaks)}):")
        print("-" * 64)
        for _, row in breaks.iterrows():
            print(f"  {row['trade_id']}: {row['detail']}")

    missing = results_df[results_df["status"].isin(["missing_internal", "missing_external"])]
    if not missing.empty:
        print(f"\nMISSING TRADES ({len(missing)}):")
        print("-" * 64)
        for _, row in missing.iterrows():
            side = "Prime Broker" if row["status"] == "missing_external" else "internal blotter"
            print(f"  {row['trade_id']}: missing from the {side} ({row['status']})")

    if not duplicates_df.empty:
        print(f"\nDUPLICATE ENTRIES ({len(duplicates_df)}):")
        print("-" * 64)
        for _, row in duplicates_df.iterrows():
            print(f"  {row['detail']}")

    print("\n" + "=" * 64)
    print(f"Full report (color-coded, with a Summary and Duplicates tab) written to: {args.output}")
    print("=" * 64)


if __name__ == "__main__":
    main()

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

    print(results_df["status"].value_counts().to_string())
    if not duplicates_df.empty:
        print(f"\n{len(duplicates_df)} duplicate entr{'y' if len(duplicates_df) == 1 else 'ies'} found.")
    print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()

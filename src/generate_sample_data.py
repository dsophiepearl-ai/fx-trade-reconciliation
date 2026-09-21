"""
Generates a matched pair of sample datasets for the reconciliation engine to
work against:

  data/internal_blotter.csv        - the firm's own trade log
  data/prime_broker_statement.csv  - the Prime Broker's version of the same trades

The Prime Broker file starts as a copy of the internal blotter, then has a
handful of deliberate breaks injected (missing trades, price mismatches,
volume mismatches, a timing shift, a duplicate) so reconcile.py has real
breaks to detect and tests have known-answer fixtures to check against.

Reproducible via a fixed seed - re-running this script always produces the
same two files.
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 11
N_TRADES = 60
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def generate_internal_blotter(rng: random.Random) -> pd.DataFrame:
    base_time = datetime(2026, 9, 18, 7, 0, 0)
    rows = []
    for i in range(1, N_TRADES + 1):
        symbol = rng.choice(SYMBOLS)
        side = rng.choice(["BUY", "SELL"])
        volume = round(rng.uniform(0.1, 5.0), 2)
        price = round(rng.uniform(0.9, 1.3), 5)
        timestamp = base_time + timedelta(minutes=rng.randint(0, 600))
        rows.append({
            "trade_id": f"T{1000 + i}",
            "account_id": f"ACC-{rng.randint(100, 120)}",
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "price": price,
            "timestamp": timestamp.isoformat(),
        })
    return pd.DataFrame(rows)


def inject_breaks(internal: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    pb = internal.copy()

    # Missing trade: drop 3 trades entirely from the Prime Broker side
    missing_ids = rng.sample(list(pb["trade_id"]), 3)
    pb = pb[~pb["trade_id"].isin(missing_ids)].reset_index(drop=True)

    # Price break: nudge the price on 3 trades
    price_break_ids = rng.sample(list(pb["trade_id"]), 3)
    for tid in price_break_ids:
        idx = pb.index[pb["trade_id"] == tid][0]
        pb.loc[idx, "price"] = round(pb.loc[idx, "price"] * (1 + rng.choice([0.004, -0.004])), 5)

    # Volume break: change the volume on 2 trades
    volume_break_ids = rng.sample(list(pb["trade_id"]), 2)
    for tid in volume_break_ids:
        idx = pb.index[pb["trade_id"] == tid][0]
        pb.loc[idx, "volume"] = round(pb.loc[idx, "volume"] + rng.choice([0.5, -0.3]), 2)

    # Timing break: shift the timestamp on 2 trades by more than the matching tolerance
    timing_break_ids = rng.sample(list(pb["trade_id"]), 2)
    for tid in timing_break_ids:
        idx = pb.index[pb["trade_id"] == tid][0]
        ts = datetime.fromisoformat(pb.loc[idx, "timestamp"]) + timedelta(minutes=45)
        pb.loc[idx, "timestamp"] = ts.isoformat()

    # Duplicate: the Prime Broker reports one trade twice
    dup_id = rng.choice(list(pb["trade_id"]))
    dup_row = pb[pb["trade_id"] == dup_id].copy()
    pb = pd.concat([pb, dup_row], ignore_index=True)

    # Also add 2 trades that exist on the Prime Broker side but never made it into
    # the internal blotter (the mirror-image "missing trade" case).
    extra_rows = []
    for i in range(2):
        extra_rows.append({
            "trade_id": f"T{2000 + i}",
            "account_id": f"ACC-{rng.randint(100, 120)}",
            "symbol": rng.choice(SYMBOLS),
            "side": rng.choice(["BUY", "SELL"]),
            "volume": round(rng.uniform(0.1, 5.0), 2),
            "price": round(rng.uniform(0.9, 1.3), 5),
            "timestamp": (datetime(2026, 9, 18, 7, 0, 0) + timedelta(minutes=rng.randint(0, 600))).isoformat(),
        })
    pb = pd.concat([pb, pd.DataFrame(extra_rows)], ignore_index=True)

    return pb.sample(frac=1, random_state=SEED).reset_index(drop=True)  # shuffle row order


def main():
    rng = random.Random(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    internal = generate_internal_blotter(rng)
    prime_broker = inject_breaks(internal, rng)

    internal.to_csv(DATA_DIR / "internal_blotter.csv", index=False)
    prime_broker.to_csv(DATA_DIR / "prime_broker_statement.csv", index=False)

    print(f"Wrote {len(internal)} internal trades and {len(prime_broker)} Prime Broker trades to {DATA_DIR}")


if __name__ == "__main__":
    main()

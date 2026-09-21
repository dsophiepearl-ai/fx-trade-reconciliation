# FX Trade Reconciliation Engine

Matches an internal trade blotter against a Prime Broker statement and flags every discrepancy — the same daily check run at a real brokerage.

## Features

- Matches trades by trade ID, symbol, price, volume, and timestamp
- Flags missing trades, price breaks, volume breaks, timing breaks, and duplicate entries
- Configurable tolerances (price %, volume, timing window) via command-line flags
- Outputs a color-coded Excel report: Summary, Trade Detail, Duplicates

## Skills demonstrated

| Skill | Where |
|---|---|
| Python (pandas data manipulation) | `src/reconcile.py` |
| Rule-based matching & tolerance-based comparison logic | `reconcile()` in `src/reconcile.py` |
| Excel report generation & conditional formatting (openpyxl) | `src/report.py` |
| Synthetic test data generation with reproducible seeded breaks | `src/generate_sample_data.py` |
| Unit testing | `tests/test_reconcile.py` — 9 tests |
| CLI tooling (argparse) | `main.py` |
| Version control | git repo |

## Tech stack

Python 3, pandas, openpyxl

## Project structure

```
fx-trade-reconciliation/
  main.py                       # CLI entry point
  src/
    generate_sample_data.py     # builds sample CSVs, with breaks deliberately injected
    reconcile.py                 # matching and classification logic
    report.py                    # builds the color-coded Excel report
  data/
    internal_blotter.csv         # generated
    prime_broker_statement.csv   # generated
  tests/
    test_reconcile.py
  requirements.txt
```

## What it checks

| Break type | What it means |
|---|---|
| Missing external | Present in the internal blotter, not in the Prime Broker statement |
| Missing internal | Present in the Prime Broker statement, not in the internal blotter |
| Price break | Same trade, fill price differs beyond tolerance |
| Volume break | Same trade, size differs beyond tolerance |
| Timing break | Same trade, timestamps differ beyond tolerance |
| Duplicate entry | Same trade ID reported more than once on either side |

## Run it yourself

```bash
git clone https://github.com/dsophiepearl-ai/fx-trade-reconciliation.git
cd fx-trade-reconciliation
pip install -r requirements.txt
python src/generate_sample_data.py
python main.py
```

Produces `reconciliation_report.xlsx` in the project folder — open it in Excel to see the color-coded results (green = matched, red = missing, amber = break).

Custom tolerances:

```bash
python main.py --price-tolerance-pct 0.05 --volume-tolerance 0.01 --time-tolerance-minutes 10
```

## Test

```bash
pytest
```

9/9 tests pass — each one builds a small two-row fixture with a known, deliberate discrepancy (a price 1.5% off, a timestamp 45 minutes apart, and so on) and checks it gets classified correctly.

## Design notes

- Real trade records are rarely byte-identical between two systems (rounding, feed timing, etc.), so matching uses configurable tolerances rather than exact equality — this mirrors how reconciliation actually works at a brokerage.
- Real Prime Broker data isn't available for a portfolio project, so `generate_sample_data.py` builds a reproducible synthetic pair of files with specific breaks injected, giving both the CLI and the test suite known-answer data to check against.

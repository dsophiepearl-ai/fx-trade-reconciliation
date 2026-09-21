# FX Trade Reconciliation Engine

I built this to demonstrate one of the most literal responsibilities named in forex Risk Analyst and Trading Operations job postings: "reconcile client funding and liaise with Prime Brokers," and "reconciliation, reporting & analytics." It's a working simulation of the daily check a brokerage runs to confirm its own trade records agree with what the Prime Broker reports.

## The problem this solves

A brokerage keeps its own internal log of every trade it executes — the trade blotter. The Prime Broker it trades through keeps its own separate record of the same activity. In theory these should match perfectly; in practice, timing lags, feed errors, and manual adjustments mean they occasionally don't. If a mismatch goes unnoticed, it can mean the firm is carrying risk it doesn't know about, or that client money isn't properly accounted for. Catching and resolving these breaks — every single trading day — is a core part of a risk or operations desk's job.

## How it works

I designed the reconciliation to follow the same sequence a real desk uses:

1. **Extract** — pull the internal blotter and the Prime Broker statement for the same time window
2. **Normalize** — align time zones, symbol naming, and volume conventions between the two files, since two systems rarely format things identically
3. **Match** — pair trades on a shared identifier, then compare price, volume, and timestamp
4. **Flag** — anything that doesn't line up gets classified into a specific break type, not just a generic "mismatch"
5. **Report** — the results are written out as a formatted Excel file, the same kind of output that would go to a risk team for a daily handover

I used configurable tolerances rather than exact matching, because real trade records are almost never byte-identical between two systems — a price difference of a fraction of a percent, or a timestamp a couple of minutes apart, is normal and shouldn't be treated the same as a genuine error.

## What it catches

| Break type | What it means |
|---|---|
| Missing external | The trade is in my internal blotter but the Prime Broker never reported it |
| Missing internal | The Prime Broker reported a trade I don't have on my side |
| Price break | Same trade, but the fill price differs beyond tolerance |
| Volume break | Same trade, but the size differs beyond tolerance |
| Timing break | Same trade, but the timestamps are further apart than expected |
| Duplicate entry | The same trade ID was reported more than once on either side |

## Skills this project demonstrates

| Skill | Where it shows up |
|---|---|
| Python (pandas for data matching and comparison) | `src/reconcile.py` |
| Rule-based, tolerance-driven matching logic | `reconcile()` in `src/reconcile.py` |
| Excel report generation with conditional formatting (openpyxl) | `src/report.py` |
| Designing reproducible test data with deliberate, known-answer breaks | `src/generate_sample_data.py` |
| Unit testing | `tests/test_reconcile.py` — 9 tests, all passing |
| Command-line tooling (argparse) | `main.py` |

## Tech stack

Python 3, pandas, openpyxl

## Project structure

```
fx-trade-reconciliation/
  main.py                       # command-line entry point
  src/
    generate_sample_data.py     # builds sample data, with breaks deliberately injected
    reconcile.py                 # the matching and classification logic
    report.py                    # builds the color-coded Excel report
  data/
    internal_blotter.csv         # generated
    prime_broker_statement.csv   # generated
  tests/
    test_reconcile.py
  requirements.txt
```

## Seeing it run

Real Prime Broker data isn't something I have access to for a portfolio project, so I wrote a generator that builds a reproducible pair of files with specific breaks planted in them — that way both the tool and the test suite have a known answer to check against, the same way you'd validate any reconciliation logic before trusting it with real data.

If you'd like to see it for yourself:

```bash
git clone https://github.com/dsophiepearl-ai/fx-trade-reconciliation.git
cd fx-trade-reconciliation
pip install -r requirements.txt
python src/generate_sample_data.py
python main.py
```

This produces `reconciliation_report.xlsx` — open it in Excel to see the color-coded output (green for matched, red for missing, amber for a break). The tolerances are adjustable from the command line, for example:

```bash
python main.py --price-tolerance-pct 0.05 --volume-tolerance 0.01 --time-tolerance-minutes 10
```

## Testing it

```bash
pytest
```

All 9 tests pass. Each one sets up a small, deliberate discrepancy — a price 1.5% off, a timestamp 45 minutes apart, a duplicate trade ID — and checks that the engine classifies it correctly. That's the same logic that runs against the full sample dataset.

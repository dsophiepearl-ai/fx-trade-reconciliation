# FX Trade Reconciliation Engine

Built for the line that appears almost word-for-word in forex Risk Analyst
and Trading Operations postings: **"Reconcile client funding and liaise
with Prime Brokers"** / **"Reconciliation, Reporting & Analytics."**

Takes two trade logs - the firm's own internal blotter and a Prime Broker's
statement of the same trading activity - matches them, and produces an
Excel report flagging every discrepancy, the same way this check runs at a
real brokerage every trading day.

## What it checks

- **Missing trades** - present on one side, absent on the other
- **Price breaks** - same trade, different fill price recorded
- **Volume breaks** - same trade, different size recorded
- **Timing breaks** - same trade, timestamps too far apart
- **Duplicate entries** - the same trade_id reported more than once on either side

All tolerances (price %, volume, and timing window) are configurable from the command line.

## Project structure

```
fx-trade-reconciliation/
  README.md
  requirements.txt
  main.py                       # CLI entry point
  src/
    generate_sample_data.py     # builds the two sample CSVs, with deliberate breaks injected
    reconcile.py                 # matching and classification logic
    report.py                    # builds the color-coded Excel report
  data/
    internal_blotter.csv         # generated
    prime_broker_statement.csv   # generated
  tests/
    test_reconcile.py
```

## Setup

```bash
pip install -r requirements.txt
```

## Generate sample data

Real broker data isn't available for a portfolio project, so this generates a
reproducible synthetic pair of files with a handful of breaks deliberately
injected (missing trades, price/volume/timing mismatches, a duplicate):

```bash
python src/generate_sample_data.py
```

## Run the reconciliation

```bash
python main.py
```

Produces `reconciliation_report.xlsx` with three sheets:

- **Summary** - counts by status
- **Trade Detail** - every trade, color-coded (green = matched, red = missing, amber = break)
- **Duplicates** - any trade_id reported more than once on either side

Custom tolerances:

```bash
python main.py --price-tolerance-pct 0.05 --volume-tolerance 0.01 --time-tolerance-minutes 10
```

## Test

```bash
pytest
```

Each test builds a small two-row fixture with a known, deliberate discrepancy
(a price 1.5% off, a timestamp 45 minutes apart, and so on) and checks it gets
classified correctly - the same logic that runs against the full sample data.

## What this demonstrates for the role

- The actual daily reconciliation workflow: extract, normalize, match, flag breaks, report
- Tolerance-based matching, since real trade records are rarely byte-identical between two systems
- An auditable output (the Excel report) suitable for a daily handover to a risk team

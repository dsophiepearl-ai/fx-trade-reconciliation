# FX Trade Reconciliation Engine

I built this to demonstrate one of the most literal responsibilities named in forex Risk Analyst and Trading Operations job postings: "reconcile client funding and liaise with Prime Brokers," and "reconciliation, reporting & analytics." It's a working simulation of the daily check a brokerage runs to confirm its own trade records agree with what the Prime Broker reports.

**Live demo:** https://fx-trade-reconciliation-7szvccrdwkpsdxkjtpbafa.streamlit.app/ — see "Seeing it run" below_

It runs as an interactive dashboard: generate a fresh set of sample trades (or upload your own two files), adjust the matching tolerances, and see the results as live metrics and a chart. The part that matters most, though, is how each discrepancy is shown: every break or missing trade is its own flagged card, expandable to the actual internal value vs. the Prime Broker value, the computed difference, and the tolerance it failed against — the same field-by-field reasoning an ops analyst would use to decide whether something is a real break or just normal noise between two systems. The same data is also available as an Excel report, downloadable at the bottom.

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
| Interactive dashboarding & data visualization | `src/dashboard.py` (Streamlit, Plotly) |
| Excel report generation with conditional formatting (openpyxl) | `src/report.py` |
| Designing reproducible test data with deliberate, known-answer breaks | `src/generate_sample_data.py` |
| Unit testing | `tests/test_reconcile.py` — 9 tests, all passing |
| Command-line tooling (argparse) | `main.py` |

## Tech stack

Python 3, pandas, Streamlit, Plotly, openpyxl

## Project structure

```
fx-trade-reconciliation/
  main.py                       # command-line entry point
  src/
    generate_sample_data.py     # builds sample data, with breaks deliberately injected
    reconcile.py                 # the matching and classification logic
    report.py                    # builds the color-coded Excel report
    dashboard.py                  # Streamlit UI
  data/
    internal_blotter.csv         # generated
    prime_broker_statement.csv   # generated
  tests/
    test_reconcile.py
  requirements.txt
```

## Seeing it run

Real Prime Broker data isn't something I have access to for a portfolio project, so I wrote a generator that builds a reproducible pair of files with specific breaks planted in them — that way both the tool and the test suite have a known answer to check against, the same way you'd validate any reconciliation logic before trusting it with real data.

**Try it now — no installation needed:** once the app above is deployed, click the live demo link at the top. In the sidebar, pick "Generate sample data" (or upload your own two CSVs), set the tolerances, and click **Run reconciliation** — the metrics and chart update immediately, and the Breaks and Missing tabs give you an expandable card per trade: internal value, Prime Broker value, the exact diff, and the tolerance it was measured against, so you can see *why* something was flagged, not just that it was. The Excel report is a click away as a download.

If you'd like to run it yourself instead:

```bash
git clone https://github.com/dsophiepearl-ai/fx-trade-reconciliation.git
cd fx-trade-reconciliation
pip install -r requirements.txt
streamlit run src/dashboard.py
```

There's also a plain command-line version for automation or scripting, which does the same reconciliation without the UI:

```bash
python src/generate_sample_data.py
python main.py --price-tolerance-pct 0.05 --volume-tolerance 0.01 --time-tolerance-minutes 10
```

## Deploying your own live version

Same process as any Streamlit app:

1. Push this repo to your own GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app**, select this repository, branch `main`, and file path `src/dashboard.py`
4. Click **Deploy**, then add the resulting link to the "Live demo" line at the top of this README

## Testing it

```bash
pytest
```

All 9 tests pass. Each one sets up a small, deliberate discrepancy — a price 1.5% off, a timestamp 45 minutes apart, a duplicate trade ID — and checks that the engine classifies it correctly. That's the same logic that runs against the full sample dataset.

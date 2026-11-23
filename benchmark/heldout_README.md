# Held-out benchmark (H01-H15)

`heldout.json`: 15 questions, same schema as `benchmark.json` (ids H01..H15). 5 single_fact, 5 multi_hop, 5 cross_filing; 2 abstain items (H05 COF FY2026 outside the filing, H15 Netflix not in the corpus). 17 tickers: GOOGL, CRM, MCD, C, COF, AMZN, BMY, ORCL, AXP, UNH, MA, PYPL, AMGN, ABT, COST, PG, META.

How derived
- Written from the page text in `data/parsed/{TICKER}.json` (`pages`) only. `src.query`, `results/`, the planner, graph output and `data/facts` were not opened. `benchmark.json` was read only for the field layout and to avoid repeating questions.
- Written BEFORE the planner/parser fixes that follow the first benchmark scores; not tuned to any system output. Every evidence `key` was checked to appear on its cited page (`tests/test_heldout.py`).
- Includes parser-hard cases: EPS (H02), negative equity in parentheses (H03), bank revenue labels (H04, H09), gross vs net capex (H06), capex printed negative (H08, H14).
- FY label follows D-043 (year of period end). `gold_value` is absolute USD, USD per share for EPS, or a fraction for ratios and growth. `verified: false` on all items.
- Known trap: Amazon's own free cash flow (p49) nets sales proceeds; H06 asks for the gross purchases line on p57.

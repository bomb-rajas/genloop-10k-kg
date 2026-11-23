# Fresh benchmark (F01-F15)

`fresh.json`: 15 questions, same schema as `heldout.json` (ids F01..F15). 5 single_fact, 5 multi_hop, 5 cross_filing; 2 abstain items (F05 Pfizer 2026 outside the filing, F13 Gilead Sciences not in the corpus). 16 tickers: AMZN, SBUX, INTC, GOOGL, PFE, MSFT, JNJ, NKE, META, HD, TGT, WMT, COST, MCD, BAC, C.

How derived
- Written from the page text in `data/parsed/{TICKER}.json` (`pages`) only. `src.query`, `src.evaluate`, `results/`, `src/planner.py`, `src/query.py`, `data/facts` and `graph/kg.json` were not opened. `heldout.json` and `benchmark.json` were read only for the field layout and to avoid repeating questions.
- Written AFTER the planner fixes (D-083, D-086) that used `heldout.json` failure categories, so `heldout.json` is now a dev set and this file is the genuinely unseen test. Not tuned to any system output. Code was not changed in response to its score.
- Every evidence `key` was checked to appear on its cited page (`tests/test_fresh.py`).
- Covers: possessives (Amazon's, Alphabet's, Johnson & Johnson's, McDonald's), short names (Citi), fiscal-year phrasing, banks, EPS, balance-sheet totals, R&D share, difference, share, growth, two-metric sum and ratio, "which generated/spent more", unknown company.
- `gold_value` is absolute USD, USD per share for EPS, or a fraction for ratios and growth. `verified: false` on all items; AI-drafted, not human verified.

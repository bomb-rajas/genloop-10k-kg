# Benchmark

`benchmark.json`: one benchmark of 59 questions (Q01-Q59) over Tech, Banks & Payments, Consumer & Retail and Healthcare filers: 20 single_fact, 20 multi_hop, 19 cross_filing. Every item is `verified: false`: gold was AI-drafted and AI-reviewed, not checked by a human.

How gold was made
- Read only from `data/parsed/{TICKER}.json` page text (1-based keys) and the statement tables printed there. Gold was not taken from `data/facts`, `data/entities`, `graph/` or any system output.
- Each figure is quoted in `evidence` as `{page, doc, key, quote}` (`doc` = `data/pdfs/{TICKER}.pdf`, the filing the page belongs to). `key` is the number or phrase that must appear on that page. `acceptable_pages` lists other pages that print the same figure.
- Derived values (ratios, sums, growth) show their inputs in `gold_answer`. `gold_value` is absolute USD, or a fraction for ratios.
- Fiscal year follows the year of the filing's period end (labels as printed in the PDF statement headers). Column order is checked per statement; AMZN and GOOGL list years ascending.
- Honest limit: Q30-Q44 and Q45-Q59 were written after earlier planner fixes, so the later questions are only partly independent of tuning.

Question types
- single_fact: one metric, one company, one fiscal year.
- multi_hop: needs a second step: ranking within a named set, a derived ratio, or a lookup linked from the ranked company (auditor, CFO, HQ city, segment).
- cross_filing: compares or ranks the same metric across 2-4 companies, or sums them.

Honest-failure items (`answerable: false`, `expected_behaviour: abstain`, `gold_value: null`): 7 in total, e.g. Q06 (BAC FY2026, outside the filing), Q10 (Visa R&D, no such line), Q20 (JPMorgan gross profit, not a bank metric).

Known limits: MRK total assets (Q08) has no label in the parsed text; the value 136,866 is checked by balance identity. BAC FY2025 total assets differ between p65 (3,411,738) and p68 (3,410,412); the cross-filing ranking does not depend on it.

Tests: `tests/test_benchmark.py` checks schema, counts, fact-id format, abstain fields and that every evidence key and quote appears on its cited parsed page. Scoring: `python -m src.evaluate` (writes `report/metrics.json`, `report/per_question.csv`).

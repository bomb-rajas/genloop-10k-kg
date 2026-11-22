# Benchmark (M7 draft)

`benchmark.json`: 29 questions (10 single_fact, 10 multi_hop, 9 cross_filing) over Tech, Banks & Payments, Consumer & Retail and Healthcare filers. Status: `verified: false` on every item until human review.

How gold was made
- Read only from `data/parsed/{TICKER}.json` page text (1-based keys) and the statement tables printed there. Gold was not taken from `data/facts`, `data/entities`, `graph/` or any system output.
- Each figure is quoted in `evidence` as `{page, key, quote}`. `key` is the number or phrase that must appear on that page.
- Derived values (ratios, sums, growth) show their inputs in `gold_answer`. `gold_value` is absolute USD, or a fraction for ratios.
- Fiscal year follows D-043: FY = year of the filing's period end (labels as printed in the PDF statement headers).
- Column order is checked per statement; AMZN and GOOGL list years ascending.

Question types
- single_fact: one metric, one company, one fiscal year.
- multi_hop: needs a second step: ranking within a named set, a derived ratio, or a lookup linked from the ranked company (auditor, CFO, HQ city, segment).
- cross_filing: compares or ranks the same metric across 2-4 companies, or sums them.

Honest-failure items (`answerable: false`, `expected_behaviour: abstain`, `answerable_by_graph: unknown`): Q06 (BAC FY2026, outside the filing), Q10 (Visa R&D, no such line), Q20 (JPMorgan gross profit, not a bank metric).

Known limits: MRK total assets (Q08) has no label in the parsed text; the value 136,866 is checked by balance identity. Pfizer FY2025 EPS (Q09) is present on p108 even though PROGRESS lists it as an extraction gap. BAC FY2025 total assets differ between p65 (3,411,738) and p68 (3,410,412); the cross-filing ranking does not depend on it.

Tests: `tests/test_benchmark.py` checks schema, counts, fact-id format, abstain fields and that every evidence key appears on its cited parsed page.

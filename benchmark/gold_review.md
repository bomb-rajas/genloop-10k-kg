# Gold review (AI, blind)

Date: Mon Nov 23 07:12 IST 2026. Decision D-081. `verified` stays false: a human still verifies.

Method: every gold value re-derived from data/parsed/{T}.json page text (PDF via pypdf where needed); ratios, sums
and growth recomputed. Blind: results/, src.query, src.evaluate, query/planner code and graph facts were not opened.
Done AFTER the first scores were published.

Result: 26 confirmed, 0 corrected, 3 ambiguous. No gold value, unit, FY label
(D-043), doc or page was proven wrong, so no original field changed. Added `acceptable_pages` (other pages of the same
filing that carry the value: primary statement, selected data, MD&A, notes) on 25 items, plus `review` and `ai_reviewed`.

| Q | Verdict | Pages added (`acceptable_pages`) | Corrections | Ambiguity / notes |
|---|---|---|---|---|
| Q01 | confirmed | AAPL: 39,41,59,76,77 | none | - |
| Q02 | confirmed | MSFT: 56,63,74,76,77,89 | none | - |
| Q03 | confirmed | NVDA: 53,57,104,105,106 | none | - |
| Q04 | confirmed | WMT: 56,109,110 | none | - |
| Q05 | confirmed | KO: 112,176 | none | - |
| Q06 | confirmed | - | none | - |
| Q07 | confirmed | JPM: 93,245,447 | none | - |
| Q08 | confirmed | - | none | - |
| Q09 | confirmed | PFE: 70,97 | none | - |
| Q10 | confirmed | - | none | - |
| Q11 | confirmed | AAPL: 39,41,59,76,77,50,53,54 | none | - |
| Q12 | confirmed | MSFT: 56,63,74,76,77,89,57,121,123 | none | - |
| Q13 | confirmed | AAPL: 76 | none | - |
| Q14 | ambiguous | AMZN: 41,50,101,102,55,56,107; AAPL: 49,39,41,59,76,77; MSFT: 73,56,57,121,123; GOOGL: 84,59,102,139 | none | Answer confirmed (AMZN 716,924 > AAPL 478,834 > GOOGL 402,836 > MSFT 331,839; EY auditor, /s/ on p56, ICFR report p107). Ambiguity: 'latest fiscal year' mixes FY2025 (AMZN, GOOGL) and FY2026 (AAPL, MSFT); ranking holds under either reading. Gold p54 is an index line; report pages 55-56 added. |
| Q15 | confirmed | JPM: 93,245,447,479 | none | - |
| Q16 | ambiguous | PEP: 78,118,123,51,198; PG: 38,69; KO: 108,83,131,191,193; MCD: 16,19,53,69 | none | Answer confirmed (PEP 93,925 FY2025 > PG 87,032 FY2026 > KO 47,941 > MCD 26,885); HQ Purchase NY on p1, also p51 and p198. Ambiguity: 'latest fiscal year' mixes FY2025/FY2026; ranking holds either way. |
| Q17 | confirmed | LLY: 59,76,79,117,66,82,85 | none | - |
| Q18 | confirmed | NVDA: 53,57,104,105,106 | none | - |
| Q19 | confirmed | META: 144,145,148,168,105,122,167,202 | none | - |
| Q20 | confirmed | - | none | - |
| Q21 | confirmed | JPM: 93,245,447; BAC: 62,158,168,295; C: 16,161,162 | none | resolved README note: BAC 3,410,412 is average total assets |
| Q22 | confirmed | MSFT: 56,63,89; AAPL: 59; NVDA: 53,86 | none | - |
| Q23 | confirmed | PFE: 81,193,195,198; ABBV: 72,76,165,167; LLY: 59,66,82,85,117 | none | - |
| Q24 | confirmed | NVDA: 53,57,104,105,106; MSFT: 56,57,121,123; AAPL: 39,41,59,76,77 | none | - |
| Q25 | ambiguous | AXP: 75,134; COF: 77,241; MA: 63,69,81,98,125 | none | Answer confirmed (AXP 72,229 > COF 53,434 > MA 32,791). Ambiguity: 'total revenue' definitions differ (AXP net of interest expense, COF total net revenue, MA net revenue); AXP also leads on gross (interest income 25,598 + non-interest revenues 54,865 vs COF 58,696 + 10,556). |
| Q26 | confirmed | MS: 71,187,342,348; GS: 139,263,454,456 | none | - |
| Q27 | confirmed | PEP: 78,118,123; KO: 83,131,191,193 | none | - |
| Q28 | confirmed | LLY: 59; ABBV: 65,111; PFE: 70,97 | none | - |
| Q29 | confirmed | AMZN: 41,50,101,102; GOOGL: 59,102,139; META: 105,122,144,167,202 | none | - |

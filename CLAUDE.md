# CLAUDE.md

## 1. Intro map
- Genloop SEC 10-K knowledge-graph QA: a fact graph built from the latest 10-K of 40 companies (4 sectors x 10), queried by graph traversal; every answer cites doc and page.
- handoff.md is the spec (companies, schema, folders, risks). GOAL.md holds milestones and "Done when" and wins on any conflict.
- Main folders: config/ (companies, metrics), src/ (pipeline), data/ (pdfs, parsed, facts, xbrl), graph/, benchmark/, results/, docs/, report/ (results PDF only).

## 2. Where things live
| You need | File or folder | Status |
|---|---|---|
| Milestones and Done-when | GOAL.md | exists |
| Spec: companies, schema, risks | handoff.md | exists |
| Project memory | CLAUDE.md | M0 |
| Every design decision | docs/decision-log.md | M0 |
| Milestone status and open issues | PROGRESS.md | M0 |
| API keys, User-Agent (gitignored) | .env (template: .env.example) | exists |
| Company list | config/companies.yaml | M1 done |
| Metric list and synonyms | config/metrics.yaml | M1 done |
| Paths, load_env, config loaders | src/config.py | M1 done |
| LLM call (Groq, Gemini, cache, retries) | src/llm.py: complete(prompt, system, json_mode) | M1 done |
| EDGAR download, HTML to PDF, XBRL fetch | src/download.py: python -m src.download [--tickers] | M2 done |
| Filing index (accession, dates, status, financials_page) | data/filings.json | M2 done |
| Raw HTML (gitignored) | data/raw_html/ | M2 done |
| 10-K PDFs (gitignored, except report/) | data/pdfs/ | M2 done (40) |
| XBRL companyfacts (gitignored, ~175 MB, D-040) | data/xbrl/ | M2 done |
| pdfplumber text and tables per page; statement rows | src/parse.py: python -m src.parse [--tickers] [--force]; src/tables.py (pure helpers); output data/parsed/{T}.json | M3 done, 40 of 40 have 3 statements and scale (D-050 to D-052) |
| Numeric facts from statement rows (PDF only) | src/extract.py: python -m src.extract [--tickers]; output data/facts/{T}.json (admitted), {T}.rejected.json | M4a done (D-054 to D-063); 976 of 976 XBRL compared matched, 0 rejected |
| XBRL validation gate (validator only, never a value source) | src/validate.py | M4a done (D-060, D-063); tests/test_extract.py, tests/test_validate.py (118 pytest total) |
| LLM disk cache (committed, read before key check) | data/llm_cache/ | M1 done |
| Graph build | src/build_graph.py, output graph/kg.json | M5 planned |
| Query planner, traversal, abstain | src/query.py | M6 planned |
| Benchmark questions | benchmark/benchmark.json | M7 planned |
| Scoring and metrics | src/evaluate.py, output results/metrics.json, results/predictions.jsonl | M8 planned |
| Unit tests (pytest) | tests/ (test_config.py, test_download.py, test_tables.py, test_parse.py, test_extract.py, test_validate.py) | M3 done; M4a adds extract and validate (118 total) |
| README | README.md | M9 planned |
| Results PDF | report/results.pdf | M9 planned |
| Pipeline doc | docs/flow.md | M10 planned |

## 3. Failure log
- Never git-add .env or *.pdf outside report/.
- Quote SEC_USER_AGENT in .env (contains spaces).
- M2: matching "consolidated balance sheet" alone hit index pages and missed MSFT "BALANCE SHEETS"; now "balance sheet" AND "total assets" (D-039).
- M3: first parse run missed JNJ (company-name title prefix), WMT net income ("Consolidated net income") and MSFT CF ("Net cash from operations"); fixed by D-045 rules.
- M3: second run missed 13 companies (singular titles, title on the page before the data, Merck with no "Total assets" label, unit line on the next page, glued "$"); fixed by D-050 and D-051.
- M4a: CapEx sign: cash-flow outflows are negative in the PDF while XBRL is positive, so CapEx uses absolute: true (D-057), not by loosening tolerance. HD and TGT fiscal labels shifted years: per-statement shift (D-058). EPS regex escaping ('\\b' in YAML single quotes) let share counts through; fixed by a single backslash in metrics.yaml (D-055).
- M2: first financials rule (D-039) missed V, TGT, MRK. D-042 rule now marks all 40 ok but AXP p96, C p190, MRK p150, MCD p31 are not statements. M3 statement parser (D-045) does not select those pages; the D-042 download rule is unchanged.

## 4. Decision-log rule
Every meaningful design or build choice gets an entry in docs/decision-log.md in the same change, before moving on. That covers architecture, schema, fact-ID format, metric mapping, libraries, parsing rules, extraction approach, LLM prompts and output schemas, validation thresholds, benchmark design, scoring rules, and company swaps. Failures are logged only when they forced a decision. If you chose between options, log it, including choices made by subagents.

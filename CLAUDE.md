# CLAUDE.md

## 1. Intro map
- Genloop SEC 10-K knowledge-graph QA: a fact graph built from the latest 10-K of 40 companies (4 sectors x 10), queried by graph traversal; every answer cites doc and page.
- Pipeline: download -> parse -> extract -> validate (XBRL gate, never a value source) -> graph -> planner/query -> evaluate.
- Rules: never edit a gold answer/value/page in benchmark/; no commits unless asked; quote SEC_USER_AGENT in .env (has spaces); never git-add .env.
- Decision ids like D-057 in code comments are historical; the log itself is gone.

## 2. Where things live
| You need | File or folder |
|---|---|
| API keys, User-Agent (gitignored) | .env (template: .env.example) |
| Companies, metrics and synonyms | config/companies.yaml, config/metrics.yaml |
| Paths, load_env, config loaders (REPORT_DIR = metrics folder) | src/config.py |
| LLM call (Groq, Gemini, disk cache data/llm_cache/ recreated on demand) | src/llm.py |
| EDGAR download, HTML to PDF, XBRL | src/download.py -> data/pdfs, data/xbrl, data/filings.json |
| Page text and statement rows | src/parse.py, src/tables.py -> data/parsed/{T}.json |
| Numeric facts, XBRL validation | src/extract.py, src/validate.py -> data/facts/{T}.json |
| Entities (segments, auditor, people, HQ) | src/entities.py -> data/entities/ |
| Graph build and helpers | src/graph.py (alias src/build_graph.py) -> graph/kg.json |
| Planner, traversal, abstain | src/planner.py, src/query.py (`python -m src.query "q" [--json]`) |
| Benchmark (29 questions, verified:false) | benchmark/benchmark.json, benchmark/README.md |
| Scoring | `python -m src.evaluate` -> report/metrics.json, report/per_question.csv |
| Results PDF | results/results.pdf (built by scripts/make_report.py) |
| Knowledge graph views | kg-visualization/ (scripts/render_kg.py, scripts/explorer_template.html) |
| Tests | tests/ (`.venv/bin/python -m pytest -q`) |

## 3. Failure log
- CapEx sign: cash-flow outflows are negative in the PDF, XBRL positive; CapEx uses `absolute: true`, not looser tolerance.
- Statement finders: match "balance sheet" AND "total assets"; company-name title prefixes, singular titles, titles on the preceding page and glued "$" each broke a parser run before being handled.
- EPS regex in metrics.yaml needs a single backslash in YAML single quotes.
- XBRL gate must compare the same measure (net income excl. NCI, equity excl. NCI).
- Per-statement fiscal-year shift (HD, TGT) and header years after the report year (MRK) are handled in src/extract.py.

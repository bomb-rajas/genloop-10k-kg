# Decision log

Times are IST. Seeded entries (D-001 to D-021) were recorded in M0 at 2026-11-23 03:01 IST; handoff.md gives no original decision times. Entries are never deleted; they are superseded.

## Decisions at a glance

| ID | Stage | Decision | Chosen | One-line why |
|---|---|---|---|---|
| D-001 | M0 | Filing type | Latest 10-K (FY2025 label; see D-043) | 10-Qs have 3- and 9-month columns, misaligned quarters, fewer facts |
| D-002 | M0 | Company universe | 40 companies, 10 per sector (Tech, Banks & Payments, Consumer & Retail, Healthcare) | Banks included for sector-specific metrics |
| D-003 | M0 | Company swap | WFC replaced by COF | WFC financials sit in Exhibit 13 |
| D-004 | M0 | Document source | EDGAR HTML converted to PDF with headless Chrome | Consistent page numbers for citations |
| D-005 | M0 | Parsing input | PDF-only parsing; HTML parsing deferred | Task rule; any HTML fallback needs user approval |
| D-006 | M0 | PDF parser | pdfplumber for per-page text and tables | Tables with page numbers, no GPU |
| D-007 | M0 | Answer method | KGQA over graph traversal, not vector RAG | Task requires graph-sourced answers |
| D-008 | M0 | Schema | Fact-centric: Fact nodes with value, unit, period, doc, page, validated | Per-value provenance and validation |
| D-009 | M0 | Metric naming | Metric nodes with synonym lists | Maps question wording to canonical metrics |
| D-010 | M0 | Derived metrics | COMPUTED_FROM edges between Metric nodes | Derived values stay traceable to inputs |
| D-011 | M0 | Graph store | NetworkX, saved as JSON | Kùzu/Cypher skipped for time |
| D-012 | M0 | LLM provider | Gemini primary, Groq fallback | Superseded by D-013 |
| D-013 | M0 | LLM provider | Groq primary (openai/gpt-oss-120b), Gemini secondary | Gemini returns 404/503; gpt-oss-120b works on Groq |
| D-014 | M0 | Planner fallback | Rule-based fallback planner; Groq-only with no further fallback, Gemini kept as optional second provider in the wrapper (Groq -> Gemini -> rules) | Free-tier quota limits |
| D-015 | M0 | Cost and compute | Free LLMs only; no paid API, no GPU | Task constraints; reproducibility |
| D-016 | M0 | XBRL role | Validation gate only, never an answer source | PDF-only answer rule |
| D-017 | M0 | Fact IDs | IDs like AAPL\|Revenue\|FY2025 are the gold supporting facts | Exact set comparison for precision and recall |
| D-018 | M0 | Benchmark gold | Written from PDF pages, not graph output | Avoids circular evaluation |
| D-019 | M0 | Metric scope | 12 non-bank metrics, 6 bank metrics (lists below) | Bank revenue semantics differ |
| D-020 | M0 | Rollout | 5-company slice (AAPL, JPM, WMT, JNJ, MSFT) before all 40 | Find failures cheaply before quota and time are spent |
| D-021 | M0 | Git workflow | Commit after each milestone; user pushes | Reviewable history; user controls the remote |
| D-022 | M1 | CIK source and fiscal year end | CIKs from SEC company_tickers.json; fiscal_year_end only for fixed calendar year-ends | Fixed-date FYs are exact; 52/53-week FYs cannot be stated as one date |
| D-023 | M1 | Sector labels | Tech, Banks, Consumer, Healthcare (short names in companies.yaml) | Matches the sector enum in GOAL/handoff spec |
| D-024 | M1 | Payments company treatment | V, MA, PYPL are is_bank: false (non-bank metrics) | Payments are not lenders; bank metric list does not fit them |
| D-025 | M1 | Metric scope encoding | applies_to all|nonbank; bank list = applies_to all (6); derived section with formula and computed_from | Keeps 12 non-bank and 6 bank metrics in one file |
| D-026 | M1 | Synonym policy | Lowercase, generous as-reported labels; generic labels (basic, diluted, research, gross margin) left out | Generic labels match ratios or other lines and would mis-map facts |
| D-027 | M1 | LLM provider chain | Groq (openai/gpt-oss-120b) then Gemini; LLM_PROVIDER=groq|gemini forces one provider | Follows D-013; env override needed for tests and offline runs |
| D-028 | M1 | Gemini model id | gemini-flash-latest, constant in src/llm.py | gemini-2.5-flash returned 404 (D-013 evidence) |
| D-029 | M1 | LLM cache key | sha256 of JSON {system, prompt, json_mode}; provider-independent | Same prompt reuses cache across providers; json_mode on/off must not collide |
| D-030 | M1 | LLM cache location and read order | data/llm_cache/<sha256>.json, committed; read before any key check | Evaluate re-runs from cache without an API key |
| D-031 | M1 | Retry policy | 3 retries on 429/500/502/503/504, backoff 2/4/8 s, 120 s timeout; then next provider | Free-tier 429s are expected; values are implementer choices |
| D-032 | M1 | Module layout | src/config.py (paths, load_env, loaders), src/llm.py, tests/test_config.py | Single source of paths and env; one wrapper for all LLM calls |
| D-033 | M1 | requirements.txt | requests, python-dotenv, pyyaml, pdfplumber, networkx, pytest; unpinned | Smallest set the milestones need; pinning deferred until a reproducibility need appears |
| D-034 | M1 | .gitignore PDF rule | Ignore *.pdf except report/*.pdf | Raw SEC PDFs are large and reproducible; the report PDF is a deliverable |
| D-035 | M1 | Committed LLM cache | data/llm_cache/ is committed, not ignored | Evaluation reruns need no API key (see D-030) |
| D-036 | M2 | Latest 10-K selection | Max filingDate among form == "10-K"; 10-K/A and 10-Q excluded | Amendments are partial; the original 10-K is the filing the spec names (see D-001) |
| D-037 | M2 | SEC throttle and retries | Min 0.2 s between requests (<=5 req/s); retry 429/500/502/503/504 with backoff 2/4/8 s; 120 s timeout | Stays under the 5 req/s cap; same retry values as D-031 |
| D-038 | M2 | Chrome HTML-to-PDF flags | --headless=new --disable-gpu --no-pdf-header-footer --no-first-run --no-default-browser-check --virtual-time-budget=30000; fresh temp profile per file; 180 s timeout | Same conversion every run keeps page numbers stable; cover text verified clean |
| D-039 | M2 | Financials presence check | Superseded by D-042 | Phrase rule hit index pages and missed V, TGT, MRK |
| D-040 | M2 | XBRL committed or ignored | data/xbrl/*.json gitignored; .gitkeep stays tracked | Measured ~175 MB for 40 companies, above the 50 MB limit |
| D-041 | M2 | filings.json schema | Single file: {ticker: {accession, filing_date, report_date, url, form, pdf, status, financials_page}}; status ok, no_financials, or "error: msg"; written after each company | One index file as the spec asks; status feeds the M3 skip logic |
| D-042 | M2 | Financials presence check (revised) | First page after the first 15% with "total assets" AND ("total liabilities" or "total equity" or "shareholders" or "stockholders"); else no_financials | Phrase rule missed V, TGT, MRK. Current rule still has false hits (see entry) |
| D-043 | M2 | Fiscal-year label | FY = fiscal year of report_date; fact IDs use period-end FY | Filings are the latest 10-K as of run date, not FY2025 |

## Full entries

### D-001
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which SEC filing to use per company?
- Chosen: Latest 10-K (FY2025) per company.
- Why: 10-Qs bring 3- and 9-month columns, quarter misalignment, and fewer facts.
- Rejected: 10-Q filings: messy periods and fewer facts (see Why).
- Evidence: none measured; reasoning from handoff.md.
- Outcome: TBD (M8)
- Status: active

### D-002
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which companies, and how many?
- Chosen: 40 companies, 10 per sector: Tech (AAPL, MSFT, GOOGL, AMZN, META, NVDA, ORCL, CRM, ADBE, INTC); Banks & Payments (JPM, BAC, C, COF, GS, MS, V, MA, AXP, PYPL); Consumer & Retail (WMT, COST, TGT, HD, PG, KO, PEP, MCD, NKE, SBUX); Healthcare (JNJ, PFE, MRK, ABBV, LLY, UNH, AMGN, BMY, ABT, CVS).
- Why: Banks are included on purpose (sector-specific metrics). Mixed fiscal-year ends are on purpose (AAPL Sept, MSFT June, WMT/NVDA Jan); the period end date is stored and the FY rule is stated.
- Rejected: Fewer or Tech-only companies: sector-specific metrics would not be tested.
- Evidence: none; list from handoff.md.
- Outcome: TBD (M8)
- Status: active

### D-003
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: evidence
- Decision: Keep Wells Fargo?
- Chosen: Replace WFC with COF.
- Why: WFC's financials sit in Exhibit 13, which the PDF-only pipeline would have to fetch separately.
- Rejected: Keeping WFC and fetching Exhibit 13: extra parsing scope before M3.
- Evidence: Exhibit 13 finding recorded in handoff.md. Other banks still need the same check (open).
- Outcome: TBD (M8)
- Status: active

### D-004
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: How to get the 10-K documents?
- Chosen: The download script fetches EDGAR HTML and converts it to PDF with headless Chrome, so page numbers are consistent. The user does not download by hand.
- Why: Citations need stable page numbers; EDGAR serves HTML only.
- Rejected: Parsing HTML directly: breaks the PDF-only rule (see D-005).
- Evidence: none.
- Outcome: n/a
- Status: active

### D-005
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Where do facts come from?
- Chosen: PDF-only parsing. All text, tables and facts come from the PDFs. HTML fallback deferred.
- Why: Task requirement. EDGAR HTML is used only to produce the PDFs.
- Rejected: HTML parsing as primary or fallback: needs the user's approval (GOAL.md).
- Evidence: none.
- Outcome: n/a
- Status: active

### D-006
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which PDF library?
- Chosen: pdfplumber for per-page text and tables.
- Why: Gives page-level text and table extraction with no LLM or GPU.
- Rejected: Other PDF table tools were not evaluated; none recorded in handoff.md.
- Evidence: none yet; to be checked in M3 (table edge-case tests).
- Outcome: TBD (M8)
- Status: active

### D-007
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Retrieval style for answering questions?
- Chosen: Knowledge-graph QA: question to plan to graph traversal to answer with fact IDs and doc+page.
- Why: The task requires answers from the graph with sources; graph structure does the work.
- Rejected: Vector RAG over chunks: the task rules out answers from vector search.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-008
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Graph schema shape?
- Chosen: Fact-centric. Fact nodes carry value, unit, scale, as-reported label, doc, page, snippet, extraction method and validated flag, linked to Company, Metric, Period and Filing.
- Why: Each value keeps its own provenance and validation status.
- Rejected: Metric values as properties on Company nodes: no per-value provenance or validation flag.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-009
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: How are metric names matched?
- Chosen: Metric nodes with canonical name and synonym list in config/metrics.yaml.
- Why: Questions use varied wording; one canonical node per metric.
- Rejected: Matching raw as-reported labels only: labels vary by company.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-010
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: How are derived metrics (e.g. NetMargin) stored?
- Chosen: COMPUTED_FROM edges between Metric nodes.
- Why: The derivation stays visible in the graph and traceable to inputs.
- Rejected: Storing derived values as extra facts: they would duplicate inputs and have no source page.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-011
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which graph store?
- Chosen: NetworkX, saved as graph/kg.json.
- Why: Pure Python, no server, the JSON file can be committed for reviewers.
- Rejected: Kùzu/Cypher and Neo4j: considered, skipped for time (handoff.md).
- Evidence: none.
- Outcome: n/a
- Status: active

### D-012
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which LLM is primary?
- Chosen: Gemini free tier as primary, Groq as fallback, behind a switchable wrapper (.env).
- Why: Planned in handoff.md before the API key was tested.
- Rejected: n/a at the time.
- Evidence: Superseded (see D-013): Gemini key returns 404/503.
- Outcome: n/a
- Status: superseded by D-013

### D-013
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: evidence
- Decision: Which LLM is primary, given the key tests?
- Chosen: Groq as primary (model openai/gpt-oss-120b); Gemini as secondary. Replaces the Gemini-primary plan in D-012.
- Why: The Gemini key fails on generateContent. Groq llama-3.3-70b-versatile is unavailable, but gpt-oss-120b works.
- Rejected: Gemini primary: 404 and 503 on generateContent. llama-3.3-70b-versatile on Groq: unavailable.
- Evidence: gemini-2.5-flash returns 404 "no longer available to new users"; gemini-flash-latest returns 503; Groq llama-3.3-70b-versatile unavailable; Groq openai/gpt-oss-120b works.
- Outcome: TBD (M8)
- Status: active

### D-014
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: What does query planning do when the LLM is unavailable or over quota?
- Chosen: Rule-based fallback planner. Groq is the only LLM the planner calls.
- Why: Free-tier quota limits (handoff.md risk: cache, Groq fallback, rule-based question parser).
- Rejected: Groq-only with no further fallback (Gemini kept as optional second provider in wrapper: Groq -> Gemini -> rules).
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-015
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Paid services or GPU?
- Chosen: Free LLM tiers only; no paid API and no GPU in the pipeline.
- Why: Task constraints and reproducibility. Claude Pro is billed separately from the Claude API; Claude Code is used only to build the project.
- Rejected: Paid APIs and GPU-based local models: violate the constraints; Ollama is not installed.
- Evidence: none.
- Outcome: n/a
- Status: active

### D-016
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: What role does XBRL play?
- Chosen: Validation gate only. XBRL companyfacts check extracted facts before the validated flag is set. Never an answer source. Tolerance and thresholds to be logged in M4.
- Why: PDF-only answer rule (GOAL.md).
- Rejected: XBRL as an answer source: breaks the PDF-only rule. Skipping validation: no accuracy check.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-017
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: How are gold supporting facts identified?
- Chosen: Fact IDs of the form TICKER|Metric|FYyyyy (example AAPL|Revenue|FY2025). The same IDs are the gold supporting facts.
- Why: Precision and recall become an exact set comparison.
- Rejected: Fuzzy snippet matching: not scorable exactly.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-018
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Where do benchmark gold answers come from?
- Chosen: Written from the PDF pages, not from graph output. Gold is verified by the user after 08:00 IST.
- Why: Avoids circular evaluation.
- Rejected: Generating gold from the graph: circular.
- Evidence: none yet.
- Outcome: TBD (M8)
- Status: active

### D-019
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Which metrics are in scope?
- Chosen: 12 non-bank metrics: Revenue, GrossProfit, OperatingIncome, NetIncome, EPS, TotalAssets, TotalLiabilities, Equity, OperatingCashFlow, CapEx, R&D, Cash. 6 bank metrics: Revenue, NetIncome, EPS, TotalAssets, TotalLiabilities, Equity.
- Why: Bank revenue has different semantics, so banks get their own list; the list covers what 10-Ks report consistently.
- Rejected: Free-form metric discovery: outside the scoped list.
- Evidence: none.
- Outcome: TBD (M8)
- Status: active

### D-020
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: How far to run before scaling to 40?
- Chosen: Run the full pipeline on a 5-company slice (AAPL, JPM, WMT, JNJ, MSFT) before scaling.
- Why: Parser and extraction failures show up cheaply, before quota and time are spent on 40 companies.
- Rejected: Running all 40 first: late failure discovery and quota burn.
- Evidence: none yet.
- Outcome: n/a
- Status: active

### D-021
- Time: 2026-11-23 03:01 IST
- Stage: M0
- Trigger: planned
- Decision: Commit and push cadence?
- Chosen: Commit after each milestone. The user pushes.
- Why: Reviewable history; the user controls the remote (GOAL.md).
- Rejected: One commit at the end: hard to review. Claude pushing: the user pushes.
- Evidence: none.
- Outcome: n/a
- Status: active

### D-022
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: Where do CIKs come from and what goes in fiscal_year_end?
- Chosen: CIKs from https://www.sec.gov/files/company_tickers.json (fetched 2026-11-23 with SEC_USER_AGENT). fiscal_year_end stored only for fixed calendar year-ends (MM-DD). Omitted for 52/53-week years: AAPL, NVDA, ADBE, INTC, COST, TGT, HD, SBUX, JNJ, PEP. Names are short display names.
- Why: Fixed-date year-ends are exact; a 52/53-week year has no single date and would be wrong.
- Rejected: Storing approximate dates (AAPL last Saturday of Sept as 09-30); fetching from EDGAR at build time (config must be static).
- Evidence: All 40 tickers resolved to CIKs (no misses).
- Outcome: n/a
- Status: active
### D-023
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: Sector label values?
- Chosen: Tech, Banks, Consumer, Healthcare.
- Why: Matches the enum in GOAL.md; the long handoff headings (Banks & Payments) are only documentation.
- Rejected: Long labels in YAML: more quoting, no gain.
- Evidence: Test asserts 4 sectors x 10 companies.
- Outcome: n/a
- Status: active
### D-024
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: evidence
- Decision: How to treat payments companies (V, MA, PYPL)?
- Chosen: is_bank: false, so they get the non-bank metric list.
- Why: Payments companies report gross profit and operating income like other businesses; the bank list would drop those.
- Rejected: is_bank: true: loses GrossProfit and OperatingIncome for three companies.
- Evidence: Test asserts bank flags = JPM, BAC, C, COF, GS, MS, AXP.
- Outcome: TBD (M8)
- Status: active
### D-025
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: How is metric scope encoded in metrics.yaml?
- Chosen: Each metric has applies_to (all or nonbank). The bank list is the applies_to: all subset (6 metrics). Derived metrics sit in a separate derived list with computed_from and formula.
- Why: One file holds both lists; the subset is computed, not duplicated.
- Rejected: Two separate metric files: duplicated Revenue/NetIncome definitions.
- Evidence: Test asserts 12 metrics, bank subset equals the 6 bank metrics, derived = NetMargin, GrossMargin.
- Outcome: TBD (M8)
- Status: active
### D-026
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: How generous should synonyms be?
- Chosen: Lowercase as-reported labels, many variants per metric. Generic labels (basic, diluted, research, gross margin, sales alone for EPS) are left out.
- Why: Generic labels match ratios or other lines and would mis-map facts.
- Rejected: Including every generic word: false matches.
- Evidence: none yet; checked in M3/M4 extraction.
- Outcome: TBD (M8)
- Status: active
### D-027
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: evidence
- Decision: Provider order and override?
- Chosen: Groq (openai/gpt-oss-120b) first, Gemini second. LLM_PROVIDER=groq or gemini forces one provider. A provider with no key is skipped.
- Why: D-013 found Groq works and Gemini fails; Groq is primary.
- Rejected: Gemini first: 404/503 per D-013.
- Evidence: Smoke call (one prompt, Groq) returned 'pong'. Cache file written to data/llm_cache/.
- Outcome: TBD (M8)
- Status: active
### D-028
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: evidence
- Decision: Which Gemini model id?
- Chosen: gemini-flash-latest, set as GEMINI_MODEL constant in src/llm.py.
- Why: gemini-2.5-flash returns 404 for new users (D-013); flash-latest alias avoids a pinned id.
- Rejected: gemini-2.5-flash: 404. Gemini 503 seen on gemini-flash-latest in D-013 test, so Gemini is secondary only.
- Evidence: Not exercised (no Gemini key in .env).
- Outcome: TBD (M8)
- Status: active
### D-029
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: What goes into the LLM cache key?
- Chosen: sha256 of JSON {system, prompt, json_mode} with sort_keys. Same key for every provider.
- Why: Cache hits should not depend on the provider. json_mode is in the key so a json and a plain reply for the same prompt do not collide (implementer choice, not from GOAL.md).
- Rejected: Including provider or model in the key: a Gemini answer would not hit a Groq cache entry.
- Evidence: test_cache_key_differs_by_system_and_json_mode in tests/test_config.py; pytest 6 passed.
- Outcome: TBD (M8).
- Status: active
### D-030
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: Where is the LLM cache and when is it read?
- Chosen: data/llm_cache/<sha256>.json (not gitignored, so it is committed). Read before any key check.
- Why: evaluate.py must rerun from cache with no key (GOAL.md Done when).
- Rejected: Cache in data/ gitignored: evaluation would need a key.
- Evidence: Test: cache hit with all keys unset and requests.post raising.
- Outcome: TBD (M8)
- Status: active
### D-031
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: Retry and timeout policy?
- Chosen: Retries on 429, 500, 502, 503, 504: 3 retries, backoff 2, 4, 8 s, timeout 120 s. Then the next provider.
- Why: Free-tier 429s and 503s are expected. The x3 retry was requested in the M1 brief; the backoff values are implementer choices.
- Rejected: No retry: fails whole run on one 429. Unlimited retry: stalls.
- Evidence: Not exercised beyond the smoke call.
- Outcome: TBD (M8)
- Status: active
### D-032
- Time: 2026-11-23 03:04 IST
- Stage: M1
- Trigger: planned
- Decision: Module layout for M1?
- Chosen: src/config.py holds paths, load_env, load_companies, load_metrics. src/llm.py holds complete(). tests/test_config.py holds config and cache tests. src/__init__.py is empty.
- Why: One place for paths and env; one wrapper for all LLM calls.
- Rejected: Config in each module: duplicated paths.
- Evidence: pytest: 6 passed.
- Outcome: n/a
- Status: active

### D-033
- Time: 2026-11-23 03:10 IST
- Stage: M1
- Trigger: planned
- Decision: Which libraries go in requirements.txt, and are they pinned?
- Chosen: requests (HTTP for SEC and LLM calls), python-dotenv (.env loading), pyyaml (config files), pdfplumber, networkx, pytest. No version pins.
- Why: Smallest set the milestones need. requests is used directly instead of an SDK; that avoids a dependency per provider.
- Rejected: Groq or Google SDKs: extra dependencies for two REST calls. Pinned versions: deferred.
- Evidence: .venv installed from requirements.txt; pytest 6 passed.
- Outcome: TBD (M8). Revisit pins if a rerun breaks.
- Status: active

### D-034
- Time: 2026-11-23 03:10 IST
- Stage: M1
- Trigger: planned
- Decision: Which PDFs are tracked by git?
- Chosen: .gitignore ignores *.pdf, with !report/*.pdf so the report PDF is tracked. Also ignores .env, data/raw_html/, data/pdfs/, __pycache__/, .venv/.
- Why: Source SEC PDFs are large and can be regenerated from EDGAR; the report PDF is a deliverable.
- Rejected: Committing source PDFs: repo bloat, and they are reproducible.
- Evidence: .gitignore content as written.
- Outcome: n/a
- Status: active

### D-035
- Time: 2026-11-23 03:10 IST
- Stage: M1
- Trigger: planned
- Decision: Is the LLM cache committed?
- Chosen: data/llm_cache/ is committed (not in .gitignore). Cache files are read before any API key check.
- Why: Evaluation reruns complete from cache without GROQ_API_KEY or GEMINI_API_KEY.
- Rejected: Ignoring the cache: every evaluation rerun would need live keys and quota.
- Evidence: Cache-hit test in tests/test_config.py runs with no key.
- Outcome: TBD (M8).
- Status: active

### D-036
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: planned
- Decision: Which 10-K filing is downloaded for each company?
- Chosen: Among submissions entries with form == "10-K", the one with the max filingDate. 10-K/A and 10-Q are excluded.
- Why: Amendments are partial documents and lack the full financial statements. Filing dates are used as the "latest" test, not reportDate.
- Rejected: Including 10-K/A (partial). Choosing by reportDate (ambiguous across amendments).
- Evidence: tests/test_download.py latest_10k tests skip amendments and 10-Q. Full run: 40 companies, all found a 10-K. Most filing dates fall in 2026 (AAPL 2026-11-03, MSFT 2026-07-29), so "latest" is as of the run date, not FY2025.
- Outcome: Refines D-001's fiscal-year label to "latest as of run date". Review D-001 if the label matters in M8.
- Status: active

### D-037
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: planned
- Decision: How are SEC requests paced and retried?
- Chosen: Minimum 0.2 s between requests (<=5 req/s, a shared Throttle in src/download.py). Retries on 429/500/502/503/504 with backoff 2/4/8 s; 120 s timeout.
- Why: The task asked for at most 5 req/s. Retry values match the LLM policy (D-031) so the project has one retry shape.
- Rejected: Parallel downloads: no need at this volume, and it risks the SEC rate limit.
- Evidence: Slice run (5 companies) and full 40-company run completed with 0 network failures.
- Outcome: n/a
- Status: active

### D-038
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: planned
- Decision: How is the HTML converted to PDF?
- Chosen: Headless Chrome with --headless=new --disable-gpu --no-pdf-header-footer --no-first-run --no-default-browser-check --virtual-time-budget=30000 --print-to-pdf. Each conversion uses a fresh temp --user-data-dir. Timeout 180 s. Output is written to a temp file then replaced.
- Why: The same flags on every run give stable page numbers, which M3 and the answer citations depend on. The virtual time budget lets the inline-XBRL page finish rendering.
- Rejected: Default header/footer: adds page-number text that pollutes the parse. Shared profile: state leaks between runs.
- Evidence: Page 1 of AAPL, MSFT, JPM, WMT, JNJ reads as the 10-K cover ("UNITED STATES / SEC / FORM 10-K"); no XML text. pdfplumber prints FontBBox warnings, which are noise.
- Outcome: n/a
- Status: active

### D-039
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: "consolidated balance sheet" check hit index pages (AAPL p48, JPM p77, WMT p70, JNJ p50, MSFT p78) and missed MSFT's "BALANCE SHEETS" title (p75).
- Decision: How is the financial statements page detected, and what happens when none is found?
- Chosen: A page counts when it contains "balance sheet" AND "total assets" (case-insensitive). The first match is stored as financials_page. No match sets status "no_financials". No company is substituted.
- Why: Requiring the table line (total assets) skips cross-reference and index pages. Substituting another filing would change the company set the spec fixes.
- Rejected: Phrase alone (wrong pages). Substituting companies: the spec fixes the 40 names; the user asked for flags, not swaps.
- Evidence: Corrected results for the 5 slice companies: AAPL p51, MSFT p75, JPM p79, WMT p54, JNJ p51. Full run flagged V, TGT and MRK as no_financials (Exhibit 13 or a non-standard layout is likely; not verified). AXP (p20) and C (p16) have early hits that may be summary tables; not verified.
- Outcome: Open: V, TGT, MRK need a manual look before M3 (see PROGRESS.md). The check is a presence test, not a proof that the page is the statement.
- Status: active

### D-040
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: planned
- Decision: Is data/xbrl/ committed to git?
- Chosen: data/xbrl/*.json is in .gitignore. data/xbrl/.gitkeep is still tracked. Files regenerate with python -m src.download.
- Why: Measured sizes: JPM 8.15 MB, MSFT 4.94 MB, JNJ 4.22 MB, AAPL 3.86 MB, WMT 3.77 MB (5 files, 24 MB). Full 40-company total is 175 MB, above the 50 MB limit set in the task.
- Rejected: Committing (repo bloat beyond the 50 MB rule). Trimming the JSON: changes source data.
- Evidence: du -ch data/xbrl/*.json = 175M after the full run.
- Outcome: n/a
- Status: active

### D-041
- Time: 2026-11-23 03:20 IST
- Stage: M2
- Trigger: planned
- Decision: What is the data/filings.json schema?
- Chosen: One file, {ticker: {accession, filing_date, report_date, url, form, pdf, status, financials_page}}. status is ok, no_financials, or "error: <msg>". The file is written after each company. A company is skipped when its status is ok or no_financials and its PDF exists.
- Why: The task asked for a single index file. Writing after each company keeps progress if a run is interrupted.
- Rejected: One JSON per ticker: the task said single file. Skipping on error status: a failed company must be retried.
- Evidence: Full run: ok=37, no_financials=3 (V, TGT, MRK), failed=0. 40 PDFs in data/pdfs. Total PDFs 242 MB, raw HTML 176 MB, both gitignored.
- Outcome: n/a
- Status: active

### D-042
- Time: 2026-11-23 03:45 IST
- Stage: M2
- Trigger: Failure: D-039 rule (page has "balance sheet" AND "total assets") gave no hit for V, TGT and MRK. Those 10-Ks have statements under "Statements of Financial Position" or no "balance sheet" heading on the page.
- Decision: Change the financials check to: first page after the first 15% of pages (int(n*0.15) skipped; covers selected-data and MD&A summaries) containing "total assets" AND one of "total liabilities", "total equity", "shareholders", "stockholders".
- Chosen: is_balance_sheet in src/download.py as above; FIN_SKIP_FRAC = 0.15; financials_page and find_financials_page share the skip rule. Test: tests/test_download.py test_financials_page_needs_total_assets_with_equity_line_and_skips_first_15_percent.
- Why: The title is not a reliable marker; the table lines are. Skipping the first 15% removes most summary tables.
- Rejected: "total liabilities and" as the only line (not yet tested across all 40; a scan was stopped before it finished). Heading-based rules (titles vary: BALANCE SHEETS, Statements of Financial Position).
- Evidence: Re-evaluated all 40 from existing PDFs (no redownload). Changed: AMGN 144 to 111, AXP 20 to 96, C 16 to 190, GS 169 to 130, MCD 55 to 31, MRK none to 150, TGT none to 49, V none to 95, WMT 54 to 77. Hit-page check: V p95 and TGT p49 are real statements (Assets block, Statements of Financial Position). WMT p77 is the Consolidated Balance Sheets. FAILURE: AXP p96 is regulatory capital ratios (not a balance sheet); C p190 is a discontinued-operations note; MRK p150 is a fair-value note; MCD p31 is MD&A text. The new rule matches these pages because they contain "total assets" and an equity/liabilities word.
- Outcome: Open. 4 of 40 hits are not the balance sheet (AXP, C, MRK, MCD, plus any other changed entry not checked). data/filings.json currently shows all 40 ok with these pages. Next: tighten the rule (for example require "total liabilities and" on the same page, or a statement title in the first 300 characters) and re-check. Not fixed in this change per coordinator instruction.
- Status: active

### D-043
- Time: 2026-11-23 03:45 IST
- Stage: M2
- Trigger: Coordinator note: the D-001 "FY2025" label does not match the data downloaded.
- Decision: The fiscal-year label is the fiscal year of report_date. Fact IDs use the fiscal year of the period end.
- Chosen: FY label = year of report_date. Examples: V report_date 2026-09-30 gives FY2026; AAPL 2026-09-26 gives FY2026; MRK, AXP, C 2025-12-31 give FY2025; TGT 2026-01-31 gives FY2026 by this rule.
- Why: The download takes the latest 10-K as of the run date (2026-11-23), so most filings are FY2026 (see D-036). The label must follow the data.
- Rejected: Keeping "FY2025" from D-001 (wrong for most companies).
- Evidence: filings.json report_date values for AAPL, V, TGT, MRK, AXP, C.
- Outcome: Caveat: TGT's year ended 2026-01-31 is called fiscal 2025 by Target. The rule gives FY2026. Confirm the label convention before M4 fact IDs are fixed.
- Status: active

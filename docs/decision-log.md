# Decision log

Times are IST. Seeded entries (D-001 to D-021) were recorded in M0 at 2026-11-23 03:01 IST; handoff.md gives no original decision times. Entries are never deleted; they are superseded.

## Decisions at a glance

| ID | Stage | Decision | Chosen | One-line why |
|---|---|---|---|---|
| D-001 | M0 | Filing type | Latest 10-K (FY2025) | 10-Qs have 3- and 9-month columns, misaligned quarters, fewer facts |
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
| D-014 | M0 | Planner fallback | Rule-based fallback planner; Groq is the only LLM the planner calls | Free-tier quota limits |
| D-015 | M0 | Cost and compute | Free LLMs only; no paid API, no GPU | Task constraints; reproducibility |
| D-016 | M0 | XBRL role | Validation gate only, never an answer source | PDF-only answer rule |
| D-017 | M0 | Fact IDs | IDs like AAPL\|Revenue\|FY2025 are the gold supporting facts | Exact set comparison for precision and recall |
| D-018 | M0 | Benchmark gold | Written from PDF pages, not graph output | Avoids circular evaluation |
| D-019 | M0 | Metric scope | 12 non-bank metrics, 6 bank metrics (lists below) | Bank revenue semantics differ |
| D-020 | M0 | Rollout | 5-company slice (AAPL, JPM, WMT, JNJ, MSFT) before all 40 | Find failures cheaply before quota and time are spent |
| D-021 | M0 | Git workflow | Commit after each milestone; user pushes | Reviewable history; user controls the remote |

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
- Rejected: Groq-only with no further fallback (Gemini kept as optional second provider in the LLM wrapper, chain Groq -> Gemini -> rules; clarified by orchestrator, no user input needed).
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

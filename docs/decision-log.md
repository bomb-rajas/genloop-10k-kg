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
| D-044 | M3 | PDF text library and table path | pdfplumber page text is primary (text-line parser in src/tables.py); pdfplumber extract_tables only for a statement page with fewer than 5 text rows | Statement tables have no ruling lines; text lines were stable on 5 pilot companies |
| D-045 | M3 | Statement page classification (superseded by D-050) | Title is the end of one of the first 8 lines (company-name prefix allowed, TOC lines excluded); page needs a key row with >=2 values (IS net income, BS total assets, CF operating activities) and >=10 two-value rows; up to 2 continuation pages | Titles vary (JNJ, MSFT, WMT, JPM); text search alone hit MD&A and notes. Resolves D-042 outcome |
| D-046 | M3 | Scale rule (amended by D-051) | Scale from the statement header (text above first line item), then the whole primary page; None when absent, never assumed | Units differ by company (in millions, thousands, Dollars in Millions) |
| D-047 | M3 | Year columns (note-column part amended by D-053) | columns = unique years in the header; newest_col = index of max year; values kept as reported, note-number leading column dropped | Newest-first is common but not guaranteed; index makes it explicit |
| D-048 | M3 | Output format and run mode | data/parsed/{T}.json; pages text for all pages keyed by 1-based page; Pool(4) with imap_unordered; skip existing unless --force | Idempotent reruns; 40 companies in minutes |
| D-049 | M3 | Commit or ignore parsed JSON | Committed: 20 MB total, under the 60 MB limit | Spec limit; the page text is the source for later citations |
| D-050 | M3 | Title and classification rules for the 13 failures | Title anywhere in the first 8 cleaned lines (Table of Contents and ImageNN.jpg stripped); singular and bank titles (statement of cash flow, balance sheet, statement of financial condition); title on the page before a data page; TOC lines ending in a page number and condensed or parent-company statements skipped; BS key row also "total liabilities"; CF key row also "by/from operations" | Failures were titles and key rows, not missing pages (see D-050 entry) |
| D-051 | M3 | Scale and year source across statement pages; glued dollar | Scale and years searched over the header of all statement pages, then the full pages; SCALE_RE accepts "(Millions, except" and "(MILLIONS"; "$" split from "(19,669)$" | Title page often has no unit line (V, AXP, TGT, PFE) |
| D-053 | M3 | Note-column rule, atomic write, cache guard | Drop a leading note column only when most value rows in the statement have width+1 values with a small integer first value (not per row); JSON written to .json.tmp then replaced; unreadable cached JSON treated as missing (PDF parsed instead) | Per-row drop could strip a real column from one odd row; partial writes could corrupt reuse |
| D-052 | M3 | Re-run mode | --reuse-pages rebuilds statements from page text already in data/parsed (no PDF reopen); --force still re-parses | 40 companies rebuilt in 3 s; PDF text unchanged |
| D-054 | M4 | Multi-year extraction | Each statement contributes its year columns: IS and CF up to 3 years, BS up to 2 | Prior-year facts are still filings' own values; 3 IS years cover the comparative columns |
| D-055 | M4 | Label matching tiers | Normalise (lowercase, drop parentheticals, punctuation to space); exact synonym, then label_regex, then prefix of a multi-word synonym whose remainder has no exclude word, then fallback_labels exact and prefix | Exact first avoids prefix false hits; generic exclude words (margin, growth, change, percent, ratio, before, and) and per-metric exclude stop 'net income' matching 'net income per share' |
| D-056 | M4 | Identity fallback | TotalLiabilities = TotalLiabilitiesAndEquity - Equity, TotalAssets = TotalLiabilitiesAndEquity (helper_metrics); method 'identity' | Merck and ABT balance sheets have no 'Total liabilities' label, but the parsed rows still show equity and the combined total |
| D-057 | M4 | CapEx sign | CapEx absolute: true, stored as abs(raw) x scale | Cash-flow outflows are printed negative in the PDF; XBRL PaymentsToAcquire... is positive; rejects in the first run came from this |
| D-058 | M4 | Fiscal-year labelling per statement | shift = report year - max header year <= report year; fiscal_year = header + shift (period-end year, D-043); window newest - N < year <= newest | HD and TGT print the company's fiscal label (HD '2025' ends 2026-02-01); a company-wide shift broke balance sheets, so it is per statement |
| D-059 | M4 | Layout normalisation | infer_header takes the year row (>=2 years 1990-2100) as columns; columns after the newest year dropped when rows match the kept width; interleaved % columns collapsed to values[0::2] unless the label has per/share | Parser misreads: PG header row, MRK 2026 column, CRM and HD % columns; per-share rows must not be collapsed (HD EPS row) |
| D-060 | M4 | XBRL gate semantics | Candidates: own-accession 10-K FY entries, else all 10-K FY; flow needs a 350-380 day span; balance is instant; end date within 7 days of the fiscal-year anchor; match if any candidate within TOLERANCE=0.005 relative (EPS 0.005 absolute); mismatch rejected to {T}.rejected.json; no candidate admitted as no_xbrl; identity check and sanity logged only | The gate validates; XBRL never supplies a value. Reject-not-admit keeps wrong numbers out of the graph; no_xbrl keeps coverage |
| D-061 | M4 | Revenue exclude 'non' | Revenue exclude list adds 'non' | 'Total non-interest revenues' is a sub-total and was taken as total revenue; rejects 9 to 6 (AXP still wrong; fixed by D-063) |
| D-062 | M3 | Statement page selection (audited statements) | A title counts only as a heading (short company-name prefix, no MD&A word such as overview, analysis, summary, expressed, information); a page is a statement only if is_statement_layout: fewer than 3 percent-value lines, no %/percent/change/increase/decrease in the header, fewer than 3 rows with 5+ values; '(Continued)' bank pages are continuations even when the title repeats; EPS label '^diluted earnings$' and NetIncome 'Citigroup s net income' style label added to metrics.yaml | NVDA MD&A percent table, C segment and overview pages, JPM/BAC/COF/MS/AXP MD&A pages won selection; the rules are generic (no ticker special case), and the label additions cover BAC 'Diluted earnings' and C 'Citigroup's net income' rows |
| D-063 | M4 | XBRL tag and label fixes | Revenue xbrl_tags adds RevenuesNetOfInterestExpense (AXP); Equity and TotalLiabilitiesAndEquity regex accept 'deficit' and 'investment' (SBUX, TGT) | AXP PDF 72229 equals the RevenuesNetOfInterestExpense FY2025 value in data/xbrl/AXP.json, so the PDF was right and the gate lacked the tag; 0 rejects, 1004 admitted, match 976/976 |
| D-064 | M4 | Concept-matching XBRL tags | Each metric validates only against XBRL concepts that measure the same thing: NetIncome NetIncomeLoss only (not ProfitLoss); Equity StockholdersEquity only; CapEx, R&D, Cash drop secondary tags; EPS diluted tag, basic rows validated against EarningsPerShareBasic (basic_xbrl_tags) | Wrong concepts passed as validated: MS NetIncome 17,025 (incl. NCI) matched ProfitLoss; INTC/KO/C/MS Equity matched total equity incl. NCI; 13 Equity, 3 NetIncome, 3 JNJ R&D matched only a secondary tag |
| D-065 | M4 | Parent-attributable row preference | NetIncome prefers 'attributable to' rows, and 'applicable to' (not 'applicable to common', which sits after preferred dividends); Equity prefers 'Total <X> stockholders equity' and 'equity attributable to' rows; NCI-inclusive totals only as fallback_labels; TotalLiabilities identity uses TotalEquityInclNCI | Parent-row rules fix MS, INTC, KO, C; the NCI-inclusive fallback is validated against the parent-only tag and rejects or stays no_xbrl if it disagrees |
| D-066 | M4 | Sanity blocks admission | validate.gate rejects a fact that fails sanity_ok (reason 'sanity: ...'); the count is in stats['rejected'] | A value that fails sanity is wrong by definition and should not reach the graph; logged-only would let it in |
| D-067 | M4 | Identity fallback details | identity_check skips identity-derived TotalAssets as well as TotalLiabilities; identity values are rounded to int like direct facts; identity TotalLiabilities is gated against the XBRL Liabilities tag like any fact (no_xbrl when absent) | Identity inputs are circular and cannot validate each other; rounding keeps the value type consistent |
| D-068 | M4 | JNJ R&D concept | R&D xbrl_tags adds ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost (JNJ prints R&D excluding IPR&D impairments) | Same concept for JNJ's presentation; primary ResearchAndDevelopmentExpense holds a different value (109 for FY2025) |
| D-069 | M4 | Groq rate limit | Sliding 60 s token budget (GROQ_TPM, default 6000) checked before each attempt; 429 waits the server hint (cap 60 s), 4 retries, then Gemini | Free-tier 429s during entity runs; chars/4 estimate needs no tokenizer |
| D-070 | M4 | Groq reasoning effort | reasoning_effort 'low' for openai/gpt-oss-120b | Fewer reasoning tokens per call; API accepted it (HTTP 200) |
| D-071 | M4 | Gemini fallback model | gemini-3.1-flash-lite, serial with 6 s gap, 3 retries on 429/5xx | gemini-flash-latest 503s; concurrent calls hit 429 (supersedes model id in D-028) |
| D-072 | M7 | Benchmark design | 29 questions, gold from PDF page text only; 3 abstain items; facts/graph not opened | Independent gold; system output never used to choose or tune items |
| D-073 | M5 | Graph schema | MultiDiGraph in graph/kg.json: Company, Sector, Metric, Filing, Period, Fact, entity nodes; Fact ids TICKER\|Metric\|FYyyyy; derived metrics as COMPUTED_FROM edges, no stored values | Traceable provenance (doc, page, snippet) on every Fact; derived values computed at query time (M6) |
| D-074 | M5 | Module name | src/graph.py holds the code; src/build_graph.py is a 3-line shim | User asked for src/graph.py; GOAL.md Done-when says python -m src.build_graph |
| D-075 | M6 | Query planner/executor | Rule planner first, LLM only on rule failure (validated); strict abstain; newest-FY default | Cheap, deterministic, no hallucinated ids; wrong answers cost more than abstains |
| D-076 | M6 | Verifier fixes (planner/query) | Bare 'cash flow' alias dropped; cash-flow text without 'operating' abstains unsupported_metric; growth regex `grow\w*`; rank rows print each company's FY | Verifier found 'free cash flow yield' answered OperatingCashFlow, 'grew' read as level; mixed FYs flagged but unnamed in text |
| D-077 | M4b | Entity extraction design | Literal grounding: name or employee number must appear on a cited page of data/parsed/{T}.json (case/space-normalised); ids PERSON\|T\|slug, SEG\|T\|slug, LOC\|slug, ORG\|slug; Employees Fact {T}\|Employees\|FY{year} unvalidated; one LLM call per category on located pages | Entities auditable against page text, no outside knowledge; Employees have no XBRL tag to check against |
| D-078 | M4b | Gate fixes and regate | Boundary-aware literal match ("166,000" not in "1,166,000"); Employees as_written must give employee_count; snippet on every grounded path; exchange org ids merged (ORG\|nasdaq); --regate replays cache only | Verifier findings; regate re-applies gate with no LLM calls and prompt/cache keys unchanged |
| D-079 | M8 | Evaluation scoring | Numeric within 0.5% of gold (USD may be x1e3..1e9 scaled; '%' /100); text gold = non-fact gold_fact_ids terms, matched in answer text or graph company name, names normalised (suffixes dropped); abstain-expected correct only if abstained; fact P/R on gold fact ids only, abstain-expected gold empty (P=1 if nothing returned, R=1); value-correct with page miss = wrong_page (correct stays value-based); no checkable gold = unscored | Gold stays unchanged; failure categories show where the system loses points; no tuning on benchmark. Partly superseded by D-080 (scorer amended after the first run). |
| D-080 | M8 | Scorer amendment | Numeric gold judged on structured value; text fallback only for non-numeric values; Q15 unscored, no P/R | Verifier found scorer bugs; first run 19/28 -> 20/28; gold not edited |
| D-081 | M8 | Gold review (AI, blind) | 29 Qs re-derived from page text after first scores, blind to system output: 26 confirmed, 0 corrected, 3 ambiguous (Q14, Q16, Q25); added acceptable_pages (25 Qs), review, ai_reviewed; verified stays false; page check accepts pages or acceptable_pages pairs | Gold listed one page per value; no gold value wrong; page_strict_rate only, not rerun |
| D-082 | M8 | Held-out benchmark | benchmark/heldout.json H01-H15, gold from PDF page text only, written before planner/parser fixes, verified false | Independence from the system and from Q01-Q29 |
| D-083 | M6/M8 | Generic planner, executor, scorer, cache fixes | 'total' sums only without a comparison cue (higher/more/which...); bare first-word company aliases (amazon); qualified metrics (current, dividend, return on, pretax, cost of) abstain unsupported_metric; two named years for one company return both; 'president' is a word match excluding vice president; scorer credits only the winner of a which-is-higher answer and ignores bare years; corrupt LLM cache file = miss, atomic write | Found by read-only audit; fixed generically, no benchmark tuning, tests/test_planner_fixes.py |
| D-084 | M4 | Parser gap fixes | EPS heading prefix, unlabelled totals, bank revenue identity; PDF-only, XBRL validates | 1004 -> 1029 admitted, 962/962 XBRL |
| D-085 | M9 | Pre-submission cleanup | accuracy_over_all (correct/n) and *_excl_abstain metrics; evidence `doc` fields; README/report/GOAL aligned to final numbers | Task rule is correct / total; docs were stale |
| D-086 | M6/M7 | Planner/executor intents + AXP OCF | New `difference` intent (A-B, two metrics or two companies) and `share` op (Y/X as %); growth cue beats 'total'; 'generated/spent/had more' rank; unknown capitalised company abstains unknown_company; OperatingCashFlow applies_to all + 'used for' synonyms | Generic gaps from audit; AXP and 6 other banks lacked OCF (+21 facts), XBRL 983/983 |

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

### D-044
- Time: 2026-11-23 03:48 IST
- Stage: M3
- Trigger: planned (GOAL M3); statement tables have no ruling lines on the pages checked.
- Decision: Which PDF text path to use for statement rows?
- Chosen: pdfplumber page.extract_text() for every page. Rows come from src/tables.py parse_text_lines (label then trailing numeric tokens). pdfplumber extract_tables is used only for a statement page whose text gives fewer than 5 rows (TABLE_FALLBACK_BELOW). rows_from_table joins cells first so split '$' and ')' cells merge.
- Why: Text lines carry the label and all values on one line; table detection finds nothing useful on unruled pages.
- Rejected: extract_tables as primary (unruled pages, split cells). HTML parsing (D-005). Camelot or other libraries (not installed; D-033 keeps requirements minimal).
- Evidence: AAPL p51 BS: text gives 28 rows with values, Total assets [404548, 359241].  Not compared against extract_tables output (fallback used only on pages with fewer than 5 text rows).
- Outcome: Good on AAPL, JPM, WMT, JNJ, MSFT and most of the 40. Labels can carry footnote letters, e.g. JPM "Total assets(a)" (kept, not stripped).
- Status: active

### D-045
- Time: 2026-11-23 03:52 IST
- Stage: M3
- Note (2026-11-23 04:01): superseded by D-050 (title, key-row and continuation rules) and D-053 (note-column rule). The text below is the first version.
- Trigger: Failure in first run: JNJ found no statements (titles prefixed by company name, e.g. "Johnson & Johnson and subsidiaries consolidated statements of earnings"); WMT IS missed (net income labelled "Consolidated net income"); MSFT CF missed ("Net cash from operations") and MSFT BS absorbed the cash flow page as a continuation.
- Decision: Classify a statement page by title, key row and density, with continuation pages.
- Chosen: TITLES match the end of a line in the first 8 non-empty lines (regex with (?:^|\s) prefix and \s*$ suffix). KEY_ROWS: income_statement r"\bnet\s+(income|earnings|\(loss\)|loss)\b" (rows with "per" excluded); balance_sheet r"^total\s+assets\b"; cash_flow_statement r"operating\s+activities|net\s+cash\s+.*\boperations\b"; each needs >=2 values. Page needs >=10 rows with >=2 values (MIN_VALUE_ROWS). Continuation: up to 2 following pages that are not any statement, have no "notes to", "statements of", "balance sheet", "comprehensive" in the page title lines, and no "statement(s)" or "balance sheet" in the first 3 lines, and have >=3 rows with rows/non-empty lines >=0.3. Table of contents lines (title then a page number) do not match because the title must end the line.
- Why: Title-only and phrase-only rules hit MD&A and notes (see D-042 evidence). Density and key rows separate statements from prose.
- Rejected: Title in first line only (JNJ and MSFT put a name or heading first). "cash flows" as a continuation stop word (would reject data rows that start with cash flow labels). Fixed page numbers per company (not portable).
- Evidence: After fix: AAPL IS p49, BS p51, CF p54. JPM IS p243, BS p245, CF p248. WMT IS p75, BS p77, CF p79. JNJ IS p52, BS p51, CF pp55-56. MSFT IS p73, BS p75, CF p76. Full run: none of the D-042 false hits (AXP p96, C p190, MRK p150, MCD p31) is a classified statement page (checked in data/parsed JSON page lists). Full-40 run: 27 of 40 have all 3 statements with a scale; 13 lack something (see PROGRESS.md M3).
- Outcome: Resolves the D-042 open outcome for the statement pages (the D-042 financials_page rule in download.py is unchanged). Still open: 13 companies lack a statement; see PROGRESS.md M3.
- Status: active

### D-046
- Time: 2026-11-23 03:52 IST
- Stage: M3
- Trigger: planned; units differ by company (In millions, in thousands, Amounts in millions, Dollars in Millions).
- Decision: How is the statement scale found?
- Chosen: src/tables.py find_scale(text) with SCALE_RE "(in|amounts in|dollars in) (dollars|units|thousands|millions|billions)" (case-insensitive) mapped to 1, 1e3, 1e6, 1e9 (dollars and units = 1). Searched in header_text (the lines above the first line item), then the whole primary page. Stored as scale plus scale_source_text. None when absent; the caller must not assume a scale.
- Why: The unit line sits in the statement header, so the search stays off the data.
- Rejected: Assuming millions (the default in most filings), which the task forbids. Reading scale from MD&A text (wrong page).
- Evidence: 5-company run: AAPL, JPM, WMT, JNJ, MSFT all got a scale from the header.
- Outcome: Values are stored as reported, not multiplied. Scaling is left to M4 fact extraction.
- Status: active

### D-047
- Time: 2026-11-23 03:52 IST
- Stage: M3
- Trigger: planned; period headers differ (Dec 31, 2025 Dec 31, 2024 / 2025 2024 2023 / Year Ended June 30, 2026 2025 2024).
- Decision: How are year columns chosen?
- Chosen: columns = unique 4-digit years in header_text in order (extract_years). newest_col = pick_year_column(header) = index of the maximum year (None if no year). A row whose value count is one more than the column count and whose first value is an integer <=99 has that leading note-reference value dropped. Header rows (dates, all-year rows) are dropped from rows.
- Why: Newest-first is common but not guaranteed, so the index is stored explicitly. Note-reference columns (e.g. "Note 2") would otherwise shift values.
- Rejected: Assuming columns are newest-first. Keeping note columns (shifts values).
- Evidence: AAPL columns [2026,2025,2024] newest_col 0; MSFT [2026,2025,2024]; JNJ [2025,2024,2023].
- Outcome: The note-column rule has no test on a real note column yet (none found in the 5 pilot companies). Check in M4.
- Status: active

### D-048
- Time: 2026-11-23 03:52 IST
- Stage: M3
- Trigger: planned (M3 spec: per-company output, parallel, idempotent).
- Decision: Output format and run mode for src/parse.py.
- Chosen: data/parsed/{T}.json = {ticker, n_pages, pages:{"1":text,...}, statements:{income_statement|balance_sheet|cash_flow_statement: {pages, scale, scale_source_text, columns, newest_col, rows:[{label, values, page}]}}}. multiprocessing Pool(4), imap_unordered, one worker per company; per-company progress print; skip when the JSON exists unless --force; a worker exception is caught and printed (one bad PDF does not stop the batch). pdfplumber is opened once per company.
- Why: Keeps the JSON self-contained for citations (page text is stored). Four workers match the spec and the machine; the 40-company run took 255 s wall time.
- Rejected: Per-page JSON files (more files, no gain). A process per statement (more overhead).
- Evidence: 5 pilot companies: 5 files in 42 s wall time with Pool(4), JPM (479 pages) took 41 s.
- Outcome: Done. Run prints per-company progress and a lacking-statements table.
- Status: active

### D-049
- Time: 2026-11-23 03:53 IST
- Stage: M3
- Trigger: Spec: parsed JSON committed if total <60 MB, else gitignore the page text.
- Decision: Commit data/parsed/*.json or ignore it?
- Chosen: To be committed with the code (no git commit made in M3). data/parsed/*.json totals 20 MB for 40 companies (under 60 MB); page text kept in the JSON.
- Why: The spec limit. Page text is needed to show citations without re-running the PDF step.
- Rejected: Ignoring it by default (reruns need the PDFs, which are gitignored anyway).
- Evidence: du of data/parsed after the 40-company run (recorded in PROGRESS.md).
- Outcome: 20.4 MB measured (du -sk 20424). To be committed with the code, as the spec allows.
- Status: active

### D-050
- Time: 2026-11-23 03:57 IST
- Stage: M3
- Trigger: Coordinator m00204 loop 1: 13 of 40 companies lacked a statement or scale.
- Decision: Supersedes D-045 classification rules (title, key row, continuation). Title may sit anywhere in the first 8 cleaned lines and may be on the page before the data page; TOC and condensed or parent-only statements are excluded; BS key row adds "total liabilities" (Merck has no "Total assets" label); CF key row adds "by/from operations" (Nike, McDonald's).
- Chosen: General rules in src/parse.py (TITLES, TITLE_SKIP, KEY_ROWS, find_statements). No per-ticker override was needed.
- Why: Diagnosis from stored JSON: titles had company prefix or "Table of Contents"/"ImageNN.jpg" headers (MS, JNJ); singular titles (C, MS, MCD, NKE, ABT, PFE); title-only page followed by data page (GS CF p269 to p270, META CF p147 to p148, V BS p94 to p95, V IS p96 to p97, SBUX CF p75 to p76); condensed parent-only pages (C p340, GS p482) must not win.
- Rejected: Per-ticker page overrides in config/ (not needed after general rules); widening key rows to any number-only line (would hit MD&A tables).
- Evidence: After the rules, 40 of 40 have IS, BS, CF pages (reuse-pages run, data/parsed rebuilt). tests/test_parse.py covers title variants, TOC skip, condensed skip, key rows, previous-page title, continuation.
- Outcome: 0 of 40 lacking a statement. Key values still blank for some (see PROGRESS.md).
- Status: active

### D-051
- Time: 2026-11-23 03:57 IST
- Stage: M3
- Trigger: V, AXP, TGT, PFE had no scale; C CF key row was glued "(67,632)$ (19,669)$".
- Decision: Supersedes the D-046 search order. Scale and year columns come from the header of every statement page (title page often has no unit line), then the full pages. SCALE_RE also matches "(Millions," and "(MILLIONS,". parse_line inserts a space before "$" in glued tokens.
- Chosen: Regex extended in src/tables.py, search widened in src/parse.py build_statement.
- Why: Unit line sits on the page after the title (V, AXP, TGT); Citigroup prints "$" glued to the preceding number.
- Rejected: Assuming scale 1e6 when absent (D-046 forbids it).
- Evidence: test_find_scale_parenthesised_units and test_parse_line_glued_dollar_splits in tests/test_parse.py; 0 of 40 lack scale after rebuild.
- Outcome: All 40 scale = 1e6 from the reuse-pages run (scale_source_text kept per statement).
- Status: active

### D-052
- Time: 2026-11-23 03:57 IST
- Stage: M3
- Trigger: Iterating on rules without re-reading 40 PDFs.
- Decision: Add --reuse-pages: rebuild statements from pages already in data/parsed/{T}.json. --force still re-parses from the PDF.
- Chosen: run_company(ticker, force, reuse_pages); parse_pdf(ticker, cached) takes cached page text.
- Why: Page text is the cached source; reopening PDFs for a rule change wastes time.
- Rejected: Always re-reading PDFs (slower, same result).
- Evidence: 40 companies rebuilt in 3 s (log).
- Outcome: Used for loop 1.
- Status: active

### D-053
- Time: 2026-11-23 04:01 IST
- Stage: M3
- Trigger: Ponytail review (coordinator): the per-row note-column drop in build_statement could strip a real value from one odd row; the JSON write was not atomic; unreadable cached JSON crashed reuse.
- Decision: Drop a leading note column only when a clear majority (more than half) of the statement's value rows (>=2 values) have width+1 values and a small integer first value. Write data/parsed/{T}.json via a .json.tmp file then replace. Read cached JSON with _read_cached; an unreadable file is treated as missing and the PDF is parsed. Removed the duplicate pages[0] search in the scale fallback.
- Chosen: build_statement collects page rows first, decides note_col once per statement; run_company uses _read_cached and atomic replace.
- Why: Per-row drops are unstable; a single stray row should not change the statement. A partial write would leave a broken JSON that reuse would then trip on.
- Rejected: Keeping the per-row rule (one odd row loses its first value); a lock file for writes (single process per company, so replace is enough).
- Evidence: tests/test_parse.py: test_build_statement_drops_majority_note_column, test_build_statement_keeps_values_when_note_column_is_minority, test_build_statement_too_narrow_header_keeps_all_values, test_run_company_writes_atomic_json_and_skips_unreadable_cache, test_read_cached_returns_none_when_unreadable. Rebuild of 40 with --reuse-pages --force: 0 of 40 lacking statements or scale; pytest 95 passed.
- Outcome: Applied. Values for the 40 are unchanged in the spot-check labels (Total assets, net income, revenue) because the note rule still drops the leading column when most rows have it.
- Status: active

### D-054
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: M4a asked for all year columns of each statement, not only the newest filed year.
- Decision: STATEMENT_YEARS = IS 3, CF 3, BS 2. Each statement's columns within the window newest - N < year + shift <= newest yield one fact per metric per year.
- Chosen: extract_company loops years_of(statement) and creates one fact per year column.
- Why: Prior-year values from the same filing are the reported values for those years and fill coverage.
- Rejected: Only the newest column (loses prior-year facts); older 10-K filings (out of scope, D-001).
- Evidence: Output sample AAPL Revenue FY2026, FY2025, FY2024 in data/facts/AAPL.json; tests/test_extract.py::test_scale_and_column_years_and_absolute_capex (FY2025 and FY2023 checked).
- Outcome: 991 candidate facts across 40 companies before the gate (run at 04:12 IST).
- Status: active

### D-055
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: Label matching needed to handle footnotes, prefix collisions and known M3 label gaps (WMT 'Consolidated net income', COF/KO/NKE revenue, JNJ 'Sales to customers').
- Decision: norm() lowercases, drops parentheticals and punctuation. match_row tries exact synonym, then label_regex, then prefix of a multi-word synonym (remainder must not contain GENERIC_EXCLUDE or metric exclude words), then fallback_labels exact and prefix. Regex hits respect the metric exclude list only (not the generic list).
- Chosen: Only full-width rows (values count == column count) are candidates; first hit in statement order.
- Why: Exact first avoids prefix collisions; generic exclude words stop 'net income margin' and 'net income per share' matches; regex carries spelling variants such as 'purchases of property, plant and equipment'.
- Rejected: Per-ticker label maps (general synonyms only); fuzzy matching (not reproducible).
- Evidence: tests/test_extract.py: test_norm_strips_footnotes_and_punctuation, test_exact_synonym_beats_prefix, test_prefix_rejected_by_exclusion_word, test_prefix_match_with_plain_remainder, test_fallback_label_used_when_no_synonym, test_regex_tier_for_revenue_and_eps_exclusions.
- Outcome: Revenue, NetIncome, EPS coverage in the Missing list (below). Bug found and fixed in this step: the regex tier had ignored exclusions (Total cost of revenues matched) and then the generic list wrongly blocked 'plant and equipment'.
- Status: active

### D-056
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: M3 notes: MRK has no 'Total assets' label; ABT total assets and liabilities are unlabelled.
- Decision: metrics.yaml gets helper_metrics (TotalLiabilitiesAndEquity) and identity {plus, minus} for TotalAssets and TotalLiabilities. Identity runs only when no direct row exists; value = sum(plus) - sum(minus) per year column; method 'identity'; snippet lists the inputs.
- Chosen: Identity facts carry the first plus row's page and label.
- Why: The identity is exact accounting, so a derived value is still PDF-only (no XBRL value used).
- Rejected: Taking the XBRL Assets value as a fallback (forbidden: XBRL is validator only).
- Evidence: tests/test_extract.py::test_identity_fallback_total_liabilities. Identity check (TA vs TL + Eq) runs on 54 balance pairs at 04:16 IST: 2 fail (UNH, logged only; likely redeemable NCI, not an extraction error).
- Supersedes: D-062 outcome line 'Identity fallback covers ABT now' was wrong. ABT and MRK totals are not identity-derivable from the parsed rows (the parser returns no total-assets row and no TLAE row for ABT).
- Outcome (04:16 IST): 22 identity facts, all TotalLiabilities, ALL 22 xbrl_status no_xbrl (admitted unvalidated, since the filer has no XBRL Liabilities tag). The 976/976 match count does not include them. TGT is one of them (TLAE regex fix, D-063). TotalAssets has no identity facts. MRK and ABT stay unresolved: MRK TotalAssets/TotalLiabilities and ABT TotalAssets/TotalLiabilities are still missing (the parser does not return their balance-sheet totals, so the identity inputs are absent; not fixed here, parser-owned). TotalLiabilities XBRL: 54/54 matched, 22 no_xbrl.
- Status: active
- Outcome (M8, 2026-11-23): M8 scoring: 4 answerable benchmark items lost to missing facts in the graph (MRK TotalAssets Q08, PFE EPS Q09 and Q28, COF Revenue Q25); these were not fixed in M8.

### D-057
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: First 5-company run: 6 rejected facts, all CapEx (MSFT 'Additions to property and equipment' (115,948)).
- Decision: metrics.yaml CapEx has absolute: true; extract applies abs() to the value.
- Chosen: Sign normalised only for CapEx; all other metrics keep the reported sign.
- Why: Root cause was sign convention: cash-flow outflows are printed negative in the PDF; XBRL PaymentsToAcquire... is positive. Fixing the rule, not the tolerance.
- Rejected: Loosening the tolerance or allowing negative matches (would hide real sign errors).
- Evidence: Spot-check MSFT|CapEx|FY2026 = 115948000000 (PDF page 76 '(115,948)'), xbrl match.
- Outcome: CapEx 93/93 matched after the fix.
- Status: active

### D-058
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: HD and TGT rejected: IS header '2025' is the company fiscal label (HD period ends 2026-02-01); a company-wide shift broke balance sheets.
- Decision: shift_of(stmt) = report year - max(column year <= report year) per statement. fiscal_year = header year + shift (period-end year, D-043). The gate anchor uses the report month and day inside the fiscal year, with no extra shift.
- Chosen: The shift is computed per statement from the header and the filing's report_date.
- Why: Retail fiscal calendars (ending late Jan or early Feb) shift the printed year, while balance sheet headers match the period-end year.
- Rejected: Company-wide shift (broke BS); fiscal calendar lookup from XBRL (XBRL is validator only, though it would need a value source).
- Evidence: HD|Revenue|FY2026 = 164683000000, PDF page 51 header '2025' with 'Net sales $ 164,683', period_end 2026-02-01, xbrl match.
- Outcome: HD and TGT match after the fix.
- Status: active

### D-059
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: Layout failures from parse output: PG columns [] (header row kept as data), MRK column 2026 spurious (rows have 3 values), CRM and HD '% of revenue' interleaved columns, HD EPS row with 6 values wrongly collapsed.
- Decision: infer_header uses the first row with a trailing run of >=2 integers in 1990-2100 as columns and removes it from rows. normalise_layout drops columns after the newest year when rows match the kept width. It collapses values[0::2] for interleaved percentage columns when all odd values are <=100 in absolute terms and the label has no 'per' or 'share'.
- Chosen: Applied before row matching; facts keep the labelled values.
- Why: Per-share rows (EPS) are the only rows where the percentage test can be wrong; excluding them avoided the HD EPS rejection.
- Rejected: Re-parsing all pages (the parser is owned by another agent; see D-061 and the gaps list).
- Evidence: tests/test_extract.py::test_layout_drops_future_column_and_keeps_value_of_pct_pairs, test_infer_header_from_year_row.
- Outcome: PG and MRK columns fixed; HD EPS not collapsed.
- Status: active

### D-060
- Time: 2026-11-23 04:13 IST
- Stage: M4
- Trigger: Gate design and numbers (M4a deliverable 2).
- Decision: validate.gate per fact: candidates from data/xbrl/{T}.json us-gaap tags (metrics.yaml xbrl_tags, units USD or USD/shares), own-accession 10-K FY entries if any, else all 10-K FY entries. Flow metrics need a 350-380 day span; balance metrics are instant; end date within DATE_WINDOW_DAYS=7 of the fiscal year anchor. Match if any candidate is within TOLERANCE=0.005 (relative; EPS within 0.005 absolute). Mismatch: fact rejected, written to data/facts/{T}.rejected.json with reason 'xbrl_mismatch: pdf X vs xbrl Y'. No candidate: admitted with xbrl_status no_xbrl and validated False. Identity check (TA vs TL + Eq, IDENTITY_TOLERANCE=0.005) and a sign and magnitude check (MAX_ABS_USD=1e13, MAX_ABS_EPS=1000) are logged only.
- Chosen: Reject, not admit, when the XBRL value is present and disagrees; admit with no_xbrl when absent.
- Why: A wrong admitted value is worse than a missing one (the system abstains on missing facts). no_xbrl keeps coverage where XBRL has no tag.
- Rejected: Loosened tolerance (forbidden by M4a); using XBRL as value source (forbidden); flagging instead of rejecting (would let bad facts into the graph).
- Evidence: tests/test_validate.py (tolerance edges, mismatch rejected, no_xbrl admitted, period matching ignores 10-Q and other years, identity logs only); 118 pytest pass repo-wide at 04:18 IST.
- Outcome (run 04:16 IST, after D-063 and the parser fix D-062): XBRL match 976/976 = 100% of compared; rejected 0; no_xbrl 28; candidates 1004 (admitted 1004, identity 22, period_end None 15: all no_xbrl facts, no XBRL end date to fill from, left None). Per metric (matched/compared): Revenue 117/117, NetIncome 120/120, EPS 111/111, TotalAssets 76/76, TotalLiabilities 54/54 (22 no_xbrl), Equity 78/78, GrossProfit 33/33, OperatingIncome 81/81, OperatingCashFlow 99/99, CapEx 93/93 (3 no_xbrl), R&D 48/48 (3 no_xbrl), Cash 66/66. Identity check: 54 checked, 2 failed (UNH, logged only). Sanity failures: 0.
- Earlier run (04:12, before D-062 and D-063): 953/959 matched, 6 rejected (AXP Revenue 3, C NetIncome 3). Superseded.
- Status: active
### D-061
- Time: 2026-11-23 04:13 IST (corrected 04:16 IST)
- Stage: M4
- Trigger: Gate rejections after the D-055 and D-057 fixes.
- Decision: Revenue exclude list adds 'non' (stops 'Total non-interest revenues' being taken as total revenue). Rejects went from 9 to 6 (only the C Revenue facts were fixed; the AXP rejections remained). The remaining 6 were investigated: AXP Revenue (3) fixed in D-063; C NetIncome (3) is not a scale error: the parsed value 7,110 (million) on p159 does not match XBRL 14,306 (no power of 1000 links them), so it is a wrong page or row in the parse. The parser is owned by another agent; this is recorded, not fixed here.
- Chosen: Exclude 'non' as a general rule, not a per-ticker override.
- Why: 'non' is a general marker of sub-totals (non-interest, non-GAAP); the gate is the check that caught it.
- Rejected: Adding 'net of interest' as a synonym for AXP (superseded by the tag fix D-063, not a label change).
- Evidence: Run output at 04:12 IST: 9 rejects before the 'non' exclusion, 6 after.
- Outcome: 0 rejected at 04:16 IST after D-062 parser fix and D-063.
- Status: active
### D-062
- Time: 2026-11-23
- Stage: M3
- Trigger: M4 XBRL gate: NVDA income_statement picked MD&A percent table p57; bank statements picked MD&A/segment/overview pages (C p16 and p39, JPM p79/p93, BAC, COF, MS, AXP missing Revenue/NetIncome/EPS/TotalAssets/Equity).
- Decision: (1) title_kinds requires _is_heading: text outside the title match is at most 8 words and has no banned word (overview, analysis, summary, discussion, selected, table, highlights, results, notes, expressed, information). (2) is_statement_layout rejects pages with 3+ lines of 'N %' values, a header with %/percent/change/increase/decrease, or 3+ rows with 5+ values. find_statements skips candidate pages that fail the layout check. (3) is_continuation accepts a page whose first 3 lines carry '(Continued)' even when the title repeats, and still requires the layout check. (4) metrics.yaml: EPS label_regex '^diluted earnings$' (BAC prints 'Diluted earnings'); NetIncome label_regex '^[a-z ]+s net income$' (after norm drops the apostrophe, C prints "Citigroup's net income" = 14,306).
- Chosen: rules in src/parse.py (title, layout, continuation); two label regexes in config/metrics.yaml; tests in tests/test_parse.py (test_mdna_sentence_and_overview_headings_are_not_titles, test_company_prefixed_lowercase_title_is_kept, test_percent_of_revenue_and_segment_pages_are_rejected, test_percent_change_header_is_rejected, test_continued_bank_page_is_a_continuation).
- Why: The audited statements carry the title as a heading, have a few year columns and no percent rows; MD&A pages repeat the title inside sentences or tables. A short company-name prefix (JNJ 'Johnson & Johnson and subsidiaries consolidated balance sheets') must still pass, so the rule is word-based, not capitalisation-based (a capitalisation rule dropped JNJ statements in a test run).
- Rejected: Ticker-specific page overrides (not needed for the banks; the generic rules picked the right pages for all 8 banks). Merging all pages with a title (would pull in MD&A pages). Changing the XBRL gate for AXP revenue (gate working as designed; see Outcome).
- Evidence: After the rules, data/parsed reuse run: 0 of 40 lacking statement or scale. NVDA IS p71 Revenue 215,938 (income statement) and BS p73 Total assets 206,803. JPM IS p243 Total net revenue 182,447 and NI 57,048; BS p245 Total assets 4,424,900. C IS p159-160, BS p161-162, CF p165-166, Citigroup's net income 14,306 admitted by the gate. BAC EPS admitted (3.81). Pytest 117 passed.
- Outcome: Extract run: XBRL match 965/968 (99.7%), rejected 3 (all AXP Revenue: 'Total revenues net of interest expense' 72,229 vs XBRL 41,304, a gate/tag mismatch not a parse error). Still missing for core metrics: COF Revenue (no total-revenue row; COF prints net interest income plus non-interest income), C EPS (EPS values not on the label line in the PDF text), V EPS, PFE EPS, SBUX Equity, TGT TotalLiabilities, MRK TotalAssets and TotalLiabilities (MRK balance sheet column layout unresolved; MRK IS header parsed as 2025,2024,2026,2023). [Superseded by D-056 outcome: the identity fallback does NOT cover ABT; ABT TotalAssets/TotalLiabilities/Equity stay missing.] Status: active

### D-063
- Time: 2026-11-23 04:16 IST
- Stage: M4
- Trigger: Final-stage gate rejects (AXP Revenue x3) and missing SBUX Equity and TGT TotalLiabilities.
- Decision: (1) Revenue xbrl_tags adds RevenuesNetOfInterestExpense, the XBRL concept for revenue net of interest expense, which AXP reports (FY2025 72229000000 is in data/xbrl/AXP.json under that tag). (2) Equity label_regex and TotalLiabilitiesAndEquity label_regex accept 'deficit' and 'investment' in place of 'equity' (SBUX: 'Total shareholders' deficit'; TGT: 'Total shareholders' investment' and 'Total liabilities and shareholders' investment').
- Chosen: Add the XBRL tag as a general candidate (gate tolerance unchanged, TOLERANCE=0.005); regex extended by a general word.
- Why: The root cause was a missing XBRL tag, not a wrong PDF value (verified: the tag holds 72229000000 for end 2025-12-31). Regex widening is general (any company using deficit/investment wording).
- Rejected: Loosening the tolerance; per-ticker overrides; using the XBRL value as the fact value.
- Evidence: Rerun 04:16 IST: rejected 0 (was 3 at the parser-fix run); SBUX Equity FY2026 -7669100000 and FY2025 -8096600000, both match in XBRL. TGT TotalLiabilities via identity is admitted with xbrl_status no_xbrl (unvalidated: the XBRL Liabilities tag is absent for TGT); it is not a match. tests: 118 pass.
- Gate fix (same date): gate_fact took xbrl_value and period_end from the first candidate even when a later one matched; now from the matched candidate. Before: 19 matched facts had xbrl_value != value; after: 0. Match counts unchanged.
- period_end None (15): all prior-year, no_xbrl facts; the filing's report_date covers only the newest year, so they stay None.
- Outcome: 976/976 matched; 0 rejected; COF Revenue, C EPS, PFE EPS, V EPS, MRK and ABT totals remain missing (see D-062 and D-056 outcome lines).
- Status: active

### D-064
- Time: 2026-11-23 04:25 IST
- Stage: M4
- Trigger: Coordinator m00408: the gate accepted a match on any tag, so wrong concepts counted as validated (MS NetIncome 17,025 incl. NCI vs parent 16,861 on p187; INTC/KO/C/MS Equity took total equity incl. NCI, e.g. INTC 126,360 vs parent 114,281; 13 Equity, 3 NetIncome, 3 JNJ R&D matched only a secondary tag).
- Decision: metrics.yaml xbrl_tags lists only concepts for the same measure. NetIncome: NetIncomeLoss. Equity: StockholdersEquity. CapEx: PaymentsToAcquirePropertyPlantAndEquipment. R&D: ResearchAndDevelopmentExpense (+ ExcludingAcquiredInProcessCost, D-068). Cash: CashAndCashEquivalentsAtCarryingValue. EPS: EarningsPerShareDiluted; basic_xbrl_tags EarningsPerShareBasic applies only to rows labelled 'Basic' (extract sets fact xbrl_tags, the gate uses it and drops the override).
- Chosen: Narrow tag list over a looser list plus tolerance. Each fact records xbrl_tag of the candidate that matched.
- Why: A tag is only a validator if it names the same concept; a broader concept can match by coincidence (NCI-inclusive totals).
- Rejected: Keeping ProfitLoss and total-equity tags as alternates (they let wrong facts pass); loosening the tolerance.
- Evidence: After the change, MS NetIncome 16861000000 (NetIncomeLoss), MS Equity 111632000000 and INTC Equity 114281000000 (StockholdersEquity) match with the parent value.
- Outcome (04:25 IST, final run): 947/947 matched, 0 rejected, 57 no_xbrl (was 933 matched of 955 compared with 2-tag matching and 6 rejects). Each fact records xbrl_tag.
- Status: active

### D-065
- Time: 2026-11-23 04:25 IST
- Stage: M4
- Trigger: Same as D-064: the extracted row was the NCI-inclusive total when a parent row existed.
- Decision: NetIncome label regex adds '^net income applicable to (?!.*(non ?controlling|common))' and the exclusion for 'applicable to common' is in the regex (not in exclude, so 'Net earnings attributable to ... common shareholders' still matches the attributable regex for UNH). Equity regex: '^total (?!liabilities)[a-z]+( [a-z]+)* (stockholders|shareholders) (equity|investment|deficit)$' requires a name word before 'stockholders' (bare 'Total stockholders equity' is NCI-inclusive); '^(total )?equity attributable to (?!.*non ?controlling)'. Equity fallback_labels adds the NCI-inclusive totals, used only when no parent row exists. Equity exclude: noncontrolling, non controlling.
- Chosen: Parent-row regex first, NCI-inclusive total as fallback only, and the gate decides whether the fallback is valid.
- Why: The 'total' row in banks and in Intel includes NCI; the parent-attributable row is what XBRL StockholdersEquity and NetIncomeLoss measure.
- Rejected: Exclude 'common' from NetIncome globally (broke UNH 'Net earnings attributable to UnitedHealth Group common shareholders', 3 facts rejected in an earlier run).
- Evidence: Run 04:25 IST: MS NetIncome 16861000000 and Equity 111632000000, INTC Equity 114281000000, KO Equity 32169000000, C Equity 212291000000 are the parent values. JPM and BAC 'applicable to common stockholders' rows (after preferred dividends) were rejected in an intermediate run and are excluded by the 'common' lookahead.
- Outcome: NetIncome 117/117 matched, 3 no_xbrl; Equity 70/70 matched, 8 no_xbrl.
- Status: active

### D-066
- Time: 2026-11-23 04:25 IST
- Stage: M4
- Trigger: Coordinator m00408: sanity_ok was logged only.
- Decision: validate.gate rejects a fact that fails sanity_ok (reason 'sanity: value U unit X'). Rejected facts go to data/facts/{T}.rejected.json and the count is stats['rejected'].
- Chosen: Reject (blocks admission), not flag.
- Why: A value that fails sanity (negative revenue or TotalAssets, |USD| > 1e13, |EPS| > 1000) is wrong; flagging would let it into the graph.
- Rejected: Log-only (the previous behaviour).
- Evidence: tests/test_validate.py::test_gate_rejects_insane_value_and_counts_it.
- Outcome: 0 sanity rejects in the final run.
- Status: active

### D-067
- Time: 2026-11-23 04:25 IST
- Stage: M4
- Trigger: Coordinator m00408 items 3, 5, 7: identity check, rounding, TotalLiabilities identity gate.
- Decision: identity_check skips any identity-derived input (TotalAssets or TotalLiabilities). Identity values are rounded to int like direct facts. Identity TotalLiabilities is gated against the XBRL Liabilities tag like any fact; no_xbrl when the tag is absent (it is, for all 22 cases). Also: find_metric_row lost its unused metric_name parameter.
- Chosen: Gate reuse, no new code path.
- Why: Identity inputs cannot validate each other; the XBRL tag is the independent check when it exists.
- Rejected: Using XBRL Assets or Liabilities as the value (XBRL is validator only).
- Evidence: Final run 04:25: TotalLiabilities 54/54 matched, 22 no_xbrl; identity check 54 pairs, 2 failed (UNH, logged).
- Outcome (04:25 IST): 22 identity TotalLiabilities facts, all no_xbrl (admitted unvalidated, no XBRL Liabilities tag for those filers); TotalLiabilities 54/54 matched overall. The 947/947 figure covers compared facts; no_xbrl facts are not in it.
- Status: active

### D-068
- Time: 2026-11-23 04:25 IST
- Stage: M4
- Trigger: JNJ R&D (3 facts) matched only the secondary tag before D-064; after restriction they were rejected (ResearchAndDevelopmentExpense = 109 for FY2025).
- Decision: R&D xbrl_tags adds ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost. JNJ prints 'Research and development expense' excluding IPR&D impairments (a separate line), so this is the same measure for JNJ.
- Chosen: Add the concept for this measure, not a per-ticker override.
- Why: The XBRL concept name and value (14665 for FY2025) match the printed line.
- Rejected: Keeping the rejects; per-ticker tag.
- Evidence: JNJ R&D FY2025 14665000000, FY2024 17232000000, FY2023 15085000000 all match the ExcludingAcquiredInProcessCost concept.
- Outcome: R&D 48/48 matched, 3 no_xbrl (04:25 run).
- Status: active

### D-069
- Stage/Trigger: Groq 429s on uncached calls while `python -m src.entities` runs (free tier 6000 TPM).
- Decision (chosen): Sliding 60 s window of estimated tokens (chars/4 of system+prompt, plus 1500 reasoning allowance) per Groq attempt, limit GROQ_TPM (default 6000, env-overridable). Each attempt waits until it fits, under a module lock shared by threads. On 429, sleep the 'try again in Xs' or retry-after hint (cap 60 s), up to 4 retries, then Gemini.
- Why / rejected: chars/4 needs no tokenizer; a fixed call-count gap ignores prompt size; plain exponential backoff ignores the server's own wait hint. A single call larger than the budget runs when the window is empty, so it cannot block forever.
- Evidence / outcome / status: tests/test_llm.py (limiter, 429 parse, Groq-exhausted to Gemini). Active.

### D-070
- Stage/Trigger: Reducing Groq reasoning tokens per uncached call (TPM budget, D-069).
- Decision (chosen): reasoning_effort 'low' on openai/gpt-oss-120b.
- Why / rejected: Fewer reasoning tokens per call. Default effort rejected for TPM use.
- Evidence / outcome / status: One tiny real call returned HTTP 200 with 'pong'; kept. Active.

### D-071
- Stage/Trigger: gemini-flash-latest returned 503 on the fallback path (see D-028, D-013).
- Decision (chosen): GEMINI_MODEL = gemini-3.1-flash-lite. Calls are serial with a 6 s minimum gap (10 req/min), and 429/5xx retry up to 3 times with backoff.
- Why / rejected: Concurrent Gemini calls rejected: 2 of 5 hit 429. Supersedes the model id in D-028.
- Evidence / outcome / status: 10/10 serial calls succeeded in a manual check; 2 of 5 concurrent hit 429. Active.

### D-072
- Stage/Trigger: M7 benchmark draft (no benchmark file existed; PROGRESS M7 pending).
- Decision (chosen): benchmark/benchmark.json with 29 items: 10 single_fact, 10 multi_hop, 9 cross_filing, across Tech, Banks & Payments, Consumer & Retail, Healthcare. Gold typed from data/parsed page text with per-figure page and key quotes. Three abstain items (Q06 BAC FY2026, Q10 Visa R&D, Q20 JPM gross profit), each marked answerable_by_graph unknown. All items verified false.
- Why / rejected: Gold from PDF text keeps it independent of the system. Rejected: gold from data/facts (circular) and gold taken from system gaps. Q09 (Pfizer EPS) and Q08 (MRK total assets) are answerable from the PDF despite PROGRESS gaps, so they stay answerable, with notes.
- Evidence / outcome / status: tests/test_benchmark.py 6 pass. Human review pending (verified false). Active.

### D-073
- Stage/Trigger: M5 build graph (task: src/graph.py builds graph/kg.json from data/facts and data/entities).
- Decision (chosen): NetworkX MultiDiGraph, saved as node_link_data (edges="edges") at graph/kg.json, 1.11 MB. Node types: Company (ticker), Sector (SEC|name), Metric (M|name, derived flag), Filing (FIL|accession), Period (PD|TICKER|FYyyyy|period_end), Fact (TICKER|Metric|FYyyyy), Location, Organization, Segment, Person (keep entity ids). Edges (attr rel): IN_SECTOR, FILED, HAS_FACT, OF_METRIC, FOR_PERIOD, REPORTS (Filing->Fact), COMPUTED_FROM (Metric->Metric, attr formula), INCORPORATED_IN, HEADQUARTERED_IN, AUDITOR_BASED_IN, LISTED_ON, HAS_SEGMENT, AUDITED_BY, EXECUTIVE_OF (Person->Company, attr title). Fact attrs: value, unit, scale, period, doc, page, snippet, method, validated, xbrl_status, xbrl_value, xbrl_tag, as_reported_label. Entity Employees facts use method "entity", validated False.
- Why / rejected: Derived values (NetMargin, GrossMargin) are not stored as facts so provenance stays traceable from input facts; query time computes them. Period keyed by (ticker, FY, period_end) because 27 of 120 (ticker, FY) pairs have two period ends. Rejected: graph built from rejected facts or ungrounded entities (excluded by spec). build_graph asserts doc, page, value, unit, period, validated present on every Fact and fails loudly.
- Evidence / outcome / status: Run 1 (05:42 IST): 1033 facts, 947/947 XBRL matched (100%), 57 no_xbrl, 0 rejected. Entity files still changing (another process re-runs M4b), so the later run gave 1035 facts (Employees missing 9 tickers instead of 11). Open: 27 Period nodes have period_end None (entity Employees facts whose FY is not the report year). tests/test_graph.py 12 pass. Active. [Superseded by D-078: the 27 None periods are statement facts (prior-year comparatives, src/extract.py:225 sets period_end None for non-newest years), not Employees; 32 facts on 27 Period ids, 21 pdf_table and 11 identity; 1039 facts = 1004 statement + 35 Employees after the regate.]

### D-074
- Stage/Trigger: M5 naming conflict between user request (src/graph.py) and GOAL.md Done-when (python -m src.build_graph).
- Decision (chosen): implementation in src/graph.py (python -m src.graph); src/build_graph.py is a 3-line alias that imports main from src.graph, so both commands work.
- Why / rejected: Satisfies both sources without duplicated code. Rejected: renaming the module (would break the GOAL.md command) and a second implementation.
- Evidence / outcome / status: Both commands run and print the same report. Active.

### D-075
- Stage/Trigger: M6 query design (src/planner.py, src/query.py); graph-only answers, Gemini quota ~10 req/min.
- Decision (chosen): rule planner (companies/aliases, sector, metric synonyms plus explicit aliases, FY mentions, intent keywords) -> plan {intent lookup|compare|rank|derived|growth|aggregate|entity, companies, sector, metric(s), years, op, growth, entity_rel, role, topn}. LLM planner (json_mode, cached) only if check(plan) fails; its plan is validated against tickers/metrics/sectors/ops/rels (unknown ticker -> unknown_company, else plan_failed; LLM error -> plan_failed). Bare 'income'/'margin' -> ambiguous, unknown capitalised name -> unknown_company, both without LLM. Executor reads Fact nodes only; derived (NetMargin, GrossMargin from graph formula, OperatingMargin in code) and growth (pct, pp for margins; needs FY-1) computed from inputs, all input fact ids returned; entity multi-hop = rank to pick winner, then follow HQ/AUDITED_BY/EXECUTIVE_OF/HAS_SEGMENT. Year omitted -> newest FY per company (mixed_years flag if they differ); named year missing -> unsupported_period (no filing) or no_fact. Named company sets are strict; sector/whole-universe rank is lenient with incomplete+missing flags. validated=false facts answered with flag.
- Why / rejected: Rules are free and deterministic; LLM is the fallback only. Rejected: LLM-first planning (quota, hallucination), fuzzy/embedding company matching, XBRL fallback, silently skipping missing companies in named comparisons.
- Evidence / outcome / status: tests/test_query.py (synthetic graph, stubbed llm) passes; dev questions on real graph run. Active.

### D-076
- Stage/Trigger: M6 verifier findings on src/planner.py and src/query.py.
- Decision (chosen): remove bare 'cash flow' from OperatingCashFlow aliases; if 'cash flow' appears without an operating qualifier (OCF_RE), abstain unsupported_metric. Growth cue regex `grow\w*` (was 'growth'). rank/compare rows print each company's FY (e.g. 'CCC FY2025 $50.00 billion'); mixed_years flag kept.
- Why / rejected: no FCF metric exists in the graph, so substituting OCF is wrong; abstaining is the strict-abstain rule (D-075). Rejected: keeping the bare alias with a qualifier blacklist (fragile). Rejected: dropping the mixed_years flag (flag still useful to the reader).
- Evidence / outcome / status: tests/test_query.py 17 pass (new: test_cash_flow_qualifiers, test_growth_verb, test_rank_mixed_fiscal_years_named_in_text); full suite 178 pass. Active.

### D-077
- Stage/Trigger: M4b entity extraction (src/entities.py, data/entities); verifier review of M4b, no LLM calls in this step.
- Decision (chosen): An entity is admitted only if its name (or employee number) appears literally on a cited page of data/parsed/{T}.json (case and whitespace normalised). Ids: PERSON|T|slug(name), SEG|T|slug(name), LOC|slug(name), ORG|slug(name) (exchange names via D-078), Employees Fact `{T}|Employees|FY{year}` with year from the filing report_date, value int, unit count, relation EMPLOYS_COUNT, validated False. One LLM call per category (cover, segments, employees, auditor, officers) on pages from find_windows, excerpt capped at MAX_CHARS 6000; one retry with RETRY_NOTE on bad JSON. Provider mix: 194 cache files, 144 Groq and 50 Gemini (counted from the cache provider field); entity records do not store the provider.
- Why / rejected: Literal grounding makes every entity checkable against the page text, with no outside knowledge. Employees stay unvalidated because no XBRL tag exists to check them. Rejected: admitting ungrounded names with a flag (the graph would still have to exclude them).
- Evidence / outcome / status: 504 candidates, 488 admitted (96.8%): Location 78, Organization 51, Segment 75, Fact 35, Person 249. 16 rejected ("not found in cited page text"): Location 12, Person 3, Segment 1. Gaps: auditor missing for BAC, C, GS, V, MA, AXP, PYPL (27 of 40 companies have no admitted auditor); officers missing for BAC, C, COF, V, PYPL; segments missing for MS, PYPL; Employees missing for INTC, MS, AXP, PFE, AMGN. Active.

### D-078
- Stage/Trigger: M4b verifier findings and regate of data/entities (src/entities.py, tests/test_entities.py).
- Decision (chosen): (1) ground() uses _literal_rx: a letter edge may not touch a letter, a digit edge may not touch a digit or a ",d"/".d" continuation, so "166,000" does not match "1,166,000". Footnote digits glued to a name ("Delaware1") still match, deliberately. (2) Employees: as_written must yield the same integer as employee_count (NUM_TOKEN_RE, _count_value); otherwise the candidate is rejected with reason "as_written ... does not give employee_count N". The matched number token is grounded; with no as_written, f"{n:,}" is grounded. snippet is set on every grounded path. (3) exchange_slug() drops the, llc, global, select, market, stock and repeated tokens for names containing exchange or market: ORG|nasdaq and ORG|new-york-exchange. (4) `python -m src.entities --regate` swaps complete for cache_only (no network); a missing cached reply raises CacheMiss (RuntimeError), counted as a failed category, and the run prints "cache misses N". src/llm.py and the prompt/schema constants are unchanged.
- Why / rejected: Unchanged prompts keep cache keys valid, so the regate needs no LLM calls. Rejected: requiring the employee number to be on a fixed page. Rejected: dropping "exchange" from ids (keeps the id readable). Shortcut: NYSE and New York Stock Exchange still differ (ORG|nyse vs ORG|new-york-exchange), upgrade with an explicit alias table if a query needs it.
- Evidence / outcome / status: Baseline replay with the old gate reproduced data/entities byte for byte (488/16/35). New rules: 0 cache misses, admitted 488, rejected 16, Employees 35 unchanged, no entity changed admitted/rejected status. Organization ids: 12 distinct before, 7 after (35 company files re-keyed to ORG|nasdaq or ORG|new-york-exchange). Spot-checks against data/parsed page text: JPM PERSON|JPM|james-dimon p70; AAPL SEG|AAPL|americas p5; WMT Employees FY2026 2100000 p7 "approximately 2.1 million associates"; KO LOC|delaware p1; MSFT ORG|nasdaq p1. tests/test_entities.py 13 pass (5 new); full suite 175 pass. Active.

### D-079
- Stage/Trigger: M8 evaluation (src/evaluate.py, tests/test_evaluate.py); first scoring design.
- Decision (chosen): see the at-a-glance row D-079: numeric within 0.5% of gold, text gold matched on normalised terms, abstain-expected correct only if abstained, fact precision/recall on gold fact ids, wrong_page is a failure category while correctness stays value-based, no checkable gold = unscored.
- Why / rejected: Keeps scoring deterministic and rerunnable from the LLM cache without a key. Rejected: LLM-as-judge (non-deterministic, needs keys, costs calls).
- Evidence / outcome / status: First run 19/28 correct, P 0.817, R 0.833. Amended by D-080 after the verifier review.

### D-080
- Stage/Trigger: M8 review after the first real run; Opus verifier findings on src/evaluate.py and tests/test_evaluate.py. Amends D-079.
- Decision (chosen): (1) Numeric gold matches the structured value (0.5% tolerance). Fallback only when the structured value is NOT numeric (dict/str/None, e.g. the HQ entity of Q16): also match the value of any returned fact node (unit None, no scaling) or any number in the answer text (x% for '%' answers, USD scales otherwise). A numeric structured value is judged alone: no fact-node or text credit. (2) Unscored rows (no number, no term gold, e.g. Q15) get no correct, precision, recall, doc_hit or page hit and are excluded from every mean; they stay in per_question.csv with failure_category unscored. (3) page_hit is renamed page_hit_strict (row) and page_strict_rate (aggregate) and reported beside doc_hit_rate. metrics.json notes: wrong_page is kept as a failure category and those rows count as correct for accuracy. (4) benchmark/benchmark.json, src/query.py and src/planner.py are unchanged. The gold was not edited.
- Why / rejected: The scorer was changed AFTER the first scores were seen (D-079 run: 19/28 correct, 67.9%; precision 0.817; recall 0.833; page hit 72.7% of answered rows). Reason: the verifier found scorer bugs. Q16 was scored wrong_value although the answer is right, and Q15 kept precision and recall from a gold fact id although it has no checkable gold. Rejected: editing gold for Q07, Q19, Q21, Q26 (verifier judged the gold suspect: gold lists summary pages, the system cites primary statement pages that contain the value). Left for the user to verify. Rejected: changing system code to fit the scores. Rejected: a fact-node rule for numeric values, which credited Q27 (a wrong sum answer) in the first amended run.
- Evidence / outcome / status: Before (D-079 run): 19/28 correct, P 0.817, R 0.833, page hit 72.7%, Q15 unscored but counted in P/R. After (final re-run of python -m src.evaluate): 20/28 correct (71.4%), P 0.84, R 0.8267, doc_hit_rate 1.0, page_strict_rate 0.7143 (scored answered rows), 1 unscored (Q15, no P/R). Flips vs D-079: Q16 wrong_value -> correct (structured value is an HQ dict, matched via text). Q27 stays wrong_value. First amended run had credited it via fact node PEP|Revenue|FY2025 = 93925e6 while the system answered a sum $141.87 billion (false positive); the numeric-value rule now blocks it. Known loose point: the fallback for non-numeric values can still match a gold number from a returned fact. Upgrade if it matters: require the fact to be the one named by the answer. tests/test_evaluate.py: new test_numeric_wrong_value_not_rescued_by_fact_node; full suite 196 pass. Active.

### D-081
- Stage/Trigger: User-requested blind AI review of benchmark/benchmark.json gold, after the first scores (D-079/D-080 runs) were published.
- Decision (chosen): Gold re-derived for all 29 items from data/parsed page text only, blind to system output (results/, src.query, src.evaluate, query/planner code and graph facts not opened). 26 confirmed, 0 corrected, 3 ambiguous (Q14, Q16 mixed FY2025/FY2026 "latest fiscal year"; Q25 differing revenue definitions; answers hold under every reading). No original gold field changed. Added per item `review` {status, note}, `ai_reviewed: true`, and `acceptable_pages` [{doc, page}] on 25 items (other pages in the same filing that carry the value). `verified` stays false. src/evaluate.py page check now accepts gold pages or a cited (doc, page) pair in acceptable_pages; nothing else in scoring changed. Q21 note resolved: BAC 3,410,412 (p68/p72) is average total assets; year-end 3,411,738 correct.
- Why / rejected: Gold listed one page per value, so a primary statement page holding the same number counted as a page miss. Rejected: replacing gold pages (keeps the original record). Rejected: rerunning src.evaluate here (left to the user). Disclosure: this changes page_strict_rate only, after scores were seen; accuracy is value-based and unaffected. Items whose page sets grew: all except Q06, Q08, Q10, Q20.
- Evidence / outcome / status: benchmark/gold_review.md; tests/test_evaluate.py test_acceptable_pages_count_as_page_hit; full suite 197 pass. src.evaluate not rerun. Active.

### D-082
- Stage/Trigger: Independence check on the system: a held-out benchmark written before the planner/parser fixes.
- Decision (chosen): benchmark/heldout.json (H01-H15; 5 single_fact, 5 multi_hop, 5 cross_filing; 2 abstain: H05, H15; 17 tickers) with benchmark/heldout_README.md and tests/test_heldout.py. Gold derived from data/parsed page text only; src.query, results/, planner, graph and data/facts not read. benchmark.json read for schema only and untouched. verified false.
- Why / rejected: Q01-Q29 were seen during development, so scores on them can be tuned toward. Rejected: reusing benchmark.json questions, deriving gold from graph facts (not independent).
- Evidence / outcome / status: every evidence key checked on its cited page; test_heldout.py added. Not yet scored by src.evaluate. Active.

### D-083
- Stage/Trigger: Read-only audit of src/planner.py, src/query.py, src/evaluate.py, src/llm.py for generic bugs (benchmark files and results deliberately not read; src.evaluate not run).
- Decision (chosen): (1) planner: 'total' means sum only when no comparison cue (MAX/MIN words, more, less, which) is present; sum, combined, together, add up, aggregate, cumulative, average always aggregate. more/less added to MAX_RE/MIN_RE. (2) 'com' added to NAME_SUFFIX and 'amazon' removed from GENERIC_FIRST so Amazon.com Inc. gets the alias 'amazon'. (3) a metric alias directly preceded by current, dividend(s), return on, pre-tax, pretax, cost of (after skipping 'total') or followed by dividend(s) abstains with unsupported_metric unless the alias itself contains that word; longest alias match was already first. (4) query.numeric_answer: lookup with one company and 2+ named years returns every year (rows keyed 'T FYy', value dict). (5) query.role_ok: word-boundary title match on the text before the first comma; vice president/vice chair stripped for roles president and chair; planner emits role 'vice president' when the question says vice. (6) evaluate: finish() returns 'winner' for max/min answers; score() then credits company terms only to the winner (name set and text before ' | '); text_has_number skips bare 19xx/20xx tokens. (7) llm._cache_read returns None on OSError/ValueError/KeyError/TypeError; _cache_write writes a pid tmp file then os.replace.
- Why / rejected: Each bug let a wrong metric, entity, year or sum be answered or credited. Rejected: a stopword list for 'current' anywhere in the question (would abstain on 'current revenue'; only adjacent words count). Rejected: crediting the winner by parsing text only (winner field is exact). Shortcut: 2+ years with several companies still uses the first year only; a bare 4-digit gold in 1900-2099 is no longer credited from answer text (written '2,025' still is).
- Evidence / outcome / status: tests/test_planner_fixes.py 41 tests; full suite result in the final run. Active.

### D-084
- Stage/Trigger: Read-only audit found generic parser/extractor gaps: EPS rows without section heading, unlabelled balance-sheet totals, repeated statement title on next page, bank revenue with no total row, NVDA CapEx label, '(1)' read as -1.
- Decision (chosen): (A) src/tables.py parse_text_lines prefixes a numberless EPS heading to following row labels until a weighted/average/shares row; EPS spec prefers rows without continuing/discontinued (prefer_exclude, src/extract.py find_metric_row). (B) label_unlabeled_totals names a bare row after the equity block 'Total liabilities and equity' and the last bare row before the liabilities block 'Total assets'; src/parse.py is_repeated_title treats a repeated title on the next page as a continuation (not 'comprehensive'). (C) Revenue identity = NetInterestIncome + TotalNonInterestIncome, banks_only, only when no printed revenue row. (D) CapEx regex allows 'related to'. (E) trailing '(d)' footnote token dropped. (F) fiscal_year_label_note skipped (D-043 stays).
- Why / rejected: Facts stay PDF-only; XBRL only validates. Rejected: taking the first bare row as total assets (Merck's gross-PP&E subtotal 47,230 failed the gate, caught by XBRL); loosening TOLERANCE.
- Evidence / outcome / status: tests/test_parse_fixes.py; gate 962/962, 0 rejected; admitted 1004 to 1029. Active.

### D-085
- Stage/Trigger: Pre-submission cleanup so docs match the final numbers. No planner, query, parser or extractor code changed.
- Decision (chosen): src/evaluate.py adds accuracy_over_all (correct/n, the task rule), precision_excl_abstain and recall_excl_abstain (overall and per type); existing accuracy (correct/scored) kept. Each evidence entry in benchmark/benchmark.json and benchmark/heldout.json gets a `doc` (data/pdfs/{TICKER}.pdf, derived from the page where the key was found); gold values, pages and answers untouched. README.md, scripts/make_report.py, report/results.pdf, GOAL.md (local path removed) updated; README states gold is AI-drafted and AI-reviewed, not human verified.
- Why / rejected: Task defines accuracy as correct over total, so 26/29 must be shown beside 26/28 scored. Held-out result reported as it is (9/15 baseline, 8/15 after fixes): main gains partly came from inspecting failures. Rejected: hiding the held-out regression; editing gold.
- Evidence / outcome / status: main 26/29 = 89.7% (26/28 = 92.9% scored), P 1.0, R 1.0; held-out 8/15 (53.3%), P 0.80, R 0.83. Remaining failures: main Q13, Q14; held-out H06-H08, H10, H11, H13, H15. pytest 249 passed. Active.

### D-086
- Stage/Trigger: Read-only audit of planner/executor gaps (difference, share, growth vs total, comparison wording, unknown company) and missing AXP operating cash flow. No benchmark read.
- Decision (chosen): src/planner.py: intent `difference` (DIFF_RE; 2 companies+1 metric or 1 company+2 metrics), op `share` (SHARE_RE; metrics[0]/metrics[1] as %, 'Y as a % of X' keeps order, 'share of X went to Y' reverses), GROW_RE beats 'total' for one company, `unknown_company()` abstains on a capitalised unknown name next to a known company or before Inc/Corp (stop lists for months, metric words, sentence-initial words); old `rate` substring bug ('gen-erated') fixed; OCF aliases widened. src/query.py: difference_answer (magnitude + signed_value, both fact ids), share via spec_of pct. config/metrics.yaml OperatingCashFlow applies_to all (banks) + 'net cash used for operating activities' synonyms.
- Why / rejected: AXP is_bank excluded nonbank-only OCF. Rejected: LLM for these (deterministic cues suffice); signing the headline difference (magnitude reported, sign in signed_value).
- Evidence / outcome / status: extract candidates 1029 -> 1050, XBRL 962/962 -> 983/983, 0 rejected; tests/test_planner_intents.py, pytest 268 passed. Limits: lower-case unknown names unseen; unknown name before a suffix reports first word only. 'percent of' no longer means ratio. Active.


### D-087
Stage/Trigger: generalisation check after D-086 fixes (the held-out set became a dev set).
Decision: wrote benchmark/fresh.json (F01-F15) from PDFs without reading planner code or outputs; scored once; no code changed afterwards.
Why/rejected: tuning on heldout.json makes 15/15 non-independent; a fresh set gives an honest number.
Evidence/outcome/status: 12/15 (80%), P 1.0, R 0.967. Failures: F09 two-metric sum, F10/F11 HD/TGT fiscal-year label shift (D-043), F15 right answer, other page. Open.

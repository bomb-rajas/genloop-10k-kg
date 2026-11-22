# Handoff: Genloop Tech Intern Take-home

Status: **planning done, no code written yet.** Brainstorming continues before coding.

## The task (from `Genloop _ Tech Intern _ Take-home Task.pdf`)

- **Deadline:** Mon 23 Nov 2026, 12:00 noon IST. Interviews Tue 24 Nov (walk through the work).
- **Build:** a knowledge graph from SEC 10-K/10-Q PDFs of 30–40 companies, and a query system that turns each question into a graph lookup or traversal and returns the answer **with its source** (doc + page). Answers must come from the graph, not from vector search over chunks.
- **Benchmark (self-made):** 25–30 questions covering three types (single-fact, multi-hop, cross-filing comparison). Each has a gold answer, source doc and page.
- **Metrics:** accuracy; precision and recall over retrieved facts versus gold supporting facts. Report overall and by question type.
- **Constraints:** a free LLM (Gemini / Groq / Ollama); regex or table parsing is fine for numbers; no GPU or paid services needed.
- **Submit:** a public GitHub repo (README with setup, run steps, how AI tools were used; benchmark file included) and a 1–2 page results PDF (results, methodology incl. benchmark prep, gaps with examples, improvements).
- **Judged on:** approach and design, honest evaluation, clarity. "A clear failure analysis beats an inflated number." "Think beyond the obvious": the graph's structure should do the work.

## Genloop paper takeaways (`64_Living_Context_Graphs_Conti.pdf`)

- "Living Context Graphs" (NeurIPS 2026 workshop): a continually learned context layer over enterprise warehouses, evaluated on text-to-SQL (BIRD). It has two parts: a semantic store (definitions, KPIs, rules, each with provenance) and a concept graph (routes the words users say to that context).
- Results: learning from verified outcomes gives +22.6 pts held-out accuracy. The **admission gate is load-bearing**: without it, accuracy falls from 53 to 29 out of 146. Removing the graph barely changes accuracy but costs 2.3–3.3× more per query.
- Repo `github.com/varunagrawal2002/Living-Context-Graph` = **data only** (fact-family annotations and splits), no code. Not directly reusable.
- **Ideas we borrow:** provenance on every object; concept/metric normalisation; "fact families" ≈ our gold supporting fact IDs; validate facts before admitting them; an honest limitations section.
- Framing for interview: we're building **KGQA** (graph is the answer source). It's GraphRAG only loosely, not the chunk-summarising kind.

## Decisions made

- **Filings:** latest **10-K** per company (FY2025), not 10-Q. 10-Qs bring messy periods (3- and 9-month columns), quarter misalignment, and fewer facts.
- **Companies: 40**, 10 per sector:

| Tech | Banks & Payments | Consumer & Retail | Healthcare |
|---|---|---|---|
| AAPL | JPM | WMT | JNJ |
| MSFT | BAC | COST | PFE |
| GOOGL | C | TGT | MRK |
| AMZN | COF | HD | ABBV |
| META | GS | PG | LLY |
| NVDA | MS | KO | UNH |
| ORCL | V | PEP | AMGN |
| CRM | MA | MCD | BMY |
| ADBE | AXP | NKE | ABT |
| INTC | PYPL | SBUX | CVS |

  - Wells Fargo was swapped for COF because WFC's financials sit in Exhibit 13. Other banks still need checking for the same issue.
  - Banks are included on purpose (Genloop's customers; sector-specific metrics). Mixed fiscal-year ends are also on purpose (AAPL Sept, MSFT June, WMT/NVDA Jan).
- **PDFs:** downloaded by script from EDGAR (HTML), converted to PDF with headless Chrome so page numbers are consistent. The user does **not** download by hand.
- **LLM:** Gemini free tier as primary, Groq as fallback, behind a switchable wrapper (`.env`). Expected load is about 100–200 calls total. Cache every call to disk.
- **Claude Pro ≠ Claude API** (billed separately). Claude Code is used only to build; disclose this in the README. No paid API or GPU in the pipeline (reproducibility, task rules).
- **Graph store:** NetworkX, saved to JSON (Kùzu/Cypher considered, skipped for time).

## Graph schema (fact-centric)

Nodes: `Company`, `Sector`, `Filing`, **`Fact`** (value, unit, scale, as-reported label, doc, page, snippet, extraction method, validated flag), `Metric` (canonical name + synonyms, category, sector applicability), `Period`, `Segment`, `Person`, `Organization`, `Location`.

```
(Company)-[:IN_SECTOR]->(Sector)
(Company)-[:FILED]->(Filing)-[:COVERS]->(Period)
(Company)-[:REPORTED]->(Fact)-[:OF_METRIC]->(Metric)
                       (Fact)-[:FOR_PERIOD]->(Period)
                       (Fact)-[:FOR_SEGMENT]->(Segment)      optional
                       (Fact)-[:SOURCED_FROM {page}]->(Filing)
(Company)-[:HAS_SEGMENT]->(Segment)
(Company)-[:AUDITED_BY {page}]->(Organization)
(Person)-[:EXECUTIVE_OF {title, page}]->(Company)
(Company)-[:HEADQUARTERED_IN {page}]->(Location)
(Metric)-[:COMPUTED_FROM]->(Metric)          derived metrics, e.g. NetMargin
```

- Fact IDs such as `AAPL|Revenue|FY2025` double as **gold supporting facts**, so precision and recall are an exact set comparison.
- **Validation gate:** check extracted numbers against SEC XBRL data (`companyfacts`) and accounting identities before marking them `validated`.
- **Query path:** question → LLM JSON plan (intent: lookup / compare / rank / multi-hop; entities, metric, period; fixed lists of allowed tickers and metrics) → templated traversal → answer + fact IDs + pages. Abstain if a needed fact is missing.
- **"Beyond the obvious" additions:** line-item hierarchy edges (Revenue → Gross Profit → Operating Income, plus "adds up to" links), which are cheap and help both checks and multi-hop questions. Company-to-company links taken from Item 1 (competitors, customers, suppliers) only if time allows.
- **Extraction is targeted and parses PDFs only** (task requirement). Item 8 tables are parsed from the PDFs with pdfplumber (no LLM), so the page number comes free. EDGAR HTML is used only to *produce* the PDFs, never parsed. HTML parsing is a possible fallback, to be decided later by the user. The LLM reads only the cover page, segments, HQ, employees, auditor report and the executive officers list.

## Planned folder structure

```
GenLoop/
├── README.md  requirements.txt  .env.example  handoff.md
├── config/      companies.yaml, metrics.yaml
├── data/        raw_html/ pdfs/ (gitignored) · xbrl/ · parsed/ · facts/ (committed)
├── graph/       kg.json (committed, so reviewers can query without re-extracting)
├── src/         download, parse, extract, validate, build_graph, query, evaluate
├── benchmark/   benchmark.json
├── results/     predictions.jsonl, metrics.json
├── CLAUDE.md    intro map, "where things live", failure log
├── docs/        decision-log.md (every major choice + rejections), flow.md (written at the end)
└── report/      results.pdf
```

## Plan of action

| # | Step | Who |
|---|---|---|
| 0 | Gemini API key; approve list and schema; SEC User-Agent contact string | **User** |
| 1 | Scaffold repo + config | Claude |
| 2 | EDGAR download → PDF; fetch XBRL | Claude |
| 3 | Parse PDFs (text + tables, per page) → extract facts | Claude |
| 4 | Validation gate → build graph | Claude |
| 5 | Query: question → plan → traversal → answer + sources | Claude |
| 6 | Draft 28–30 benchmark Qs **from the PDFs** (not from the graph) with gold fact IDs | Claude |
| 7 | **Verify gold answers against PDF pages** | **User** |
| 8 | Evaluate: accuracy / precision / recall by type | Claude |
| 9 | README, decision log, results PDF | Claude → user review |
| 10 | GitHub repo, push, fresh-clone test (`gh` CLI not installed; plain git works) | User + Claude |

**Timing:** build done by **08:00 IST**; then testing and the results PDF; submit before 11:00 meetings. **No scope cuts** (user decision).

## Main risks and backups

- SEC blocks or throttles downloads → proper User-Agent, throttle to under 10 requests/sec.
- Bank financials in Exhibit 13 → fetch the exhibit or swap the company.
- PDF table parsing (parentheses, dashes, footnotes, year columns, scale, tables split across pages) → explicit rules + tests; read the scale from the table header; XBRL gate. HTML parsing only if the user approves it as a fallback.
- Bank "revenue" semantics → separate bank metrics; mark not applicable.
- Fiscal-year mismatch → store the period end date; state the FY rule.
- Free-tier quota → cache, Groq fallback, rule-based question parser.
- Planner picks the wrong metric or company → constrained JSON output, fuzzy matching, worked examples.
- Benchmark circularity → write gold answers from the PDFs, include facts the graph may miss.
- Scoring tolerance → declare the rule up front (e.g. ±0.5%, same unit).
- Repo hygiene → `.env` gitignored, graph committed, one-command demo.
- **Decision log covers every major design choice, not only failures:** what was chosen, why, what was rejected and why, and the outcome. Failures appear only when they forced a decision. Log real failures in `docs/decision-log.md` as they happen (what broke, numbers, cause, fix, before/after). Don't invent any.

## Environment

macOS, Python 3.13, Google Chrome installed, git + Homebrew available. Ollama and `gh` are not installed.

## Open items

- [ ] Gemini API key (into `.env`)
- [ ] SEC User-Agent contact string
- [ ] Final approval of company list and schema
- [ ] Decide: line-item hierarchy edges in scope? company-to-company links?

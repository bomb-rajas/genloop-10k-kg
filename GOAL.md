# GOAL: Genloop SEC 10-K knowledge-graph QA

> This file holds the full details behind the short `/goal` command (which is capped at 4000 characters). The `/goal` text is the summary; this file is authoritative where it adds detail. If the two ever conflict, follow this file and log the conflict in docs/decision-log.md.

Build the Genloop SEC 10-K knowledge-graph QA project end to end until every item in "Done when" passes, keeping token spend low.

## Project
A knowledge graph built from the latest 10-K of 40 companies (4 sectors × 10), queried by graph traversal (not vector search). Every answer cites its document and page. Evaluated on a self-made benchmark. Python 3.13, NetworkX, pdfplumber, Gemini free tier with Groq as fallback.
Repo: /Users/pimp_juice/Documents/GenLoop. handoff.md is the spec: companies, schema, folder layout, risks. Read it once at the start.
Constraints: free LLMs only; no GPU or paid APIs in the pipeline.
PDF-only parsing: all text, tables and facts are parsed from the PDFs. EDGAR serves HTML, so the download step converts it to PDF with headless Chrome, and that HTML is never parsed for facts. Do not add HTML parsing as a fallback without my approval. SEC XBRL JSON is used only to validate extracted facts, never as an answer source.
Time: build finished by 08:00 IST. No scope cuts. Run `date` at the start of each milestone and note it in PROGRESS.md.

## Done when
- CLAUDE.md, docs/decision-log.md and PROGRESS.md exist and are kept current (see M0).
- `pytest` passes with no skips. Tests cover the PDF table-parser edge cases (parentheses as negatives, dashes as zero, footnote markers, scale headers like "in millions", picking the year column, a table split across two pages) and the scorer math.
- `python -m src.download` produces 40 10-K PDFs in data/pdfs/. Any company substitution is logged in docs/decision-log.md.
- `python -m src.build_graph` writes graph/kg.json. Every Fact carries doc, page, value, unit, period and a validated flag; the XBRL match rate is printed.
- `python -m src.query "<question>"` returns the answer, fact IDs and doc+page, or abstains.
- benchmark/benchmark.json has 28–30 questions covering all 3 types (single-fact, multi-hop, cross-filing). Each has a gold answer, gold fact IDs, doc, page and `"verified": false`. Gold answers are written from the PDF pages, not from the graph.
- `python -m src.evaluate` writes results/metrics.json with accuracy, precision and recall, overall and per type. It re-runs from the committed LLM cache without an API key.
- README covers setup, run steps and how AI tools were used.
- docs/flow.md is written from the final code (see M10).
- A fresh clone plus the README steps reproduces the evaluation. .env is gitignored and no secrets are committed.

## Milestones (one at a time)
M0 Project memory files. Create:
  - CLAUDE.md (under 80 lines), with exactly these sections:
    1. Intro map: 3 lines on what the project is, that handoff.md is the spec, and the main folders.
    2. Where things live: a table mapping "you need" to the file or folder. Update it whenever a milestone adds a module.
    3. Failure log: one imperative line per real mistake, specific to this repo (e.g. "Read the scale from the table header; never assume millions"). Add a line in the same change whenever something goes wrong or is corrected. No general advice.
    4. Decision-log rule: "Every meaningful design or build choice gets an entry in docs/decision-log.md in the same change, before moving on. That covers architecture, schema, fact-ID format, metric mapping, libraries, parsing rules, extraction approach, LLM prompts and output schemas, validation thresholds, benchmark design, scoring rules, and company swaps. Failures are logged only when they forced a decision. If you chose between options, log it, including choices made by subagents."
  - docs/decision-log.md, the record of every important decision made while building the project. It has two parts:
    a) "Decisions at a glance": a table at the top (ID, stage, decision, chosen, one-line why). Keep it current.
    b) Full entries. Each has: ID (D-001…); time (IST); stage (milestone); trigger (planned / evidence / failure / Advisor); Decision (the question being answered); Chosen; Why; Rejected (each alternative and why it was rejected); Evidence (numbers, test or output, if any); Outcome (the effect it had on the system or the metrics, filled in once known); and Status (active, or superseded by D-xxx). Never delete entries; supersede them.
    Seed it with the decisions already made in handoff.md: 10-K over 10-Q; 40 companies in 4 sectors; WFC swapped for COF; EDGAR HTML→PDF with Chrome; PDF-only parsing (HTML fallback deferred); KGQA over vector RAG; fact-centric schema with Fact nodes; Metric nodes with synonyms; derived metrics as computed edges; NetworkX over Kùzu/Neo4j; Gemini primary with Groq fallback; no paid API or GPU; XBRL as a validation gate only; fact IDs as gold supporting facts; benchmark written from the PDFs, not the graph.
  - PROGRESS.md: milestone, status, time, open issues.
M1 Scaffold + config (companies.yaml, metrics.yaml).
M2 Download from EDGAR → PDF; fetch XBRL companyfacts.
M3 Parse PDFs: per-page text and tables with pdfplumber.
M4 Extract facts + XBRL validation gate.
M5 Build the graph.
M6 Query planner (constrained JSON plan) + traversal + abstain.
M7 Benchmark draft.
M8 Evaluate. Then fill in the Outcome of every decision that affected the metrics (e.g. "XBRL gate: N facts rejected; accuracy X → Y").
M9 README.
M10 docs/flow.md, written from the actual code (grep it; don't copy the plan). Include:
  - The pipeline as an ASCII diagram: download → parse → extract → validate → build_graph → query → evaluate.
  - Per module: entry command, main functions, input files → output files, which module or function calls which.
  - Key variables, settings and environment variables that change behaviour (e.g. GEMINI_API_KEY, LLM provider switch, numeric tolerance, validation thresholds, metrics.yaml synonyms), and what each one changes.
  - File formats of data/parsed, data/facts, graph/kg.json, benchmark.json and results/.
  - One benchmark question traced end to end, naming every function it passes through.

## Roles
- Orchestrator (this session): plan, delegate, track progress in PROGRESS.md. Do not write bulk code yourself.
- Implementer (subagent, model: haiku): writes all code, tests and routine fixes. One milestone at a time, with the exact files and the acceptance check.
- Advisor (subagent, model: opus, read-only): only on escalation. Returns a diagnosis and a short plan, not full code.
- Verifier (subagent): Sonnet by default; Opus when the escalation rules below say so.

## Escalation (Implementer -> Advisor)
The Implementer is stuck if the same error or failing test survives 2 fix attempts, or 3 attempts pass with no progress, or a design decision affects multiple modules (schema, fact IDs, metric names). When stuck it stops and returns a STUCK report: goal, exact error, what was tried, relevant files, and its best hypothesis. Subagents cannot spawn subagents, so the Orchestrator relays the report to the Advisor and hands the Advisor's plan back to the Implementer. Never escalate for typos, missing imports or simple test fixes. Every Advisor decision goes into docs/decision-log.md.

## Verification loop (after every milestone)
1. Run pytest and the milestone's command. Pass only the failing output forward.
2. Sonnet Verifier checks the diff against the milestone spec and handoff.md. It also checks that every choice made in this milestone has a decision-log entry, and that Outcome fields of earlier entries were filled in where this milestone produced results. A milestone with no new decisions must say "no new decisions" in PROGRESS.md.
3. Use an Opus Verifier instead when: the change touches the schema, fact IDs, the XBRL gate, scoring math or secrets handling; or Sonnet has failed the same check twice; or the root cause is unclear; or this milestone needed the Advisor.
4. On failure, send a short defect list back to the Implementer. At most 3 loops per milestone; after that, stop and report the blocker.

## Code review and changes
Ponytail is on at full for all work. After each milestone passes verification, run the `ponytail:ponytail-review` skill on that milestone's diff. The Implementer applies only its "Must fix" and "Should fix" items, then re-run step 1 of the verification loop.

## Honesty rules (the task is judged on these)
- Never edit gold answers to match system output. Never tune prompts or rules on benchmark questions.
- Report metrics exactly as they come out.
- Spot-check at least 5 extracted facts per milestone from M4 on against the actual PDF page, and record the result in PROGRESS.md.

## Token discipline
- One milestone at a time with narrow context: pass file paths and diffs, not whole files or history.
- Keep every subagent report under 200 words.
- Do not re-read unchanged files. No exploratory refactors or unrequested features.
- Cache every LLM call to disk; never re-call for the same input.

## Stop conditions
Stop and report when all "Done when" items pass, or a milestone fails 3 verification loops, or a decision needs my input.
Stop before M2 if GEMINI_API_KEY or SEC_USER_AGENT is missing from .env.
Do not stop for gold-answer verification (I do it after 08:00) or for GitHub push (I do it).
At 08:00 IST, report status whatever state the build is in.

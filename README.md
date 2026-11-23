# Genloop SEC 10-K knowledge-graph QA

A knowledge graph built from the latest 10-K filing of 40 US public companies (4 sectors x 10). Questions are answered by traversing the graph, not by vector search over chunks. Every answer cites its document and PDF page, or abstains when the needed fact is not in the graph.

Scope: 40 companies, the latest 10-K of each (see `docs/decision-log.md` D-001 and D-043 for the fiscal-year rule; year labels follow each company's report period). Evaluated on a self-made 29-question benchmark. Honest results and failures are reported below.

## The 40 companies

Source: `config/companies.yaml`. Wells Fargo was swapped for Capital One (D-003, its financials sit in Exhibit 13).

| Sector | Companies (tickers) |
|---|---|
| Tech | AAPL, MSFT, GOOGL, AMZN, META, NVDA, ORCL, CRM, ADBE, INTC |
| Banks & Payments | JPM, BAC, C, COF, GS, MS, V, MA, AXP, PYPL |
| Consumer & Retail | WMT, COST, TGT, HD, PG, KO, PEP, MCD, NKE, SBUX |
| Healthcare | JNJ, PFE, MRK, ABBV, LLY, UNH, AMGN, BMY, ABT, CVS |

Fiscal year ends differ on purpose (AAPL and NVDA are late Sept and late Jan, MSFT is June, WMT is January). The graph labels each year by its report year.

## Architecture

Stages run in order: `download` (EDGAR HTML converted to PDF with headless Chrome, plus XBRL companyfacts) -> `parse` (pdfplumber text and statement tables per page) -> `extract` (rows matched to canonical metrics, each fact keeps doc, page and snippet, then gated against XBRL) -> `entities` (LLM extraction of people, segments, locations, auditor and employee count, admitted only if the literal text appears on the cited page) -> `graph` (NetworkX MultiDiGraph saved to `graph/kg.json`) -> `query` (rule planner first, LLM fallback, then traversal with abstain) -> `evaluate` (scores against the benchmark). The PDFs are the only source of facts. XBRL is a validation gate, never an answer source. Full diagram, per-module functions and a traced query: [docs/flow.md](docs/flow.md).

## Setup

Requirements: Python 3.13, macOS with Google Chrome at `/Applications/Google Chrome.app` (the PDF step uses it; the path is hard-coded in `src/download.py`).

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # pdfplumber, networkx, pyyaml, requests, python-dotenv, pytest
cp .env.example .env                   # then fill in the values
```

`.env` (gitignored; never commit it). Template: `.env.example`.

- `SEC_USER_AGENT` is required for `download`. SEC asks for a name and contact email. Quote the value because it contains spaces, e.g. `SEC_USER_AGENT="Your Name your@email.com"`.
- `GROQ_API_KEY` is the primary LLM (`openai/gpt-oss-120b`).
- `GEMINI_API_KEY` is the fallback LLM (`gemini-3.1-flash-lite`).
- Optional: `LLM_PROVIDER=groq|gemini` forces one provider; `GROQ_TPM` sets the Groq tokens-per-minute budget (default 7500).

No LLM key is needed to rebuild the graph, run queries that the rules can plan, or run the evaluation. Only uncached LLM calls need a key.

## Run steps (in order)

Each command is run from the repo root with the venv active.

1. **Download** (network, Chrome, `SEC_USER_AGENT`): `python -m src.download`
   Writes `data/raw_html/`, `data/pdfs/` (40 10-K PDFs), `data/xbrl/` and `data/filings.json`. The PDFs and XBRL JSON are gitignored and are re-downloaded by this step.
2. **Parse**: `python -m src.parse` (add `--reuse-pages` to rebuild statements from the page text already in `data/parsed/`, which needs no PDFs). Writes `data/parsed/{TICKER}.json`.
3. **Extract + validate**: `python -m src.extract` (add `--verbose` to print every fact). Needs `data/xbrl/` from step 1. Writes `data/facts/{TICKER}.json` (admitted) and `{TICKER}.rejected.json`, and prints the XBRL match rate.
4. **Entities** (LLM, cached): `python -m src.entities`. Writes `data/entities/`. Use `python -m src.entities --regate` to re-apply the grounding gate to cached LLM replies with no network and no key.
5. **Graph**: `python -m src.graph` (alias: `python -m src.build_graph`). Writes `graph/kg.json` and prints the XBRL match rate (947/947 compared at the last build).
6. **Query example**: `python -m src.query "What was Apple's revenue in fiscal 2025?"` (add `--json` for the structured answer). Expected output:
   ```
   Revenue (FY2025): AAPL FY2025 $416.16 billion
     validated: True
     fact ids: AAPL|Revenue|FY2025
     - AAPL|Revenue|FY2025: data/pdfs/AAPL.pdf p.49
   ```
   Questions the rules cannot plan go to the LLM planner. An abstain is printed as `Cannot answer (<reason>)`.
7. **Evaluate**: `python -m src.evaluate` writes `results/metrics.json` and `results/per_question.csv`.
8. **Tests**: `pytest` (196 tests).

### Rerunnable offline (no key, no network)

These read only committed data (`data/parsed`, `data/facts`, `data/entities`, `data/llm_cache`, `graph/kg.json`, `benchmark/`):

- `python -m src.parse --reuse-pages`
- `python -m src.entities --regate` (or plain `python -m src.entities`, which reads the cache first and makes no call on a full cache)
- `python -m src.graph`
- `python -m src.query "<question>"` for rule-plannable questions
- `python -m src.evaluate`
- `pytest`

`python -m src.extract` needs `data/xbrl/*.json`, which is gitignored. Run `python -m src.download` once first, or copy the files from a machine that has them.

### Fresh clone

A fresh clone plus the steps above reproduces the evaluation with no `.env`. Checked in a clean clone in a scratch directory: `pytest` gave 196 passed, `python -m src.evaluate` produced `results/metrics.json` and `results/per_question.csv` byte-identical to the committed files (md5 match), and `python -m src.graph` reproduced `graph/kg.json` byte-identical. `src.extract` reproduced the committed `data/facts` after copying `data/xbrl` in.

## Benchmark

File: `benchmark/benchmark.json` (`version` 1.0, key `items`), 29 questions: 10 `single_fact`, 10 `multi_hop`, 9 `cross_filing`. Each item has:

- `id`, `type`, `question`
- `answerable` (bool), `expected_behaviour` (`answer` or `abstain`). Three items expect abstention: Q06, Q10, Q20.
- `gold_answer` (text), `gold_value` (absolute USD, or a fraction for ratios), `gold_fact_ids` (for example `AAPL|Revenue|FY2026`)
- `docs` (PDF paths), `pages` (1-based), `evidence` (`{page, key, quote}`: the figure as printed on the cited page)
- `notes`, `verified` (bool)

Status: every item has `"verified": false`. The gold was written from the parsed PDF page text (`data/parsed`), not from `data/facts`, the graph or any system output (D-018, D-072). **No human has verified the gold yet.** The user does this check.

Selection caveat (D-072): the 29 questions were drafted by the builder, not sampled at random, and the builder chose them with the PDFs in view. Coverage is therefore not representative of all 10-K questions. Items were kept where the graph is known to lack a fact (Q08, Q09, Q25, Q28), so the benchmark is not tuned to graph coverage, but the score is not a population estimate.

Gold suspects (not edited; left for the gold check):

- Q07, Q19, Q21, Q26: gold lists a summary page, while the system cites the primary statement page that holds the same value (D-080). These four are counted as `wrong_page`, which is correct on value but misses the strict page check.
- Also noted in `benchmark/README.md`: Q08 (Merck total assets) has no "Total assets" label in the parsed text, checked by the balance identity instead; Q09 (Pfizer EPS) is on p108 even though extraction missed it; BAC FY2025 total assets differ between p65 (3,411,738) and p68 (3,410,412), and the cross-filing ranking does not depend on it.

## Results

Source: `results/metrics.json` (scorer version after D-080). Numbers as produced by `python -m src.evaluate`.

| Group | n | scored | correct | accuracy | precision | recall | doc hit | strict page hit | abstained (expected) |
|---|---|---|---|---|---|---|---|---|---|
| **overall** | 29 | 28 | 20 | **71.4%** (20/28) | 0.840 | 0.827 | 100% | 71.4% | 7 (3) |
| single_fact | 10 | 10 | 8 | 80.0% | 0.800 | 0.800 | 100% | 83.3% | 4 (2) |
| multi_hop | 10 | 9 | 7 | 77.8% | 1.000 | 1.000 | 100% | 62.5% | 1 (1) |
| cross_filing | 9 | 9 | 5 | 55.6% | 0.778 | 0.741 | 100% | 71.4% | 2 (0) |

- Q15 (multi_hop) is unscored: it has no checkable gold, so it is excluded from all means.
- Accuracy is value- or term-based. `wrong_page` rows count as correct for accuracy; the strict page hit is reported separately.
- Failures (8 incorrect rows): missing fact in graph, abstained (Q08, Q09, Q25, Q28); wrong value (Q13, Q27); wrong company (Q14, Q29). Plus 4 `wrong_page` rows (Q07, Q19, Q21, Q26) that are correct on value.

Caveats, stated plainly:

- **Scorer changed after the first run.** The first run gave 19/28 correct (67.9%), precision 0.817, recall 0.833. Verifier review found scorer bugs (Q16 was scored wrong although its answer is right; Q15 kept precision and recall with no gold). D-080 amended the scorer and the result became 20/28. The change was made after seeing the first scores. Gold was not edited, and the amendment is logged in D-080.
- **Small n.** 29 items, 28 scored. One question moves accuracy by about 3.6 points. The per-type cells are 9 or 10 items each.
- **Mixed LLM provenance.** Entity extraction and the planner fallback used Groq (`openai/gpt-oss-120b`) and Gemini (`gemini-3.1-flash-lite`). The cache holds 146 Groq and 50 Gemini replies (`data/llm_cache/`, at M4b it held 144 and 50). Entity records do not store the provider. Evaluation reads the cache only, so the numbers depend on those replies being the ones that were cached.
- **Residual scorer weakness.** The fallback for non-numeric answers can still match a gold number from a returned fact (D-080, "known loose point").

## Known gaps

- **Missing facts, abstain instead.** Many filers do not report GrossProfit, R&D or OperatingIncome as rows, so those are absent by design. Real misses include PFE EPS, C EPS, NVDA CapEx, and MRK and ABT balance totals (`PROGRESS.md`, M4 row). The system abstains on these.
- **Unvalidated facts.** 57 facts have no XBRL tag to compare against (`no_xbrl`) and are admitted unvalidated. Employee-count facts are LLM-extracted and unvalidated.
- **Auditor coverage.** Auditor is absent for 27 of 40 companies, including banks BAC, C, GS, V, MA, AXP and PYPL.
- **Executives and entity queries.** Apple has no `EXECUTIVE_OF` edges. A multi-company entity lookup abstains if any company lacks the edge. Multi-year ranges use only the first year.
- **Fiscal-year labels.** Years are labelled by report year (D-043). Many FY2025 values come from the prior-year column of the FY2026 10-K, not a separate filing.
- **Planner.** Rules first, LLM only when the rules fail; unknown metric or company abstains (D-075). Strict abstain costs coverage on unusual wording.
- **Benchmark.** Small (29), builder-drafted, not human-verified, four gold suspects. Cross-filing is the weakest type (55.6%).
- **Only the latest 10-K per company**, no 10-Q, no HTML fallback (task rule: PDF-only parsing).
- **Setup is macOS-specific.** The Chrome path in `src/download.py` is hard-coded.

## How AI tools were used

- **Claude Code (this repo's build).** Claude Code ran the build as orchestrator. Roles were set in `GOAL.md`: Haiku as implementer, Sonnet as verifier, Opus as advisor and escalation verifier (scoring, schema, fact IDs, XBRL gate, secrets). The decision log (`docs/decision-log.md`) records every design choice, including choices made by subagents. Verification was not run for every milestone: `PROGRESS.md` records that the verification loop and ponytail review were not run for M1 and M2, and that M8 scoring was reviewed by an Opus verifier (D-080).
- **Runtime LLMs (in the pipeline, free tier, cached).** Groq `openai/gpt-oss-120b` (primary, D-013) and Gemini `gemini-3.1-flash-lite` (fallback, D-071). They are used only for entity extraction (cover, segments, employees, auditor, officers) and for the planner fallback. No LLM reads or writes a numeric fact: numbers come from PDF table rows, and XBRL is compared, not copied.
- **What the human did.** Chose the filing type, the 40-company list and the Wells Fargo swap; approved the schema; owns the gold verification and the GitHub push. The human decisions are in `handoff.md`.
- **Known limits of the AI work.** Gold was drafted by AI from the PDFs and is not yet human-verified. The scorer was amended after seeing the first results (D-080). Read `docs/decision-log.md` before trusting any single number.

## Repo layout

| Path | Contents | Committed |
|---|---|---|
| `README.md` | this file | yes |
| `GOAL.md`, `handoff.md` | the spec and milestone list; the original plan | yes |
| `CLAUDE.md` | project memory: where things live, failure log | yes |
| `PROGRESS.md` | milestone status and open issues | yes |
| `docs/decision-log.md` | every design decision (D-001 onward) | yes |
| `docs/flow.md` | pipeline diagram, per-module functions, traced query | yes |
| `requirements.txt`, `.env.example`, `.gitignore` | dependencies, env template, ignores | yes |
| `config/companies.yaml` | 40 companies, CIK, sector, bank flag | yes |
| `config/metrics.yaml` | canonical metrics, synonyms, derived metrics | yes |
| `src/` | pipeline code (`download`, `parse`, `tables`, `extract`, `validate`, `entities`, `graph`, `build_graph` shim, `planner`, `query`, `evaluate`, `llm`, `config`) | yes |
| `tests/` | pytest suite (196 tests) | yes |
| `data/pdfs/` | 10-K PDFs (EDGAR HTML converted with Chrome) | no (re-downloaded) |
| `data/raw_html/` | raw EDGAR HTML | no |
| `data/xbrl/` | XBRL companyfacts JSON (about 175 MB) | no (re-downloaded) |
| `data/filings.json` | filing index: accession, dates, status, financials page | yes |
| `data/parsed/` | per-page text and statement rows per company | yes |
| `data/facts/` | admitted and rejected facts per company | yes |
| `data/entities/` | LLM entity records, admitted and rejected | yes |
| `data/llm_cache/` | cached LLM replies, keyed by hash of prompt | yes |
| `graph/kg.json` | the knowledge graph (node-link JSON) | yes |
| `benchmark/` | `benchmark.json` (29 items), `README.md` on how gold was made | yes |
| `results/` | `metrics.json`, `per_question.csv` | yes |
| `report/` | results PDF (see `handoff.md`) | PDF only |

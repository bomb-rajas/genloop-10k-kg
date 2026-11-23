# GenLoop: 10-K knowledge-graph QA

Builds a knowledge graph from the latest 10-K of 40 US public companies (4 sectors x 10) and answers questions by traversing the graph, not by vector search. Every answer cites its document and PDF page, or abstains when the fact is not in the graph. Repo: https://github.com/bomb-rajas/genloop-10k-kg

![GenLoop knowledge graph](kg-visualization/genloop-kg.png)

*Sectors, companies, facts and entities. [Open the interactive explorer](kg-visualization/explorer.html) (single file, works offline).*

## Quick start

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # optional: GROQ_API_KEY, GEMINI_API_KEY (only needed to rebuild entities)
.venv/bin/python -m src.query "What was Apple's total net sales in fiscal 2026?"
.venv/bin/python -m src.evaluate     # reproduces the results below from graph/kg.json, no keys
.venv/bin/python -m pytest -q        # 266 tests
```

## Run it step by step

**1. Set up** (the built graph `graph/kg.json` is already in the repo; no keys, downloads or build step needed):

```bash
git clone https://github.com/bomb-rajas/genloop-10k-kg.git && cd genloop-10k-kg
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Optional, only if you change `data/facts` or `data/entities`: rebuild the graph with `.venv/bin/python -m src.build_graph`.

**2. Ask a question** (answer, fact IDs, document and page):

```bash
.venv/bin/python -m src.query "What was Apple's net income in fiscal 2025?"
.venv/bin/python -m src.query "Which of Apple, Microsoft and Alphabet had the highest net income in fiscal 2025?"
.venv/bin/python -m src.query "Who audits Microsoft?"
.venv/bin/python -m src.query "What was Visa's gross profit in fiscal 2026?"   # not in the graph: abstains with a reason
.venv/bin/python -m src.query --json "What was Apple's net income in fiscal 2025?"   # full plan + citations as JSON
```

**3. Query the graph directly** (traverse nodes and edges, no search index):

```bash
.venv/bin/python - <<'PY'
from src import graph
G = graph.load_graph()                                  # NetworkX MultiDiGraph
print(G.nodes["AAPL"])                                  # Company node
for _, fact, e in G.out_edges("AAPL", data=True):       # Company -HAS_FACT-> Fact
    if e["rel"] == "HAS_FACT" and "NetIncome" in fact:
        n = G.nodes[fact]
        print(fact, n["value"], n["doc"], "p.", n["page"], "validated:", n["validated"])
PY
```

**4. Score the benchmark** (29 questions, writes `report/metrics.json` and `report/per_question.csv`):

```bash
.venv/bin/python -m src.evaluate
```

## Pipeline

| Step | Command | Output |
|---|---|---|
| 1. Download 10-K (HTML to PDF) + XBRL | `python -m src.download` | `data/pdfs`, `data/xbrl` |
| 2. Parse PDFs page by page | `python -m src.parse` | `data/parsed` |
| 3. Extract numeric facts from tables | `python -m src.extract` | `data/facts` |
| 4. Extract entities with an LLM | `python -m src.entities` | `data/entities` |
| 5. Build the graph | `python -m src.build_graph` | `graph/kg.json` |
| 6. Ask / evaluate | `python -m src.query "..."`, `python -m src.evaluate` | `report/` |

Plus `python scripts/render_kg.py` to regenerate the explorer.

## Repo map

| Folder | Contents |
|---|---|
| `config` | the 40 companies, metric definitions |
| `data` | `pdfs` (gitignored), `parsed` text, `facts` (numbers read from PDF tables), `entities` (people, auditor, HQ, segments extracted by LLM from text and grounded), `xbrl` (gitignored) |
| `graph` | `kg.json`, the built graph |
| `src` | pipeline, planner, query |
| `benchmark` | `benchmark.json` (29 questions with gold), `gold_review.md` |
| `report` | `metrics.json`, `per_question.csv` |
| `results` | `results.pdf` |
| `kg-visualization` | explorer and graph images |
| `scripts`, `tests` | report/render helpers, pytest suite |

## Results

29 questions, `report/metrics.json`: **27 correct of 28 scored** (1 has no checkable gold).

| | n | correct | accuracy (scored) | accuracy (all 29) |
|---|---|---|---|---|
| Overall | 29 | 27/28 | 96.4% | 93.1% |
| Single fact | 10 | 10/10 | 100% | 100% |
| Multi-hop | 10 | 8/9 | 88.9% | 80.0% |
| Cross-filing | 9 | 9/9 | 100% | 100% |

Precision 1.00, recall 1.00. 3 of 3 expected abstentions were correct.

Honest note: questions were chosen after seeing the extractor's known gaps, so results are likely optimistic; n=29 is small (one question is 3.4 points). Gold is AI-drafted and AI-reviewed (`verified: false`); the author verifies it by hand.

## Known gaps

- Metrics such as GrossProfit, R&D and OperatingIncome are missing for companies that do not report them as a line item.
- Multi-hop questions are the weakest type (80% over all; the miss is Q13, segment values are not stored).
- Fiscal-year labels can shift for retailers with 52/53-week years.
- Only the latest 10-K per company, so no long time series.

## XBRL (validation only)

XBRL is the SEC's machine-readable copy of a filing's numbers. The task asks for PDF-only parsing, so XBRL is used only to check the PDF-extracted facts: a fact is flagged validated when it matches XBRL for the same period (983/983 compared match). XBRL never supplies an answer.

## AI tools and where the author made the decisions

The author decided what to build and the rules it had to follow; AI wrote the code.

- The author wrote the project spec: the schema (Company, Sector, Filing, Fact, Metric, Period, Segment, Person, Org, Location), the fact ID format `TICKER|Metric|FY`, the 40 companies across 4 sectors, the folder layout and the timebox plan.
- The author set the hard rules: parse PDFs only (EDGAR HTML converted to PDF with headless Chrome, never parsed for facts); XBRL only to validate, never to supply answers; answer by graph traversal, not vector search; free LLM tiers only; gold is never edited to fit output.
- The author supplied the Groq and Gemini keys and chose Groq as primary with Gemini as fallback after testing which models worked.
- The author set the process: AI works as Implementer and Verifier, review and test after each milestone, honest failure analysis, question selection disclosed.
- The author asked for the blind second-model gold review and approved the planner and parser fixes after seeing the failure diagnosis.
- The author asked for the interactive KG explorer and the minimal results PDF, and published the repo.
- The author verifies the gold by hand.

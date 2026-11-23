"""Build report/results.html (+ results.pdf via headless Chrome) from results/ and data/facts/. Needs matplotlib."""
import csv, glob, io, json, subprocess, sys
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use("svg")
import matplotlib.pyplot as plt
import yaml

R = Path(__file__).resolve().parent.parent
m = json.load(open(R / "results/metrics.json"))
rows = list(csv.DictReader(open(R / "results/per_question.csv")))
INK, MUT, C1, C2, C3 = "#1f2933", "#6b7280", "#2b6cb0", "#dd8a1a", "#2f855a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": "#aaa", "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})

def svg(fig):
    b = io.StringIO(); fig.savefig(b, format="svg", bbox_inches="tight"); plt.close(fig)
    s = b.getvalue(); return s[s.index("<svg"):]

# 1 accuracy/precision/recall by type
names = ["overall", "single_fact", "multi_hop", "cross_filing"]
src = [m["overall"]] + [m["per_type"][t] for t in names[1:]]
fig, ax = plt.subplots(figsize=(3.6, 2.0))
w = .26
for i, (k, c) in enumerate([("accuracy", C1), ("precision", C2), ("recall", C3)]):
    xs = [j + (i - 1) * w for j in range(4)]; v = [s[k] for s in src]
    ax.bar(xs, v, w, color=c, label=k)
    for x, y in zip(xs, v): ax.text(x, y + .015, f"{y:.2f}".lstrip("0") if y < 1 else "1.0", ha="center", fontsize=5.8, color=INK)
ax.set_xticks(range(4)); ax.set_xticklabels([f"{n.replace('_', ' ')}\n({s['correct']}/{s['scored']})" for n, s in zip(names, src)])
ax.set_ylim(0, 1.12); ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(.5, 1.18), fontsize=7)
chart_metrics = svg(fig)

# 2 failure causes by type
labels = {"missing_fact_in_graph": "Fact missing from graph", "wrong_value": "Wrong value (planner)", "wrong_company": "Wrong company (alias/rank)"}
cnt = Counter((r["failure_category"], r["type"]) for r in rows if r["failure_category"] in labels)
fig, ax = plt.subplots(figsize=(3.6, 1.55))
left = [0] * len(labels)
for t, c in [("single_fact", C1), ("multi_hop", C2), ("cross_filing", C3)]:
    v = [cnt[(k, t)] for k in labels]
    ax.barh(list(labels.values()), v, left=left, color=c, label=t.replace("_", " "))
    left = [a + b for a, b in zip(left, v)]
ax.invert_yaxis(); ax.set_xticks(range(0, max(left) + 1)); ax.legend(frameon=False, fontsize=6.5, loc="lower right")
for y, n in enumerate(left): ax.text(n + .05, y, str(n), va="center", fontsize=7)
chart_fail = svg(fig)

# 3 coverage heatmap: company x metric
metrics = [x for x in ["Revenue", "GrossProfit", "OperatingIncome", "NetIncome", "EPS", "TotalAssets", "TotalLiabilities", "Equity", "OperatingCashFlow", "CapEx", "R&D", "Cash"]]
cfg = yaml.safe_load(open(R / "config/companies.yaml"))
cos = cfg["companies"] if isinstance(cfg, dict) else cfg
order = [c["ticker"] for c in cos]
have = {}
for f in glob.glob(str(R / "data/facts/*.json")):
    if f.endswith(".rejected.json"): continue
    for x in json.load(open(f)): have.setdefault(x["ticker"], {})[x["metric"]] = 1 if x.get("validated") else 0.5
mk = {t: [m_ for m_ in metrics] for t in order}
import numpy as np
M = np.array([[have.get(t, {}).get(k, np.nan) for t in order] for k in metrics])
fig, ax = plt.subplots(figsize=(7.4, 1.9))
cm = matplotlib.colors.ListedColormap(["#e8c27a", "#2f855a"]); cm.set_bad("#eef0f3")
ax.imshow(np.where(np.isnan(M), np.nan, M), cmap=cm, vmin=.5, vmax=1, aspect="auto")
ax.set_xticks(range(len(order))); ax.set_xticklabels(order, rotation=90, fontsize=5.5)
ax.set_yticks(range(len(metrics))); ax.set_yticklabels(metrics, fontsize=6.2)
ax.set_xticks(np.arange(-.5, len(order)), minor=True); ax.set_yticks(np.arange(-.5, len(metrics)), minor=True)
ax.grid(which="minor", color="white", lw=.8); ax.tick_params(which="both", length=0)
for s in ax.spines.values(): s.set_visible(False)
chart_heat = svg(fig)
n_have = int(np.sum(~np.isnan(M)))

o = m["overall"]
tiles = [(f"{o['accuracy']*100:.1f}%", f"accuracy ({o['correct']}/{o['scored']} scored)"), (f"{o['precision']:.2f} / {o['recall']:.2f}", "precision / recall"),
         ("947 / 947", "PDF facts matching XBRL"), (f"{o['page_strict_rate']*100:.0f}%", "citations on a valid page"), ("1,655 / 4,693", "graph nodes / edges")]
tiles_html = "".join(f'<div class="tile"><b>{a}</b><span>{b}</span></div>' for a, b in tiles)
pipe = ["10-K HTML<br>(EDGAR)", "PDF<br>(Chrome)", "Parse tables<br>(pdfplumber)", "Extract facts<br>PDF values only", "XBRL check<br>validate, never answer", "Knowledge graph<br>NetworkX", "Planner +<br>traversal", "Answer +<br>doc + page"]
pipe_html = '<span class="ar">&rarr;</span>'.join(f'<div class="st{" hl" if i in (4,) else ""}">{p}</div>' for i, p in enumerate(pipe))
rows_tab = "".join(f"<tr><td>{n.replace('_',' ')}</td><td>{s['n']}</td><td>{s['correct']}/{s['scored']}</td><td>{s['accuracy']*100:.1f}%</td><td>{s['precision']:.3f}</td><td>{s['recall']:.3f}</td><td>{s['abstained']} ({s['abstain_correct']}/{s['abstain_expected']})</td></tr>" for n, s in zip(names, src))

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>GenLoop Results</title><style>
@page{{size:A4;margin:11mm 12mm}}*{{box-sizing:border-box}}
body{{font:8.8pt/1.34 Helvetica,Arial,sans-serif;color:{INK};margin:0}}
header{{border-left:5px solid {C1};padding:1px 0 1px 9px;margin-bottom:6px}}
h1{{font-size:16pt;margin:0;letter-spacing:-.2px}}.sub{{color:{MUT};font-size:8.3pt}}
h2{{font-size:10.2pt;margin:9px 0 3px;color:{C1};border-bottom:1.5px solid #dbe4ee;padding-bottom:1px}}
p,ul{{margin:2px 0}}ul{{padding-left:14px}}li{{margin:1.5px 0}}
.tiles{{display:flex;gap:6px;margin:5px 0}}.tile{{flex:1;background:#f3f6fa;border-radius:5px;padding:5px 7px;text-align:center}}
.tile b{{display:block;font-size:12.5pt;color:{C1}}}.tile span{{font-size:7pt;color:{MUT}}}
.pipe{{display:flex;align-items:center;gap:2px;margin:5px 0}}.st{{flex:1;border:1px solid #c7d3e0;border-radius:4px;padding:4px 2px;text-align:center;font-size:6.9pt;background:#fff}}
.st.hl{{background:#fff6e5;border-color:{C2}}}.ar{{color:{MUT};font-size:9pt}}
.two{{display:flex;gap:12px;align-items:flex-start}}.two>div{{flex:1}}
table{{border-collapse:collapse;width:100%;font-size:7.8pt;margin:3px 0}}td,th{{border-bottom:1px solid #dde3ea;padding:2px 4px;text-align:right}}th{{color:{MUT};font-weight:600}}td:first-child,th:first-child{{text-align:left}}
.cap{{color:{MUT};font-size:7.3pt}}svg{{max-width:100%;height:auto}}.pb{{break-before:page}}
</style></head><body>
<header><h1>GenLoop: Financial Knowledge Graph QA</h1>
<div class="sub">Latest 10-K for 40 companies in 4 sectors, answered by graph traversal with document and page citations. 29-question benchmark. Numbers from results/metrics.json. Gold is AI-reviewed but not yet human-verified.</div></header>
<div class="tiles">{tiles_html}</div>
<div class="pipe">{pipe_html}</div>
<p class="cap">Facts are read from the PDFs only. XBRL is an independent check applied before a fact is admitted. It never supplies an answer value.</p>
<h2>Results</h2>
<div class="two"><div>{chart_metrics}</div><div>
<table><tr><th>Slice</th><th>n</th><th>Correct</th><th>Acc.</th><th>Prec.</th><th>Rec.</th><th>Abstain</th></tr>{rows_tab}</table>
<p class="cap">Q15 has no checkable gold and is excluded. Abstain = abstentions (correct / expected); all 3 deliberately unanswerable questions were refused. Doc hit {o['doc_hit_rate']:.2f}; strict page hit {o['page_strict_rate']:.3f} (cited page is a gold or acceptable page). With n=29 one question moves accuracy about 3.5 points; no confidence intervals.</p></div></div>
<h2>Methodology</h2>
<ul>
<li><b>PDF-only parsing.</b> EDGAR 10-K HTML is printed to PDF with headless Chrome and parsed with pdfplumber (tables, parentheses negatives, scale from the table header, multi-page tables, correct year column). Each fact stores doc, page and snippet; ID format TICKER|Metric|FY.</li>
<li><b>XBRL as a validation gate only.</b> XBRL (the SEC's machine-readable copy of the filing numbers) was not in the task brief; it was added as a check on our parsing. 947/947 compared facts match; 57 have no XBRL counterpart (22 derived TotalLiabilities); 0 rejected; 1,004 statement facts admitted.</li>
<li><b>Grounded LLM entity extraction.</b> Officers, auditor, HQ, segments, employees come from cited pages; an entity is admitted only if its name appears literally on the cited page (488 of 504). Providers were mixed (Groq then Gemini after a daily quota hit).</li>
<li><b>Query.</b> A rule-based planner builds a plan over the graph (company, metric, period, compare/rank/sum/growth); an LLM planner runs only if rules fail. No supporting fact means abstain with a reason.</li>
<li><b>Benchmark.</b> 10 single-fact, 10 multi-hop, 9 cross-filing (3 unanswerable by design). Gold was written from PDF page text, not from the graph. An independent blind re-derivation by a second model confirmed 26, corrected 0, flagged 3 as ambiguous.</li></ul>
<h2>Graph schema</h2><div style="text-align:center"><img src="../docs/kg/schema.png" style="max-width:88%;max-height:300px"></div><p class="cap">Fact-centric schema: each Fact node holds value, unit, period, doc, page, snippet and validated flag. Interactive explorer of all 1,655 nodes: docs/kg/explorer.html.</p><div class="pb"></div>
<h2>Where it fails</h2>
<div class="two"><div>{chart_fail}<p class="cap">8 of 28 scored questions are wrong; every one traces to a generic cause.</p></div><div><ul>
<li><b>Fact missing (4):</b> Merck total assets (no "Total assets" label in the PDF), Pfizer diluted EPS (heading line lost), Capital One revenue (no total line printed; equals net interest income + non-interest income).</li>
<li><b>Planner (4):</b> "Amazon" not recognised as a company alias (Q14, Q29); "higher revenue" read as a sum (PepsiCo vs Coca-Cola, $141.87B); largest-segment question lists all segments instead of ranking.</li></ul>
<p class="cap">Strict page check was 71% before the gold review added acceptable pages for the same filing (4 answers cited the primary statement instead of a summary page); 95% after. Accuracy is value-based and did not change.</p></div></div>
<h2>Fact coverage: what the graph holds</h2>
{chart_heat}
<p class="cap">{n_have} of {len(order)*len(metrics)} company-metric cells are filled (green = matches XBRL, amber = no XBRL tag to check). Grey cells are mostly metrics a company does not report (gross profit for banks, R&amp;D for retailers). Real parser misses: Merck/Abbott balance sheet, Citi/Visa/Pfizer EPS, NVIDIA CapEx.</p>
<h2>Other gaps</h2>
<ul>
<li><b>Entities are thin.</b> Auditor found for 13 of 40 (extraction window ends before the signature page), HQ for 28 (PDF text like "Atlanta,Georgia" fails the literal grounding check), no executives for 10 companies. Segments hold names only, not values.</li>
<li><b>Scope.</b> One 10-K per company: three income-statement years, no quarters, no restatements. Fiscal-year label is the year the period ends, so Home Depot "fiscal 2025" is stored as FY2026.</li>
<li><b>Evaluation honesty.</b> The scorer was amended after the first run (D-080: 19/28 became 20/28). Question selection was informed by the extractor's known gap list (D-072), so abstain results are likely optimistic. No held-out set yet.</li></ul>
<h2>Concrete improvements</h2>
<ul>
<li>Planner: register the bare company name as an alias; route "which/higher/largest" to ranking, summing only on "combined"/"sum"; add tests. Parser: prefix heading lines to EPS rows; keep unlabelled total rows after the equity block; add a bank revenue identity. Estimated effect is about 26/28, a projection to be confirmed on a held-out question set written before the fixes.</li>
<li>Entities: use the signature page for the auditor, normalise comma spacing before grounding, add per-entity provider logging, parse the segment note into segment facts.</li>
<li>Grow the benchmark beyond 29, write questions before inspecting system output, and finish human verification of gold.</li></ul>
</body></html>"""
(R / "report/results.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={R/'report/results.pdf'}", f"file://{R/'report/results.html'}"], check=True, capture_output=True)
print("ok")

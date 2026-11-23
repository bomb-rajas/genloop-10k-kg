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
hm = json.load(open(R / "results/heldout_after/metrics.json"))["overall"]
hrows = list(csv.DictReader(open(R / "results/heldout_after/per_question.csv")))
HB = 9  # results/heldout_baseline: 9/15 before the fixes
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
for i, (k, c) in enumerate([("accuracy_over_all", C1), ("precision", C2), ("recall", C3)]):
    xs = [j + (i - 1) * w for j in range(4)]; v = [s[k] for s in src]
    ax.bar(xs, v, w, color=c, label=k.replace("_over_all", " (of all n)"))
    for x, y in zip(xs, v): ax.text(x, y + .015, f"{y:.2f}".lstrip("0") if y < 1 else "1.0", ha="center", fontsize=5.8, color=INK)
ax.set_xticks(range(4)); ax.set_xticklabels([f"{n.replace('_', ' ')}\n({s['correct']}/{s['n']})" for n, s in zip(names, src)])
ax.set_ylim(0, 1.12); ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(.5, 1.18), fontsize=7)
chart_metrics = svg(fig)

# 2 failure causes: main benchmark vs held-out (current results)
labels = {"missing_fact_in_graph": "Fact missing from graph", "wrong_value": "Wrong value (planner)", "abstained_wrongly": "Wrongly abstained (fact missing)", "answered_unanswerable": "Unknown company not refused"}
cm_ = Counter(r["failure_category"] for r in rows); ch_ = Counter(r["failure_category"] for r in hrows)
fig, ax = plt.subplots(figsize=(3.6, 1.55))
ks = list(labels); y = range(len(ks))
ax.barh([i - .18 for i in y], [cm_[k] for k in ks], .36, color=C1, label="main (Q01-Q29)")
ax.barh([i + .18 for i in y], [ch_[k] for k in ks], .36, color=C2, label="held-out (H01-H15)")
ax.set_yticks(list(y)); ax.set_yticklabels(labels.values()); ax.invert_yaxis(); ax.set_xticks(range(0, 6)); ax.legend(frameon=False, fontsize=6.5, loc="lower right")
for i, k in enumerate(ks):
    for d, c in ((-.18, cm_[k]), (.18, ch_[k])): ax.text(c + .05, i + d, str(c), va="center", fontsize=7)
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
ho = hm
tiles = [(f"{o['accuracy_over_all']*100:.1f}%", f"accuracy over all 29 ({o['correct']}/29); {o['accuracy']*100:.1f}% of 28 scored"), (f"{o['precision']:.2f} / {o['recall']:.2f}", "precision / recall"),
         (f"{ho['correct']}/{ho['n']}", f"held-out accuracy (baseline {HB}/15)"), ("962 / 962", "PDF facts matching XBRL"), (f"{o['page_strict_rate']*100:.0f}%", "citations on a valid page"), ("1,684 / 4,793", "graph nodes / edges")]
tiles_html = "".join(f'<div class="tile"><b>{a}</b><span>{b}</span></div>' for a, b in tiles)
pipe = ["10-K HTML<br>(EDGAR)", "PDF<br>(Chrome)", "Parse tables<br>(pdfplumber)", "Extract facts<br>PDF values only", "XBRL check<br>validate, never answer", "Knowledge graph<br>NetworkX", "Planner +<br>traversal", "Answer +<br>doc + page"]
pipe_html = '<span class="ar">&rarr;</span>'.join(f'<div class="st{" hl" if i in (4,) else ""}">{p}</div>' for i, p in enumerate(pipe))
rows_tab = "".join(f"<tr><td>{n.replace('_',' ')}</td><td>{s['n']}</td><td>{s['correct']}/{s['n']}</td><td>{s['accuracy_over_all']*100:.1f}%</td><td>{s['accuracy']*100:.1f}%</td><td>{s['precision']:.3f}</td><td>{s['recall']:.3f}</td><td>{s['abstained']} ({s['abstain_correct']}/{s['abstain_expected']})</td></tr>" for n, s in zip(names, src))
rows_tab += f"<tr><td>held-out (15)</td><td>{ho['n']}</td><td>{ho['correct']}/{ho['n']}</td><td>{ho['accuracy_over_all']*100:.1f}%</td><td>{ho['accuracy']*100:.1f}%</td><td>{ho['precision']:.3f}</td><td>{ho['recall']:.3f}</td><td>{ho['abstained']} ({ho['abstain_correct']}/{ho['abstain_expected']})</td></tr>"

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
<div class="sub">Latest 10-K for 40 companies in 4 sectors, answered by graph traversal with document and page citations. 29-question benchmark. Numbers from results/metrics.json. Gold is AI-drafted and AI-reviewed, not human verified (verified: false).</div></header>
<div class="tiles">{tiles_html}</div>
<div class="pipe">{pipe_html}</div>
<p class="cap">Facts are read from the PDFs only. XBRL is an independent check applied before a fact is admitted. It never supplies an answer value.</p>
<h2>Results</h2>
<div class="two"><div>{chart_metrics}</div><div>
<table><tr><th>Slice</th><th>n</th><th>Correct</th><th>Acc. /n</th><th>Acc. /scored</th><th>Prec.</th><th>Rec.</th><th>Abstain</th></tr>{rows_tab}</table>
<p class="cap">Q15 has no checkable gold: accuracy over all 29 is the task-defined number (26/29), over the 28 scored 26/28. Held-out row: 15 questions written before the planner/parser fixes; baseline 9/15, after fixes 8/15 (no improvement; main-benchmark gains partly came from inspecting its failures). Abstain = abstentions (correct / expected); all 3 deliberately unanswerable questions were refused. Doc hit {o['doc_hit_rate']:.2f}; strict page hit {o['page_strict_rate']:.3f} (cited page is a gold or acceptable page). With n=29 one question moves accuracy about 3.5 points; no confidence intervals.</p></div></div>
<h2>Methodology</h2>
<ul>
<li><b>PDF-only parsing.</b> EDGAR 10-K HTML is printed to PDF with headless Chrome and parsed with pdfplumber (tables, parentheses negatives, scale from the table header, multi-page tables, correct year column). Each fact stores doc, page and snippet; ID format TICKER|Metric|FY.</li>
<li><b>XBRL as a validation gate only.</b> XBRL (the SEC's machine-readable copy of the filing numbers) was not in the task brief; it was added as a check on our parsing. 962/962 compared facts match; 67 have no XBRL counterpart; 0 rejected; 1,029 statement facts admitted.</li>
<li><b>Grounded LLM entity extraction.</b> Officers, auditor, HQ, segments, employees come from cited pages; an entity is admitted only if its name appears literally on the cited page (488 of 504). Providers were mixed (Groq then Gemini after a daily quota hit).</li>
<li><b>Query.</b> A rule-based planner builds a plan over the graph (company, metric, period, compare/rank/sum/growth); an LLM planner runs only if rules fail. No supporting fact means abstain with a reason.</li>
<li><b>Benchmark.</b> 10 single-fact, 10 multi-hop, 9 cross-filing (3 unanswerable by design). Gold was written from PDF page text, not from the graph. Gold is AI-drafted and AI-reviewed (blind re-derivation by a second model), not human verified. A 15-question held-out set was written before the fixes.</li></ul>
<h2>Graph schema</h2><div style="text-align:center"><img src="../docs/kg/schema.png" style="max-width:80%;max-height:200px"></div><p class="cap">Fact-centric schema: each Fact node holds value, unit, period, doc, page, snippet and validated flag. Interactive explorer of all 1,684 nodes: docs/kg/explorer.html.</p><div class="pb"></div>
<h2>Where it fails</h2>
<div class="two"><div>{chart_fail}<p class="cap">Current failures: main 3 incorrect of 29 (one unscored); held-out 7 of 15 incorrect.</p></div><div><ul>
<li><b>Main (26/29):</b> Q13 largest Apple geographic segment: segment values are not in the graph, so it lists all segments (wrong value). Q14 Amazon auditor is missing from the graph, so it abstains wrongly. Q15 is unscored.</li>
<li><b>Held-out (8/15; baseline 9/15):</b> difference, share-of-total and growth intents are not planned (H06 Amazon OCF minus capex, H07 BMY R&amp;D share, H08, H10 UNH growth read as a sum); "generated more" read as growth (H13, a regression); Amex operating cash flow missing (H11); unknown company Netflix not refused (H15).</li></ul>
<p class="cap">Strict page hit is 95.8% after the gold review added acceptable pages (D-081). The held-out set did not improve, so the main-benchmark gain is partly overfit to inspected failures.</p></div></div>
<h2>Fact coverage: what the graph holds</h2>
{chart_heat}
<p class="cap">{n_have} of {len(order)*len(metrics)} company-metric cells are filled (green = matches XBRL, amber = no XBRL tag to check). Grey cells are mostly metrics a company does not report (gross profit for banks, R&amp;D for retailers). Remaining parser miss: Amex operating cash flow (earlier misses for Merck/Abbott, Citi/Visa/Pfizer EPS and NVIDIA CapEx were fixed in D-084).</p>
<h2>Other gaps</h2>
<ul>
<li><b>Entities are thin.</b> Auditor found for 13 of 40 (extraction window ends before the signature page), HQ for 28 (PDF text like "Atlanta,Georgia" fails the literal grounding check), no executives for 10 companies. Segments hold names only, not values.</li>
<li><b>Scope.</b> One 10-K per company: three income-statement years, no quarters, no restatements. Fiscal-year label is the year the period ends, so Home Depot "fiscal 2025" is stored as FY2026.</li>
<li><b>Evaluation honesty.</b> The scorer was amended after the first run (D-080: 19/28 became 20/28). Question selection was informed by the extractor's known gap list (D-072), so abstain results are likely optimistic. Held-out: 9/15 baseline, 8/15 after fixes; both reported, n is small.</li></ul>
<h2>Concrete improvements</h2>
<ul>
<li>Planner: add difference, share-of-total and growth intents; stop reading \"generated more\" as growth; refuse questions naming a company outside the corpus. Query/graph: store segment values so \"largest segment\" can rank; extract the Amazon auditor and Amex operating cash flow. Re-check on a fresh held-out set written before the fixes (the current one has now been inspected).</li>
<li>Entities: use the signature page for the auditor, normalise comma spacing before grounding, add per-entity provider logging, parse the segment note into segment facts.</li>
<li>Grow the benchmark beyond 29, write questions before inspecting system output, and have a human verify the gold (it is AI-drafted and AI-reviewed only).</li></ul>
</body></html>"""
(R / "report/results.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={R/'report/results.pdf'}", f"file://{R/'report/results.html'}"], check=True, capture_output=True)
print("ok")

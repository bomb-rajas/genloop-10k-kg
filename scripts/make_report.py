"""Build results/results.pdf (2 pages, A4) from report/ and graph/. HTML goes to the system temp dir. Needs matplotlib, pyyaml."""
import base64, csv, io, json, re, subprocess, tempfile
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use("svg")
import matplotlib.pyplot as plt
import yaml

R = Path(__file__).resolve().parent.parent
m = json.load(open(R / "report/metrics.json"))
rows = list(csv.DictReader(open(R / "report/per_question.csv")))
by = {r["id"]: r for r in rows}
filings = json.load(open(R / "data/filings.json"))
companies = yaml.safe_load(open(R / "config/companies.yaml"))["companies"]
kg = json.load(open(R / "graph/kg.json"))
facts = [n for n in kg["nodes"] if n["node_type"] == "Fact"]
xb = Counter(f["xbrl_status"] for f in facts)
cnt = lambda rej: sum(len(json.load(open(f))["entities"]) for f in (R / "data/entities").glob("*.json") if ("rejected" in f.name) == rej)
n_ok, n_rej = cnt(False), cnt(True)
src = lambda rel, i: {e[i] for e in kg["edges"] if e["rel"] == rel}
aud, hq, execs = len(src("AUDITED_BY", "source")), len(src("HEADQUARTERED_IN", "source")), len(src("EXECUTIVE_OF", "target"))
o = m["overall"]
ids = lambda a, b: [f"Q{i:02d}" for i in range(a, b + 1)]
sc = lambda L: [by[i] for i in L if by[i]["failure_category"] != "unscored"]
cor = lambda L: sum(r["correct"] == "True" for r in sc(L))
a, b = cor(ids(1, 29)), len(sc(ids(1, 29)))
c45, n45 = cor(ids(45, 59)), len(sc(ids(45, 59)))

ACC, G = "#1f4e79", ["#bdbdbd", "#7a7a7a"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "svg.fonttype": "none"})
def svg(fig):
    s = io.StringIO(); fig.savefig(s, format="svg", bbox_inches="tight"); plt.close(fig)
    t = s.getvalue(); return t[t.index("<svg"):]

names = ["single_fact", "multi_hop", "cross_filing"]
fig, ax = plt.subplots(figsize=(3.6, 1.8)); w = .26
for i, (k, c) in enumerate([("accuracy_over_all", ACC), ("precision", G[0]), ("recall", G[1])]):
    xs = [j + (i - 1) * w for j in range(3)]; v = [m["per_type"][t][k] for t in names]
    ax.bar(xs, v, w, color=c, label=k.replace("_over_all", " (of all)"))
    for x, y in zip(xs, v): ax.text(x, y + .02, f"{y:.2f}", ha="center", fontsize=5.5)
ax.set_xticks(range(3)); ax.set_xticklabels([n.replace("_", " ") for n in names]); ax.set_ylim(0, 1.15); ax.set_yticks([])
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(.5, 1.2), fontsize=6.5)
chart1 = svg(fig)

fc = Counter(r["failure_category"] for r in rows if r["failure_category"] and r["failure_category"] not in ("unscored",) and not r["failure_category"].startswith("abstained_unans"))
fig, ax = plt.subplots(figsize=(3.2, 1.3))
ks = list(fc); ax.barh(ks, [fc[k] for k in ks], color=ACC, height=.55); ax.invert_yaxis()
for i, k in enumerate(ks): ax.text(fc[k] + .05, i, fc[k], va="center", fontsize=6)
ax.set_xticks([]); [ax.spines[s].set_visible(False) for s in ("top", "right", "bottom")]
chart2 = svg(fig)

def tr(name, d, ab=True):
    abst = f"{d['abstain_correct']}/{d['abstain_expected']}"
    return f"<tr><td>{name}</td><td>{d['n']}</td><td>{d['scored']}</td><td>{d['correct']}</td><td>{d['accuracy']:.1%}</td><td>{d['precision']:.3f}</td><td>{d['recall']:.3f}</td><td>{abst}</td></tr>"
table = tr("Overall", o) + "".join(tr(t, m["per_type"][t]) for t in names)

def short(n): return re.sub(r",? (Inc\.?|Corp\.?|Corporation|Group Inc\.|Company)$", "", n).replace(" Inc.", "")
sectors = list(dict.fromkeys(c["sector"] for c in companies))
blocks = ""
for s in sectors:
    cs = [c for c in companies if c["sector"] == s]
    blocks += f"<table class='co'><tr><th colspan=3>{s}</th></tr>" + "".join(
        f"<tr><td><b>{c['ticker']}</b></td><td>{short(c['name'])}</td><td>{filings[c['ticker']]['report_date']}</td></tr>" for c in cs) + "</table>"

q = lambda i: by[i]
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>GenLoop Results</title><style>
@page{{size:A4;margin:11mm}}body{{font:9.6pt/1.35 Helvetica,Arial,sans-serif;color:#111;margin:0}}
h1{{font-size:15pt;margin:0 0 2px}}h2{{font-size:10.5pt;margin:8px 0 2px;border-bottom:1px solid #999}}
p,ul{{margin:2px 0}}ul{{padding-left:15px}}li{{margin:1px 0}}
table{{border-collapse:collapse;margin:3px 0;font-size:9pt}}td,th{{border:1px solid #999;padding:1px 6px;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#eee}}
.s{{color:#555;font-size:8pt}}.row{{display:flex;gap:14px;align-items:flex-start}}svg{{max-width:100%;height:auto}}
.grid{{display:flex;gap:6px}}.co{{font-size:7.4pt;margin:2px 0;flex:1}}.co td,.co th{{padding:0 3px;text-align:left;border:0;border-bottom:.5px solid #ddd}}.co th{{background:none;border-bottom:1px solid #999;color:{ACC}}}
.pipe{{color:{ACC};font-size:8pt}}b.a{{color:{ACC}}}</style></head><body>
<h1>GenLoop: Financial Knowledge Graph QA, Results</h1>
<p class="s">40 companies, latest 10-K each, answered by graph traversal; {o['n']}-question benchmark. Gold is AI-drafted and AI-reviewed, not human-verified.</p>
<h2>Results</h2>
<div class="row"><table><tr><th>Slice</th><th>n</th><th>Scored</th><th>Correct</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>Abstained (correct/expected)</th></tr>{table}</table><div style="flex:none;width:330px">{chart1}</div></div>
<p class="s">Accuracy is correct/scored; over all {o['n']} it is {o['correct']}/{o['n']} = {o['accuracy_over_all']:.1%}. Q15 is unscored (no checkable gold). Q30-Q59 were written after earlier planner fixes, so Q01-Q29 ({a}/{b}) is optimistic; Q45-Q59 is the cleanest estimate: {c45}/{n45}.</p>
<h2>Methodology</h2>
<p class="pipe">10-K HTML &rarr; Chrome PDF &rarr; pdfplumber facts &rarr; XBRL check &rarr; NetworkX graph &rarr; rule planner (LLM fallback) &rarr; cited answer or abstain</p>
<ul>
<li><b>PDF-only parsing.</b> EDGAR 10-Ks printed to PDF with headless Chrome, parsed with pdfplumber; each fact keeps doc, page and snippet.</li>
<li><b>XBRL as a validation gate only.</b> {xb['match']}/{xb['match']} compared facts match; {xb['no_xbrl']} have no XBRL counterpart. It never supplies an answer.</li>
<li><b>Grounded LLM entity extraction.</b> An entity is admitted only if its name appears literally on the cited page: {n_ok} of {n_ok + n_rej}.</li>
<li><b>Graph and query.</b> NetworkX graph of {len(kg['nodes'])} nodes; a rule planner builds the query, an LLM planner runs only if rules fail; no supporting fact means abstain.</li>
<li><b>Benchmark.</b> Written from PDF page text, not from the graph, to avoid circularity.</li></ul>
<h2>Companies used (ticker, name, period end of the 10-K)</h2>
<div class="grid">{blocks}</div>
<h2>Gaps, with examples</h2>
<ul>
<li><b>Q13</b> largest Apple geographic segment: segment values are not stored, so it lists all five names instead of Americas ($198,083M).</li>
<li><b>Q14</b> largest of four tech firms and its auditor: Amazon's auditor (Ernst &amp; Young) is not in the graph, so the answer abstains wrongly.</li>
<li><b>Q53</b> Meta capex plus R&amp;D: sum of two different metrics is unsupported; returns capex $69.69B only (gold $127,063M).</li>
<li><b>Q54, Q55</b> Home Depot and Target: fiscal-year label is the year the period ends, so "fiscal 2025" returns the prior year (HD margin 13.49% vs gold 12.69%; HD cash flow $19.81B vs $16.325B).</li>
<li><b>Q59</b> BAC vs Citi liabilities: values correct, cited page not in gold (wrong_page). <b>Q15</b> is unscored (no checkable gold).</li>
<li>Thin entities: auditor for {aud}/40, headquarters {hq}/40, executives missing for {40 - execs} companies.</li>
<li>Gold is not human-verified; the scorer was amended once after the first run; n is small (one question is about {100/o['n']:.1f} points).</li></ul>
<div class="row"><div style="flex:none;width:260px">{chart2}</div><p class="s" style="align-self:center">Current failures by category (unanswerable-by-design abstentions excluded).</p></div>
<h2>Improvements</h2>
<ul><li> store segment values; fix the fiscal-year label; plan multi-metric sums; read the auditor from the signature page; log the LLM provider per entity.</li></ul>
<h2>With more time</h2>
<ul><li>Human-verified gold and a larger benchmark written before inspecting system output; confidence intervals.</li></ul>
</body></html>"""
tmp = Path(tempfile.mkdtemp()) / "results.html"; tmp.write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={R/'results/results.pdf'}", f"file://{tmp}"], check=True, capture_output=True)
print("ok", fc, a, b, c45, n45, aud, hq, execs)

"""Render graph/kg.json to docs/kg/ (interactive HTML via vis-network, static PNGs via matplotlib).
Run: .venv/bin/python scripts/render_kg.py   (deps: requirements-viz.txt)"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.graph import load_graph  # noqa: E402

OUT = ROOT / "docs" / "kg"
EGO = ["AAPL", "JPM", "WMT", "JNJ", "MSFT"]
# Okabe-Ito colourblind-safe
TYPE_COL = {"Sector": "#000000", "Company": "#0072B2", "Segment": "#009E73", "Location": "#E69F00",
            "Organization": "#CC79A7", "Person": "#56B4E9", "Fact": "#999999", "Metric": "#D55E00",
            "Period": "#F0E442", "Filing": "#7F7F7F"}
SECTOR_COL = ["#0072B2", "#D55E00", "#F0E442", "#444444"]  # distinct from entity-type colours
CDN = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"

G = load_graph(ROOT / "graph" / "kg.json")
nt = lambda n: G.nodes[n]["node_type"]  # noqa: E731
sectors = sorted(n for n in G if nt(n) == "Sector")
sec_col = {s: SECTOR_COL[i % 4] for i, s in enumerate(sectors)}
company_sector = {u: v for u, v, d in G.edges(data=True) if d["rel"] == "IN_SECTOR"}
fact_count = Counter(u for u, v, d in G.edges(data=True) if d["rel"] == "HAS_FACT")


def label(n):
    d = G.nodes[n]
    t = d["node_type"]
    if t == "Fact":
        return f"{d['metric']} FY{d['fiscal_year']}"
    if t == "Company":
        return n
    if t == "Metric":
        return d["name"]
    if t == "Period":
        return f"FY{d['fiscal_year']}"
    if t == "Filing":
        return "10-K " + str(d["fiscal_year"])
    return d["name"]


def tip(n):
    d = G.nodes[n]
    t = d["node_type"]
    lines = [f"{t}: {label(n)}"]
    if t == "Fact":
        lines += [f"value: {d['value']:,} {d['unit']}", f"period end: {d['period_end']}"]
    if t == "Company":
        lines += [d["name"], f"sector: {d['sector']}", f"facts: {fact_count[n]}"]
    if d.get("role"):
        lines.append(f"role: {d['role']}")
    if d.get("doc"):
        lines.append(f"doc: {d['doc']}  page: {d.get('page')}")
    if d.get("snippet"):
        lines.append(f"“{d['snippet'][:160]}”")
    return "\n".join(lines)


def node_size(n):
    return 28 if nt(n) == "Company" and False else None


def vis_node(n, collapsed=False):
    t = nt(n)
    col = sec_col[company_sector[n]] if t == "Company" and collapsed else TYPE_COL[t]
    if t == "Sector":
        col = sec_col[n]
    v = {"id": n, "label": label(n), "title": tip(n), "color": col, "group": t}
    if t == "Sector":
        v.update(size=45, shape="box", font={"size": 22, "color": "#ffffff"}, widthConstraint=False)
    elif t == "Company":
        c = fact_count[n]
        v.update(size=12 + c * 0.45, label=f"{n} ({c} facts)" if collapsed else n, shape="dot")
    elif t == "Fact":
        v.update(size=7, shape="dot", font={"size": 0 if False else 11})
    elif t in ("Metric", "Period", "Filing"):
        v.update(size=14, shape="diamond" if t == "Metric" else "square")
        if t == "Period":
            v["font"] = {"color": "#333"}
    else:
        v.update(size=8 if t == "Person" else 12, shape="dot")
    return v


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>%(title)s</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="%(cdn)s"></script>
<style>body{margin:0;font-family:system-ui,sans-serif}#net{height:100vh}
#ui{position:fixed;top:8px;left:8px;background:#fffffff0;padding:8px 10px;border-radius:6px;box-shadow:0 1px 4px #0004;font-size:13px;max-width:260px}
#ui input{width:100%%;box-sizing:border-box;margin:4px 0}.sw{display:inline-block;width:11px;height:11px;border-radius:50%%;margin-right:5px}
.vis-tooltip{white-space:pre-wrap!important;max-width:420px}</style></head><body>
<div id="ui"><b>%(title)s</b><br>%(stats)s<input id="q" placeholder="search node (Enter)"><div id="leg">%(legend)s</div>
<small>%(note)s</small></div><div id="net"></div>
<script>
const nodes=new vis.DataSet(%(nodes)s),edges=new vis.DataSet(%(edges)s);
const net=new vis.Network(document.getElementById('net'),{nodes,edges},{
 nodes:{borderWidth:1,font:{size:13}},
 edges:{arrows:{to:{scaleFactor:.4}},color:{color:'#9aa',opacity:.7},font:{size:9,align:'middle',strokeWidth:3},smooth:false,width:.8},
 physics:{solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-%(grav)d,springLength:%(spring)d,springConstant:.06,avoidOverlap:.8},
  stabilization:{iterations:600,fit:true}},interaction:{hover:true,tooltipDelay:100}});
net.once('stabilizationIterationsDone',()=>{net.setOptions({physics:false});net.fit()});
document.getElementById('q').addEventListener('keydown',e=>{if(e.key!=='Enter')return;
 const s=e.target.value.toLowerCase();const m=nodes.get().find(n=>n.label.toLowerCase().includes(s));
 if(m){net.selectNodes([m.id]);net.focus(m.id,{scale:1.2,animation:true})}});
</script></body></html>"""


def legend(types):
    return "".join(f'<div><span class="sw" style="background:{TYPE_COL[t]}"></span>{t}</div>' for t in types)


def write_html(name, title, nodes, edges, note, grav=60, spring=110):
    tc = Counter(n["group"] for n in nodes)
    stats = f"{len(nodes)} nodes, {len(edges)} edges"
    html = PAGE % dict(title=title, cdn=CDN, stats=stats, legend=legend(tc), note=note,
                       nodes=json.dumps(nodes), edges=json.dumps(edges), grav=grav, spring=spring)
    (OUT / name).write_text(html)


def ve(u, v, rel):
    return {"from": u, "to": v, "label": rel}


def overview_sub():
    keep = {n for n in G if nt(n) in ("Sector", "Company", "Segment", "Location", "Organization", "Person")}
    H = G.subgraph(keep)
    return H


def build_overview():
    H = overview_sub()
    nodes = [vis_node(n, True) for n in H]
    edges = [ve(u, v, d["rel"]) for u, v, d in H.edges(data=True)]
    write_html("overview.html", "GenLoop KG overview", nodes, edges,
               "Facts collapsed: company size = fact count. Colour: company = sector, entities = type. Hover for doc/page/snippet.",
               grav=70, spring=90)
    return H


def ego(t, include_filing=False):
    keep = {t}
    for u, v, d in G.edges(data=True):
        if t in (u, v):
            keep |= {u, v}
    facts = [n for n in keep if nt(n) == "Fact"]
    for f in facts:
        keep |= set(G.successors(f))
    keep = {n for n in keep if nt(n) != "Filing"}
    return G.subgraph(keep)


def build_ego_html(t):
    H = ego(t)
    nodes = [vis_node(n) for n in H]
    edges = [ve(u, v, d["rel"]) for u, v, d in H.edges(data=True)]
    write_html(f"company_{t}.html", f"{t} ego graph", nodes, edges,
               "Company -> Fact -> Metric / Period provenance chain. Hover a Fact for value, page and snippet.",
               grav=40, spring=70)


EXPLORER = (Path(__file__).parent / "explorer_template.html").read_text()


# ---------- PNG ----------
def png(overview_H):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch

    def finish(fig, ax, name, types):
        ax.axis("off")
        ax.legend(handles=[Line2D([], [], marker="o", ls="", color=TYPE_COL[t], label=t) for t in types]
                  + ([Line2D([], [], marker="o", ls="", color=c, label=f"{s.split('|')[-1]} (sector + its companies)") for s, c in sec_col.items()] if name == "overview.png" else []),
                  loc="lower left", fontsize=10)
        fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
        plt.close(fig)

    # overview: sectors centre; each sector's companies on arc; entities (excl. Person) around company
    H = overview_H.copy()
    H.remove_nodes_from([n for n in list(H) if nt(n) == "Person"])
    pos = {}
    ns = len(sectors)
    for i, s in enumerate(sectors):
        a = 2 * math.pi * i / ns + math.pi / 4
        sc = (3.2 * math.cos(a), 3.2 * math.sin(a))
        pos[s] = (1.3 * math.cos(a), 1.3 * math.sin(a))
        cos = sorted(c for c, sx in company_sector.items() if sx == s)
        for j, c in enumerate(cos):
            b = a + (j - (len(cos) - 1) / 2) * (2 * math.pi / ns * 0.9 / len(cos))
            r = 4.2 + (j % 2) * 1.1
            pos[c] = (r * math.cos(b), r * math.sin(b))
            ents = [e for e in H.successors(c) if nt(e) != "Sector"]
            ents = [e for e in ents if H.in_degree(e) == 1]  # shared hubs (exchanges, auditors) placed later
            for k, e in enumerate(sorted(ents)):
                off = (k - (len(ents) - 1) / 2) * 0.22
                rr = r + 0.9 + (k % 2) * 0.4
                pos[e] = (rr * math.cos(b + off / 1.6), rr * math.sin(b + off / 1.6))
    # shared entities (e.g. Nasdaq) get placed at mean of neighbours
    for n in H:
        if n not in pos:
            nb = [pos[m] for m in list(H.predecessors(n)) if m in pos]
            pos[n] = (sum(x for x, _ in nb) / len(nb), sum(y for _, y in nb) / len(nb)) if nb else (0, 0)
    import networkx as nx
    fig, ax = plt.subplots(figsize=(22, 22))
    nx.draw_networkx_edges(H, pos, ax=ax, edge_color="#bbbbbb", width=0.6, arrows=False)
    for n in H:
        t = nt(n)
        col = sec_col[n] if t == "Sector" else sec_col[company_sector[n]] if t == "Company" else TYPE_COL[t]
        sz = {"Sector": 6500, "Company": 380}.get(t, 70)
        ax.scatter(*pos[n], s=sz, c=col, edgecolors="k", linewidths=0.5, zorder=3)
        if t in ("Sector", "Company"):
            ax.annotate(n.split("|")[-1] if t == "Sector" else n, pos[n], ha="center", va="center", zorder=4,
                        fontsize=12 if t == "Sector" else 8, color="k" if sec_col.get(n) == "#F0E442" else "w" if t == "Sector" else "k",
                        fontweight="bold" if t == "Sector" else "normal",
                        xytext=(0, 0 if t == "Sector" else 11), textcoords="offset points")
    ax.set_title("GenLoop knowledge graph: sectors, companies, segments, locations, organizations "
                 f"({H.number_of_nodes()} nodes; officers and facts omitted)", fontsize=16)
    finish(fig, ax, "overview.png", ["Segment", "Location", "Organization"])
    # sector legend note: company colour = sector colour
    # schema
    tcount = Counter(nt(n) for n in G)
    rels = Counter((nt(u), d["rel"], nt(v)) for u, v, d in G.edges(data=True))
    sp = {"Sector": (0, 4), "Company": (0, 2), "Filing": (-5, 2), "Fact": (-5, 0), "Metric": (-8, -2),
          "Period": (-3, -2), "Person": (5, 4), "Segment": (5, 2), "Location": (5, 0), "Organization": (5, -2)}
    sp = {"Sector": (4, 8), "Company": (4, 4), "Filing": (-2, 6), "Fact": (-2, 2), "Metric": (-6.5, -1),
          "Period": (0, -1), "Person": (10, 7), "Segment": (10, 4), "Location": (10, 0.5), "Organization": (10, -3)}
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(-8, 13); ax.set_ylim(-4, 9.5)
    for n, (x, y) in sp.items():
        ax.add_patch(FancyBboxPatch((x - 1.3, y - 0.45), 2.6, 0.9, boxstyle="round,pad=0.05",
                                    fc=TYPE_COL[n], ec="k", zorder=3, alpha=0.9))
        ax.text(x, y, f"{n}\n{tcount[n]:,} nodes", ha="center", va="center", fontsize=11, zorder=4,
                color="w" if n in ("Sector", "Company", "Metric") else "k", fontweight="bold")
    grp = Counter()
    for (a, r, b), c in rels.items():
        grp[(a, b)] += 1
    seen = Counter()
    for (a, r, b), c in sorted(rels.items()):
        (x1, y1), (x2, y2) = sp[a], sp[b]
        k = seen[(a, b)]; seen[(a, b)] += 1
        n_here = grp[(a, b)]
        if a == b:  # self loop (COMPUTED_FROM): draw a small arc above the box
            ax.annotate("", (x1 + 0.6, y1 + 0.5), (x1 - 0.6, y1 + 0.5), zorder=2,
                        arrowprops=dict(arrowstyle="-|>", connectionstyle="arc3,rad=-1.6", color="#444"))
            ax.text(x1 - 0.2, y1 + 1.5, f"{r} ({c})", ha="center", fontsize=10, bbox=dict(fc="w", ec="none", pad=1))
            continue
        rad = 0.0 if n_here == 1 else [-0.3, 0.0, 0.3][k] if n_here == 3 else [-0.22, 0.22][k]
        ax.annotate("", (x2, y2), (x1, y1), zorder=2, arrowprops=dict(
            arrowstyle="-|>", color="#444", shrinkA=26, shrinkB=26, connectionstyle=f"arc3,rad={rad}", lw=1.4))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        off = rad * L * 0.5
        tt = 0.5 if n_here == 1 else 0.6
        cx, cy = mx + rad * dy, my - rad * dx
        ax.text((1-tt)**2*x1 + 2*tt*(1-tt)*cx + tt**2*x2, (1-tt)**2*y1 + 2*tt*(1-tt)*cy + tt**2*y2, f"{r} ({c})", ha="center", va="center",
                fontsize=10, zorder=5, bbox=dict(fc="w", ec="none", pad=1.2, alpha=0.9))
    ax.set_title(f"GenLoop KG schema: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges", fontsize=16)
    ax.axis("off")
    fig.savefig(OUT / "schema.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    # ego AAPL: columns company+entities | facts | metrics | periods
    t = "AAPL"
    H = ego(t)
    facts = sorted((n for n in H if nt(n) == "Fact"), key=lambda n: (H.nodes[n]["metric"], -H.nodes[n]["fiscal_year"]))
    ents = sorted(n for n in H if nt(n) not in ("Fact", "Metric", "Period", "Company"))
    mets = sorted({m for f in facts for m in H.successors(f) if nt(m) == "Metric"}, key=lambda m: label(m))
    pers = sorted(n for n in H if nt(n) == "Period")
    pos = {t: (-4.5, 0)}
    def col(items, x):
        for i, n in enumerate(items):
            pos[n] = (x, (len(items) - 1) / 2 - i)
    col(ents, -9); col(facts, 4); col(mets, 8)
    for i, p in enumerate(pers):
        pos[p] = (12, (len(pers) - 1) / 2 - i)
    h = max(len(facts), len(ents), len(mets), len(pers))
    fig, ax = plt.subplots(figsize=(20, max(8, h * 0.42)))
    for u, v, d in H.edges(data=True):
        if u in pos and v in pos:
            ax.annotate("", pos[v], pos[u], arrowprops=dict(arrowstyle="-", color="#cccccc" if d["rel"] == "HAS_FACT" else "#888", lw=0.7), zorder=1)
    for n in H:
        tt = nt(n)
        x, y = pos[n]
        ax.scatter(x, y, s=500 if tt == "Company" else 60, c=TYPE_COL[tt], edgecolors="k", linewidths=0.5, zorder=3)
        if tt == "Fact":
            d = H.nodes[n]
            v = f"{d['value']:,.0f}" if abs(d['value']) >= 1000 else f"{d['value']:g}"
            txt = f"{d['metric']} FY{d['fiscal_year']}: {v} {d['unit']} (p.{d['page']})"
            ax.text(x - 0.12, y, txt, ha="right", va="center", fontsize=7)
        elif tt == "Company":
            ax.text(x, y + 0.5, f"{n}  ({len(facts)} facts)", ha="center", fontsize=13, fontweight="bold")
        elif tt in ("Metric", "Period"):
            ax.text(x + 0.12, y, label(n) if tt == "Metric" else label(n) + " " + H.nodes[n]["period_end"], ha="left", va="center", fontsize=8)
        else:
            ax.text(x - 0.12, y, f"{label(n)} [{G.edges[(t, n, 0)]['rel'] if G.has_edge(t, n) else 'EXECUTIVE_OF'}]", ha="right", va="center", fontsize=7)
    ax.set_xlim(-13, 15)
    ax.set_title("AAPL ego graph: Company -> Fact -> Metric / Period (entities on the left)", fontsize=14)
    finish(fig, ax, "ego_AAPL.png", ["Company", "Fact", "Metric", "Period", "Person", "Segment", "Location", "Organization"])


def build_explorer():
    """Single-file interactive explorer: whole kg.json + vis-network inlined (works on file://, offline)."""
    lib = ROOT / ".cache" / "vis-network-9.1.9.min.js"
    if not lib.exists():
        import urllib.request
        lib.parent.mkdir(exist_ok=True)
        lib.write_bytes(urllib.request.urlopen(CDN, timeout=60).read())
    raw = json.loads((ROOT / "graph" / "kg.json").read_text())
    data = {"nodes": raw["nodes"], "edges": [[e["source"], e["target"], e["rel"]] for e in raw["edges"]],
            "colors": TYPE_COL, "sectorColors": sec_col}
    js = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")  # noqa: E731
    html = (EXPLORER.replace("__LIB__", lib.read_text().replace("</script", "<\\/script"))
            .replace("__DATA__", js(data)))
    (OUT / "explorer.html").write_text(html)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    build_explorer()
    H = build_overview()
    for t in EGO:
        build_ego_html(t)
    png(H)
    print({p.name: p.stat().st_size for p in sorted(OUT.iterdir())})


if __name__ == "__main__":
    main()

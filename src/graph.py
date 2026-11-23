"""Build the knowledge graph graph/kg.json (NetworkX MultiDiGraph, node_link JSON).

Input: data/facts/{T}.json (admitted facts only; *.rejected.json is never read) and
data/entities/{T}.json (grounded entities only; a missing or unreadable file is skipped).
Edges carry attr `rel`; nodes carry attr `node_type`. Derived metrics (NetMargin, GrossMargin)
are Metric nodes with COMPUTED_FROM edges; their values are never stored (computed at query time).
Run: python -m src.graph
"""
import json
from collections import Counter

import networkx as nx

from src.config import (DATA_DIR, ENTITIES_DIR, FACTS_DIR, GRAPH_DIR, load_companies,
                        load_metrics)

GRAPH_PATH = GRAPH_DIR / "kg.json"
FILINGS_PATH = DATA_DIR / "filings.json"
FACT_REQUIRED = ("doc", "page", "value", "unit", "period", "validated")


def sector_id(name):
    return f"SEC|{name}"


def metric_id(name):
    return f"M|{name}"


def period_id(ticker, fy, period_end):
    return f"PD|{ticker}|FY{fy}|{period_end}"


def _add_fact(G, row, filing_id):
    """Add one Fact node with its HAS_FACT, OF_METRIC, FOR_PERIOD and REPORTS edges."""
    pid = period_id(row["ticker"], row["fiscal_year"], row["period_end"])
    attrs = dict(row, node_type="Fact", period=pid)
    missing = [k for k in FACT_REQUIRED if attrs.get(k) is None]
    if missing:
        raise ValueError(f"Fact {row['id']} missing {missing}")
    if row["id"] in G:
        raise ValueError(f"duplicate fact id {row['id']}")
    if metric_id(row["metric"]) not in G:
        raise ValueError(f"fact {row['id']}: unknown metric {row['metric']}")
    if pid not in G:
        G.add_node(pid, node_type="Period", ticker=row["ticker"], fiscal_year=row["fiscal_year"],
                   period_end=row["period_end"])
    G.add_node(row["id"], **attrs)
    G.add_edge(row["ticker"], row["id"], rel="HAS_FACT")
    G.add_edge(row["id"], metric_id(row["metric"]), rel="OF_METRIC")
    G.add_edge(row["id"], pid, rel="FOR_PERIOD")
    G.add_edge(filing_id, row["id"], rel="REPORTS")


def _statement_row(rec):
    return dict(id=rec["id"], ticker=rec["ticker"], metric=rec["metric"],
                fiscal_year=rec["period"]["fiscal_year"], period_end=rec["period"]["period_end"],
                value=rec["value"], unit=rec["unit"], scale=rec.get("scale"),
                as_reported_label=rec.get("as_reported_label"), doc=rec["doc"], page=rec["page"],
                snippet=rec.get("snippet"), method=rec.get("method"), validated=rec["validated"],
                xbrl_status=rec.get("xbrl_status"), xbrl_tag=rec.get("xbrl_tag"),
                xbrl_value=rec.get("xbrl_value"))


def _entity_fact_row(e, ticker, filing):
    fy = int(e["id"].rsplit("|", 1)[1][2:])  # id is TICKER|Employees|FYyyyy
    period_end = filing["report_date"] if fy == int(filing["report_date"][:4]) else None
    return dict(id=e["id"], ticker=ticker, metric=e["id"].split("|")[1], fiscal_year=fy, period_end=period_end,
                value=e["value"], unit=e["unit"], scale=None, as_reported_label=None,
                doc=e["doc"], page=e["page"], snippet=e["snippet"], method="entity",
                validated=False, xbrl_status=None, xbrl_tag=None, xbrl_value=None)


def _add_entities(G, ticker, data, filing):
    for e in data.get("entities", []):
        if e.get("grounded") is not True:
            continue
        if e["type"] == "Fact":
            _add_fact(G, _entity_fact_row(e, ticker, filing), filing["id"])
            continue
        nid = e["id"]
        if nid in G and G.nodes[nid]["node_type"] != e["type"]:
            raise ValueError(f"entity id {nid} used as {G.nodes[nid]['node_type']} and {e['type']}")
        if nid not in G:
            G.add_node(nid, node_type=e["type"], name=e["name"], role=e.get("role"),
                       doc=e["doc"], page=e["page"], snippet=e["snippet"])
        prov = dict(rel=e["relation"], doc=e["doc"], page=e["page"], snippet=e["snippet"])
        if e["type"] == "Person":
            G.add_edge(nid, ticker, title=e.get("role"), **prov)
        else:
            G.add_edge(ticker, nid, **prov)


def build_graph(companies, metrics, facts_dir, entities_dir, filings):
    """companies: config list; metrics: metrics.yaml dict; filings: {ticker: filings.json entry}."""
    G = nx.MultiDiGraph()
    for c in companies:
        t = c["ticker"]
        G.add_node(t, node_type="Company", ticker=t, name=c["name"], cik=c.get("cik"),
                   sector=c["sector"], fiscal_year_end=c.get("fiscal_year_end"),
                   is_bank=c.get("is_bank", False))
        G.add_node(sector_id(c["sector"]), node_type="Sector", name=c["sector"])
        G.add_edge(t, sector_id(c["sector"]), rel="IN_SECTOR")
    for m in metrics["metrics"] + metrics.get("count_metrics", []):
        G.add_node(metric_id(m["name"]), node_type="Metric", name=m["name"],
                   synonyms=m.get("synonyms", []), category=m.get("category"),
                   statement=m.get("statement"), applies_to=m.get("applies_to"), derived=False)
    for d in metrics.get("derived", []):
        G.add_node(metric_id(d["name"]), node_type="Metric", name=d["name"],
                   applies_to=d.get("applies_to"), derived=True, formula=d["formula"])
        for inp in d["computed_from"]:
            if metric_id(inp) not in G:
                raise ValueError(f"derived {d['name']} uses unknown metric {inp}")
            G.add_edge(metric_id(d["name"]), metric_id(inp), rel="COMPUTED_FROM", formula=d["formula"])

    for c in companies:
        t = c["ticker"]
        f = filings.get(t)
        if f is None:
            raise ValueError(f"{t} has no entry in filings.json")
        fid = f"FIL|{f['accession']}"
        G.add_node(fid, node_type="Filing", doc=f["pdf"], accession=f["accession"],
                   report_date=f["report_date"], fiscal_year=int(f["report_date"][:4]))
        G.add_edge(t, fid, rel="FILED")
        filing = dict(f, id=fid)
        with open(facts_dir / f"{t}.json", encoding="utf-8") as fh:
            for rec in json.load(fh):
                if rec["doc"] != f["pdf"]:
                    raise ValueError(f"fact {rec['id']} doc {rec['doc']} != filing {f['pdf']}")
                _add_fact(G, _statement_row(rec), fid)
        ent_path = entities_dir / f"{t}.json"
        if ent_path.exists():
            try:
                with open(ent_path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except json.JSONDecodeError as err:
                print(f"WARN skipping unreadable {ent_path}: {err}")
                continue
            _add_entities(G, t, data, filing)
    return G


def save_graph(G, path=GRAPH_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(G, edges="edges")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))


def load_graph(path=GRAPH_PATH):
    with open(path, encoding="utf-8") as fh:
        return nx.node_link_graph(json.load(fh), edges="edges")


def neighbors(G, node, rel, direction="out"):
    if direction == "out":
        return [v for _, v, d in G.out_edges(node, data=True) if d["rel"] == rel]
    return [u for u, _, d in G.in_edges(node, data=True) if d["rel"] == rel]


def facts_of(G, ticker, metric, fy=None):
    return [f for f in neighbors(G, ticker, "HAS_FACT")
            if G.nodes[f]["metric"] == metric and (fy is None or G.nodes[f]["fiscal_year"] == fy)]


def sector_members(G, sector):
    return neighbors(G, sector_id(sector), "IN_SECTOR", direction="in")


def report(G, companies, metrics, facts_dir):
    print("Nodes:", dict(Counter(d["node_type"] for _, d in G.nodes(data=True))))
    print("Edges:", dict(Counter(d["rel"] for _, _, d in G.edges(data=True))))
    stmt = [d for _, d in G.nodes(data=True) if d["node_type"] == "Fact" and d["method"] != "entity"]
    compared = [d for d in stmt if d["xbrl_status"] not in (None, "no_xbrl")]
    matched = [d for d in compared if d["xbrl_status"] == "match"]
    no_xbrl = sum(d["xbrl_status"] == "no_xbrl" for d in stmt)
    rejected = 0
    for p in facts_dir.glob("*.rejected.json"):
        with open(p, encoding="utf-8") as fh:
            rejected += len(json.load(fh))
    print(f"XBRL match: {len(matched)}/{len(compared)} compared "
          f"({100 * len(matched) / max(len(compared), 1):.1f}%); no_xbrl {no_xbrl}; rejected {rejected}")
    facts = [(d["ticker"], d["metric"]) for _, d in G.nodes(data=True) if d["node_type"] == "Fact"]
    have = set(facts)
    per_sector = Counter(G.nodes[t]["sector"] for t, _ in facts)
    print("Facts per sector:", dict(per_sector), "total", len(facts))
    is_bank = {c["ticker"]: c.get("is_bank", False) for c in companies}
    for m in metrics["metrics"] + metrics.get("count_metrics", []):
        tickers = [c["ticker"] for c in companies
                   if not (m.get("applies_to") == "nonbank" and is_bank[c["ticker"]])]
        missing = [t for t in tickers if (t, m["name"]) not in have]
        if missing:
            print(f"Missing {m['name']} ({len(missing)}): {','.join(missing)}")


def main():
    companies = load_companies()
    metrics = load_metrics()
    with open(FILINGS_PATH, encoding="utf-8") as fh:
        filings = json.load(fh)
    G = build_graph(companies, metrics, FACTS_DIR, ENTITIES_DIR, filings)
    save_graph(G)
    report(G, companies, metrics, FACTS_DIR)
    size = GRAPH_PATH.stat().st_size
    print(f"Wrote {GRAPH_PATH} ({size / 1e6:.2f} MB, limit 20 MB)")
    assert size < 20 * 1024 * 1024, "graph/kg.json exceeds 20 MB"


if __name__ == "__main__":
    main()

"""Offline tests for src/graph.py: fact/entity nodes, rejected and ungrounded exclusion, derived edges, roundtrip, helpers."""
import json

import pytest

from src import graph as g

COMPANIES = [
    {"ticker": "AAA", "name": "Alpha", "cik": "1", "sector": "Tech", "is_bank": False},
    {"ticker": "BBB", "name": "Beta", "cik": "2", "sector": "Banks", "is_bank": True},
]
METRICS = {
    "metrics": [
        {"name": "Revenue", "synonyms": ["Sales"], "category": "income", "statement": "IS", "applies_to": "all"},
        {"name": "NetIncome", "synonyms": [], "category": "income", "statement": "IS", "applies_to": "all"},
    ],
    "count_metrics": [{"name": "Employees", "applies_to": "all"}],
    "derived": [{"name": "NetMargin", "computed_from": ["NetIncome", "Revenue"], "formula": "NetIncome / Revenue", "applies_to": "all"}],
}
FILINGS = {
    "AAA": {"accession": "0001", "report_date": "2025-09-27", "pdf": "data/pdfs/AAA.pdf"},
    "BBB": {"accession": "0002", "report_date": "2025-12-31", "pdf": "data/pdfs/BBB.pdf"},
}


def _fact(ticker, metric, fy, value, validated=True, doc=None, end=None):
    return {"id": f"{ticker}|{metric}|FY{fy}", "ticker": ticker, "metric": metric,
            "value": value, "unit": "USD", "scale": 1, "as_reported_label": metric,
            "period": {"fiscal_year": fy, "period_end": end or f"{fy}-09-27"},
            "doc": doc or f"data/pdfs/{ticker}.pdf", "page": 10, "snippet": "x",
            "method": "pdf_table", "validated": validated,
            "xbrl_status": "match", "xbrl_value": value, "xbrl_tag": "T"}


def _write_dirs(root, layout):
    facts, ents = root / "facts", root / "entities"
    facts.mkdir()
    ents.mkdir()
    (facts / "AAA.json").write_text(json.dumps([
        _fact("AAA", "Revenue", 2025, 100, end="2025-09-27"),
        _fact("AAA", "NetIncome", 2025, 10, validated=False),
    ]))
    (facts / "BBB.json").write_text(json.dumps([_fact("BBB", "Revenue", 2025, 50, end="2025-12-31")]))
    (facts / "AAA.rejected.json").write_text(json.dumps([_fact("AAA", "Revenue", 2024, 999)]))
    if layout == "full":
        (ents / "AAA.json").write_text(json.dumps({"ticker": "AAA", "entities": [
            {"id": "PERSON|tim", "type": "Person", "name": "Tim", "relation": "EXECUTIVE_OF", "role": "CEO",
             "doc": "data/pdfs/AAA.pdf", "page": 5, "snippet": "CEO", "grounded": True},
            {"id": "SEG|americas", "type": "Segment", "name": "Americas", "relation": "HAS_SEGMENT",
             "role": None, "doc": "data/pdfs/AAA.pdf", "page": 4, "snippet": "seg", "grounded": True},
            {"id": "SEG|ghost", "type": "Segment", "name": "Ghost", "relation": "HAS_SEGMENT",
             "role": None, "doc": "data/pdfs/AAA.pdf", "page": 4, "snippet": "none", "grounded": False},
            {"id": "AAA|Employees|FY2025", "type": "Fact", "name": "Employees", "relation": "EMPLOYS_COUNT",
             "value": 1200, "unit": "count", "doc": "data/pdfs/AAA.pdf", "page": 4, "snippet": "1,200",
             "grounded": True},
        ]}))
        (ents / "BBB.json").write_text("{not json")  # unreadable: skipped with WARN
    return facts, ents


def _build(tmp_path, layout="full"):
    facts, ents = _write_dirs(tmp_path, layout)
    return g.build_graph(COMPANIES, METRICS, facts, ents, FILINGS)


@pytest.fixture(params=["full", "no_entities"])
def G(request, tmp_path):
    return _build(tmp_path, request.param)


def test_fact_required_attrs(G):
    facts = [d for _, d in G.nodes(data=True) if d["node_type"] == "Fact"]
    assert facts
    for d in facts:
        for k in g.FACT_REQUIRED:
            assert d[k] is not None, (d["id"], k)


def test_rejected_excluded(G):
    assert "AAA|Revenue|FY2024" not in G
    assert "AAA|Revenue|FY2025" in G


def test_ungrounded_entity_excluded(tmp_path):
    G = _build(tmp_path, "full")
    assert "SEG|ghost" not in G
    assert "SEG|americas" in G


def test_missing_or_unreadable_entities_tolerated(tmp_path):
    G = _build(tmp_path, "no_entities")
    assert G.nodes["AAA"]["node_type"] == "Company"
    assert not [n for n, d in G.nodes(data=True) if d["node_type"] == "Person"]


def test_entity_relations_and_employees_fact(tmp_path):
    G = _build(tmp_path, "full")
    assert G.has_edge("PERSON|tim", "AAA")
    assert any(d["rel"] == "HAS_SEGMENT" for _, _, d in G.out_edges("AAA", data=True))
    assert G.nodes["AAA|Employees|FY2025"]["validated"] is False
    assert G.nodes["AAA|Employees|FY2025"]["metric"] == "Employees"


def test_derived_metric_edges_and_no_values(G):
    edges = {(u, v) for u, v, d in G.edges(data=True) if d["rel"] == "COMPUTED_FROM"}
    assert edges == {("M|NetMargin", "M|NetIncome"), ("M|NetMargin", "M|Revenue")}
    assert G.nodes["M|NetMargin"]["derived"] is True
    assert not [n for n, d in G.nodes(data=True) if d["node_type"] == "Fact" and d["metric"] == "NetMargin"]


def test_fact_missing_required_attr_fails(tmp_path):
    facts, ents = _write_dirs(tmp_path, "no_entities")
    rows = json.loads((facts / "BBB.json").read_text())
    rows[0]["validated"] = None
    (facts / "BBB.json").write_text(json.dumps(rows))
    with pytest.raises(ValueError, match="missing"):
        g.build_graph(COMPANIES, METRICS, facts, ents, FILINGS)


def test_helpers_and_roundtrip(G, tmp_path):
    fid = g.facts_of(G, "AAA", "Revenue", fy=2025)
    assert fid == ["AAA|Revenue|FY2025"]
    assert g.facts_of(G, "AAA", "Revenue", fy=2024) == []
    assert g.facts_of(G, "AAA", "NetIncome") == ["AAA|NetIncome|FY2025"]
    assert g.sector_members(G, "Banks") == ["BBB"]
    assert g.neighbors(G, "AAA|Revenue|FY2025", "FOR_PERIOD") == ["PD|AAA|FY2025|2025-09-27"]
    path = tmp_path / "kg.json"
    g.save_graph(G, path)
    H = g.load_graph(path)
    assert sorted(H.nodes) == sorted(G.nodes)
    assert H.number_of_edges() == G.number_of_edges()
    assert g.facts_of(H, "AAA", "Revenue", fy=2025) == ["AAA|Revenue|FY2025"]

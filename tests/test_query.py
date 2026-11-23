"""M6 query tests: synthetic graph, stubbed LLM, no network."""
import json

import networkx as nx
import pytest

from src import graph as g
from src import planner, query

COMPANIES = [dict(ticker=t, name=n, sector=s, is_bank=b) for t, n, s, b in [
    ("AAA", "Alpha Corp", "Tech", False), ("BBB", "Beta Inc", "Tech", False), ("CCC", "Gamma Bancorp", "Banks", True),
    ("DDD", "Delta Holdings", "Banks", True)]]
METRICS = {"metrics": [dict(name=n, synonyms=[]) for n in ("Revenue", "NetIncome", "GrossProfit", "TotalAssets")],
           "count_metrics": [dict(name="Employees", synonyms=[])],
           "derived": [dict(name="NetMargin"), dict(name="GrossMargin")]}
VALS = {  # (ticker, metric, fy): value
    **{("AAA", "Revenue", 2024): 100e9, ("AAA", "Revenue", 2025): 120e9, ("AAA", "NetIncome", 2025): 30e9,
       ("AAA", "NetIncome", 2024): 20e9, ("AAA", "GrossProfit", 2025): 60e9, ("AAA", "Employees", 2025): 5000},
    ("BBB", "Revenue", 2025): 200e9, ("BBB", "NetIncome", 2025): 10e9,
    ("CCC", "TotalAssets", 2025): 900e9, ("DDD", "TotalAssets", 2025): 500e9, ("CCC", "Revenue", 2025): 50e9}


def build():
    G = nx.MultiDiGraph()
    G.add_node(g.metric_id("NetMargin"), node_type="Metric", formula="NetIncome / Revenue")
    G.add_node(g.metric_id("GrossMargin"), node_type="Metric", formula="GrossProfit / Revenue")
    for c in COMPANIES:
        G.add_node(c["ticker"], node_type="Company", name=c["name"], sector=c["sector"])
        G.add_node(g.sector_id(c["sector"]), node_type="Sector", name=c["sector"])
        G.add_edge(c["ticker"], g.sector_id(c["sector"]), rel="IN_SECTOR")
    for (t, m, fy), v in VALS.items():
        fid = f"{t}|{m}|FY{fy}"
        G.add_node(fid, node_type="Fact", ticker=t, metric=m, fiscal_year=fy, value=v, unit="count" if m == "Employees" else "USD",
                   doc=f"{t}.pdf", page=3, snippet="s", validated=m != "Employees")
        G.add_edge(t, fid, rel="HAS_FACT")
    G.add_node("LOC|x", node_type="Location", name="Springfield", doc="AAA.pdf", page=1, snippet="hq")
    G.add_edge("AAA", "LOC|x", rel="HEADQUARTERED_IN")
    G.add_node("ORG|aud", node_type="Organization", name="Audit LLP", doc="CCC.pdf", page=2, snippet="a")
    G.add_edge("CCC", "ORG|aud", rel="AUDITED_BY")
    G.add_node("P|1", node_type="Person", name="Ann Lee", role="Chief Executive Officer", doc="AAA.pdf", page=4, snippet="p")
    G.add_edge("P|1", "AAA", rel="EXECUTIVE_OF", title="Chief Executive Officer")
    return G


@pytest.fixture(scope="module")
def env():
    return build(), planner.Lexicon(COMPANIES, METRICS)


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("LLM called")
    monkeypatch.setattr(planner.llm, "complete", boom)


def ask(env, q):
    return query.answer(q, *env)


def test_lookup_and_default_year(env):
    a = ask(env, "What was Alpha's revenue?")
    assert a["value"] == 120e9 and a["fact_ids"] == ["AAA|Revenue|FY2025"] and a["validated"] is True
    assert a["citations"][0]["doc"] == "AAA.pdf" and "$120.00 billion" in a["answer"] and not a["abstained"]
    assert ask(env, "Alpha revenue in fiscal 2024")["value"] == 100e9


def test_unvalidated_flag(env):
    assert ask(env, "How many employees does Alpha have?")["validated"] is False


def test_compare_rank_sector(env):
    a = ask(env, "Compare revenue of Alpha and Beta")
    assert a["value"] == {"AAA": 120e9, "BBB": 200e9} and len(a["fact_ids"]) == 2
    a = ask(env, "Which tech company has the highest revenue?")
    assert a["value"] == 200e9 and "BBB" in a["answer"]
    assert ask(env, "Which bank has the lowest total assets?")["value"] == 500e9
    a = ask(env, "Rank banks by revenue")  # DDD lacks revenue: lenient with flag
    assert a["incomplete"] and a["missing"] == {"DDD": "no_fact"}
    assert ask(env, "Difference in revenue between Alpha and Beta")["value"] == 80e9


def test_aggregate_and_growth(env):
    assert ask(env, "Total revenue of Alpha and Beta")["value"] == 320e9
    a = ask(env, "Sum of Alpha revenue FY2024 and FY2025")
    assert a["value"] == 220e9 and len(a["fact_ids"]) == 2
    a = ask(env, "Alpha revenue growth in fiscal 2025")
    assert a["value"] == pytest.approx(20.0) and a["unit"] == "%" and len(a["fact_ids"]) == 2
    assert ask(env, "Change in Alpha revenue FY2025")["value"] == 20e9


def test_derived(env):
    a = ask(env, "What is Alpha's net margin in FY2025?")
    assert a["value"] == pytest.approx(25.0) and set(a["fact_ids"]) == {"AAA|NetIncome|FY2025", "AAA|Revenue|FY2025"}
    assert ask(env, "Alpha gross margin")["value"] == pytest.approx(50.0)
    assert ask(env, "Ratio of net income to revenue for Alpha")["unit"] == "x"
    assert ask(env, "Which tech company has the highest net margin?")["value"] == pytest.approx(25.0)


def test_entity(env):
    assert "Springfield" in ask(env, "Where is Alpha headquartered?")["answer"]
    a = ask(env, "Who is the CEO of Alpha?")
    assert "Ann Lee" in a["answer"] and "P|1" in a["fact_ids"]
    a = ask(env, "Who audits the bank with the highest total assets?")  # multi-hop
    assert "Audit LLP" in a["answer"] and "CCC|TotalAssets|FY2025" in a["fact_ids"] and "ORG|aud" in a["fact_ids"]
    a = ask(env, "Headquarters of the tech company with the highest revenue")
    assert a["abstained"] and a["reason"] == "no_fact"  # BBB has no HQ edge: abstain, not guess


@pytest.mark.parametrize("q,reason", [
    ("What was Alpha revenue in fiscal 2030?", "unsupported_period"),
    ("What was Alpha gross profit in fiscal 2024?", "no_fact"),
    ("What was Beta revenue in 2024?", "unsupported_period"),
    ("What was Zorbix revenue?", "unknown_company"),
    ("What is Alpha's income?", "ambiguous"),
    ("Alpha total assets", "no_fact"),
])
def test_abstain(env, q, reason):
    a = ask(env, q)
    assert a["abstained"] and a["reason"] == reason and a["fact_ids"] == [] and a["value"] is None


def test_llm_not_called_when_rules_succeed(env):
    assert ask(env, "Alpha revenue")["abstained"] is False  # autouse stub raises if LLM touched


def test_llm_fallback_and_validation(env, monkeypatch):
    lex = env[1]
    good = dict(intent="lookup", companies=["AAA"], metric="Revenue", years=[2025])
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(good))
    assert ask(env, "Gimme the thing for the first one")["value"] == 120e9
    for bad, reason in [(dict(good, companies=["ZZZ"]), "unknown_company"), (dict(good, metric="Bogus"), "plan_failed"),
                        (dict(good, sector="Space"), "plan_failed"), (dict(good, op="median"), "plan_failed"),
                        (dict(good, intent="compare"), "plan_failed")]:
        monkeypatch.setattr(planner.llm, "complete", lambda *a, _b=bad, **k: json.dumps(_b))
        assert planner.make_plan("zzz qqq", lex)[1][0] == reason
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: "not json")
    assert planner.make_plan("zzz qqq", lex)[1][0] == "plan_failed"

    def fail(*a, **k):
        raise RuntimeError("no key")
    monkeypatch.setattr(planner.llm, "complete", fail)
    assert ask(env, "blah blah")["reason"] == "plan_failed"


def test_cash_flow_qualifiers(env):
    for q in ("Free cash flow yield of Alpha", "What is Alpha's cash flow?"):
        a = ask(env, q)
        assert a["abstained"] and a["reason"] == "unsupported_metric" and a["value"] is None  # no substitute metric
    for q in ("Alpha operating cash flow", "Alpha cash flow from operations", "Alpha cash from operations"):
        assert planner.make_plan(q, env[1])[0]["metric"] == "OperatingCashFlow"


def test_growth_verb(env):
    a = ask(env, "How much did Alpha's revenue grow in fiscal 2025?")
    assert a["value"] == pytest.approx(20.0) and a["unit"] == "%"  # not the level (120e9)


def test_rank_mixed_fiscal_years_named_in_text(env):
    G = env[0].copy()  # DDD only has FY2024 revenue, so the open rank mixes FYs
    G.add_node("DDD|Revenue|FY2024", node_type="Fact", ticker="DDD", metric="Revenue", fiscal_year=2024, value=30e9,
               unit="USD", doc="DDD.pdf", page=3, snippet="s", validated=True)
    G.add_edge("DDD", "DDD|Revenue|FY2024", rel="HAS_FACT")
    a = query.answer("Rank banks by revenue", G, env[1])
    assert a["mixed_years"] is True and not a["abstained"]
    assert "CCC FY2025" in a["answer"] and "DDD FY2024" in a["answer"]

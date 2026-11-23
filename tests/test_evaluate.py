"""M8 scorer tests: hand-computed cases on a tiny synthetic graph, no network, no LLM."""
import networkx as nx
import pytest

from src import evaluate as ev
from src import llm, planner, query

G = nx.MultiDiGraph()
G.add_node("AMZN", node_type="Company", name="Amazon.com Inc.")
G.add_node("PEP", node_type="Company", name="PepsiCo Inc.")
G.add_node("AMZN|Revenue|FY2025", doc="data/pdfs/AMZN.pdf", page=58, value=716924e6)
G.add_node("AMZN|NetIncome|FY2025", doc="data/pdfs/AMZN.pdf", page=60)
G.add_node("PEP|Revenue|FY2025", doc="data/pdfs/PEP.pdf", page=105, value=93925e6)


def item(**kw):
    base = dict(id="T", type="single_fact", question="q", gold_answer="g", gold_value=None, gold_fact_ids=[],
                docs=["data/pdfs/AMZN.pdf"], pages=[58], expected_behaviour="answer")
    return {**base, **kw}


def res(**kw):
    base = dict(abstained=False, answer="", value=None, unit=None, fact_ids=[], citations=[], reason=None)
    return {**base, **kw}


def cite(doc, page):
    return dict(doc=doc, page=page)


# normalisation: suffixes and punctuation dropped on both sides
def test_norm_company_pairs():
    assert ev.norm("Amazon.com, Inc.") == ev.norm("Amazon.com Inc.") == "amazon com"
    assert ev.norm("PepsiCo") == ev.norm("PepsiCo Inc.") == "pepsico"


# tolerance: 0.5% relative, edges exact in float
def test_numeric_tolerance_edges():
    assert ev.numeric_ok(201, None, 200)       # exactly 0.5% above
    assert not ev.numeric_ok(201.02, None, 200)
    assert ev.numeric_ok(199, None, 200)       # exactly 0.5% below
    assert not ev.numeric_ok(198.9, None, 200)
    assert not ev.numeric_ok(None, None, 200)
    assert not ev.numeric_ok({"AMZN": 1}, None, 200)
    assert not ev.numeric_ok(200, None, None)


def test_numeric_unit_scaling():
    assert ev.numeric_ok(478.834, "USD", 478834e6)          # quoted in billions
    assert ev.numeric_ok(478834, "USD", 478834e6)           # quoted in millions
    assert ev.numeric_ok(65.47, "%", 0.654735)  # 65.47% vs 0.654735 fraction
    assert not ev.numeric_ok(65.47, None, 0.654735)         # no % unit: no scaling


# fact precision / recall
def test_precision_recall_partial():
    it = item(gold_fact_ids=["AMZN|Revenue|FY2025", "AMZN|NetIncome|FY2025"], gold_value=716924e6)
    r = ev.score(it, res(answer="AMZN: 716924", value=716924e6, unit="USD",
                         fact_ids=["AMZN|Revenue|FY2025", "PEP|Revenue|FY2025"],
                         citations=[cite("data/pdfs/AMZN.pdf", 58)]), G)
    assert r["precision"] == 0.5 and r["recall"] == 0.5
    assert r["correct"] is True and r["page_hit_strict"] is True and r["doc_hit"] is True


def test_empty_gold_facts_excluded():
    # text-only gold (entity name): fact P/R not scorable
    r = ev.score(item(gold_fact_ids=["Americas"]), res(answer="Americas"), G)
    assert r["precision"] is None and r["recall"] is None


def test_answered_with_no_facts_is_zero_precision_and_recall():
    it = item(gold_fact_ids=["AMZN|Revenue|FY2025"], gold_value=716924e6)
    r = ev.score(it, res(answer="nothing", value=None), G)
    assert r["precision"] == 0.0 and r["recall"] == 0.0 and r["correct"] is False


# abstain gold
def test_abstain_gold_correct_only_when_abstained():
    it = item(expected_behaviour="abstain", gold_fact_ids=["BAC|TotalAssets|FY2026"])
    ok = ev.score(it, res(abstained=True, reason="no_fact"), G)
    assert ok["correct"] is True and ok["precision"] == 1.0 and ok["recall"] == 1.0
    assert ok["failure_category"] == "abstained_unanswerable"
    bad = ev.score(it, res(answer="x", fact_ids=["AMZN|Revenue|FY2025"]), G)
    assert bad["correct"] is False and bad["precision"] == 0.0 and bad["recall"] == 1.0
    assert bad["failure_category"] == "answered_unanswerable"


# list / multi-part gold: every term and the number must match
def test_list_terms_need_all_parts():
    it = item(gold_fact_ids=["Amazon.com, Inc.", "Ernst & Young LLP"], gold_value=716924e6,
              gold_answer="Amazon.com, Inc. ... Auditor: Ernst & Young LLP.")
    both = ev.score(it, res(answer="AMZN: 716924 (auditor Ernst & Young LLP)", value=716924e6, unit="USD",
                            fact_ids=["AMZN|Revenue|FY2025"], citations=[cite("data/pdfs/AMZN.pdf", 58)]), G)
    assert both["correct"] is True
    no_aud = ev.score(it, res(answer="AMZN: 716924", value=716924e6, unit="USD", fact_ids=["AMZN|Revenue|FY2025"]), G)
    assert no_aud["correct"] is False and no_aud["failure_category"] == "wrong_value"


def test_company_name_term_matches_graph_name():
    it = item(gold_fact_ids=["PepsiCo"], gold_value=None)
    r = ev.score(it, res(answer="PEP: Purchase", value={"PEP": ["x"]}, fact_ids=["PEP|Revenue|FY2025"]), G)
    assert r["correct"] is True


def test_wrong_company_and_wrong_page_categories():
    it = item(gold_fact_ids=["AMZN|Revenue|FY2025"], gold_value=716924e6)
    wc = ev.score(it, res(answer="PEP", value=93925e6, unit="USD", fact_ids=["PEP|Revenue|FY2025"]), G)
    assert wc["failure_category"] == "wrong_company"
    wp = ev.score(it, res(answer="AMZN", value=716924e6, unit="USD", fact_ids=["AMZN|Revenue|FY2025"],
                          citations=[cite("data/pdfs/AMZN.pdf", 99)]), G)
    assert wp["correct"] is True and wp["failure_category"] == "wrong_page" and wp["page_hit_strict"] is False


def test_acceptable_pages_count_as_page_hit():
    it = item(gold_fact_ids=["AMZN|Revenue|FY2025"], gold_value=716924e6,
              acceptable_pages=[{"doc": "data/pdfs/AMZN.pdf", "page": 101}])
    r = lambda d, p: ev.score(it, res(answer="AMZN", value=716924e6, unit="USD", fact_ids=["AMZN|Revenue|FY2025"],
                                      citations=[cite(d, p)]), G)
    assert r("data/pdfs/AMZN.pdf", 101)["page_hit_strict"] is True
    assert r("data/pdfs/AMZN.pdf", 58)["page_hit_strict"] is True
    assert r("data/pdfs/AMZN.pdf", 99)["failure_category"] == "wrong_page"
    assert r("data/pdfs/PEP.pdf", 101)["page_hit_strict"] is False  # page pairs with its doc


def test_missing_fact_and_planner_failed_categories():
    it = item(gold_fact_ids=["MRK|TotalAssets|FY2025"], gold_value=136866e6)
    assert ev.score(it, res(abstained=True, reason="no_fact"), G)["failure_category"] == "missing_fact_in_graph"
    it2 = item(gold_fact_ids=["AMZN|Revenue|FY2025"], gold_value=716924e6)
    assert ev.score(it2, res(abstained=True, reason="ambiguous"), G)["failure_category"] == "planner_failed"
    assert ev.score(it2, res(abstained=True, reason="no_fact"), G)["failure_category"] == "abstained_wrongly"


def test_unscored_when_no_checkable_gold():
    r = ev.score(item(gold_value=None, gold_fact_ids=[]), res(answer="x"), G)
    assert r["correct"] is None and r["failure_category"] == "unscored"


def test_unscored_row_has_no_precision_recall_or_citation_and_is_excluded_from_means():
    # Q15-style: gold fact id but no number and no term -> unscored; must not dilute P/R or hit rates
    cited = [cite("data/pdfs/AMZN.pdf", 58)]
    un = ev.score(item(id="U", gold_value=None, gold_fact_ids=["AMZN|Revenue|FY2025"]),
                  res(answer="x", fact_ids=["PEP|Revenue|FY2025"], citations=cited), G)
    assert un["correct"] is None and un["failure_category"] == "unscored"
    assert un["precision"] is None and un["recall"] is None and un["doc_hit"] is None and un["page_hit_strict"] is None
    ok = ev.score(item(id="S", gold_value=716924e6, gold_fact_ids=["AMZN|Revenue|FY2025"]),
                  res(value=716924e6, unit="USD", fact_ids=["AMZN|Revenue|FY2025"], citations=cited), G)
    rep = ev.build_report([un, ok])
    assert rep["overall"]["precision"] == 1.0 and rep["overall"]["recall"] == 1.0
    assert rep["overall"]["scored"] == 1 and rep["overall"]["unscored"] == 1 and rep["overall"]["accuracy"] == 1.0
    assert rep["overall"]["doc_hit_rate"] == 1.0 and rep["overall"]["page_strict_rate"] == 1.0
    assert rep["notes"]["wrong_page"] and "wrong_page" in rep["notes"]["accuracy"]


# Q16-style: structured value is a dict (HQ city), the number is in the answer text or on a returned fact node
def test_number_matched_via_fact_node_or_answer_text_not_dict_value():
    it = item(gold_value=93925e6, gold_fact_ids=["PepsiCo", "Purchase, New York"])
    by_fact = ev.score(it, res(answer="PepsiCo: Purchase, New York", value={"PEP": ["Purchase"]},
                               fact_ids=["PEP|Revenue|FY2025"]), G)
    assert by_fact["correct"] is True
    by_text = ev.score(it, res(answer="PepsiCo net revenue $93,925 million; Purchase, New York",
                               value={"PEP": ["Purchase"]}, fact_ids=[]), G)
    assert by_text["correct"] is True
    wrong = ev.score(it, res(answer="PepsiCo net revenue unknown; Purchase, New York",
                             value={"PEP": ["Purchase"]}, fact_ids=["AMZN|Revenue|FY2025"]), G)
    assert wrong["correct"] is False and wrong["failure_category"] == "wrong_value"


def test_numeric_wrong_value_not_rescued_by_fact_node():
    it = item(gold_value=93925e6, gold_fact_ids=["PepsiCo"])
    r = ev.score(it, res(answer="sum is $141.87 billion", value=141.87e9, unit="USD",
                         fact_ids=["PEP|Revenue|FY2025"]), G)
    assert r["correct"] is False and r["failure_category"] == "wrong_value"


# per-type aggregation
def test_aggregate_per_type():
    rows = [
        ev.score(item(id="a", type="single_fact", gold_value=716924e6, gold_fact_ids=["AMZN|Revenue|FY2025"]),
                 res(value=716924e6, unit="USD", fact_ids=["AMZN|Revenue|FY2025"],
                     citations=[cite("data/pdfs/AMZN.pdf", 58)]), G),
        ev.score(item(id="b", type="single_fact", gold_value=716924e6, gold_fact_ids=["AMZN|Revenue|FY2025"]),
                 res(value=1.0, unit="USD", fact_ids=["PEP|Revenue|FY2025"]), G),
        ev.score(item(id="c", type="multi_hop", expected_behaviour="abstain", gold_fact_ids=[]),
                 res(abstained=True, reason="no_fact"), G),
    ]
    rep = ev.build_report(rows)
    assert rep["overall"]["n"] == 3 and rep["overall"]["correct"] == 2 and rep["overall"]["accuracy"] == 0.6667
    assert rep["overall"]["abstained"] == 1 and rep["overall"]["abstain_correct"] == 1
    assert rep["per_type"]["single_fact"]["accuracy"] == 0.5
    assert rep["per_type"]["multi_hop"]["n"] == 1
    assert rep["per_type"]["multi_hop"]["accuracy"] == 1.0
    assert rep["per_type"]["cross_filing"]["n"] == 0 and rep["per_type"]["cross_filing"]["accuracy"] is None


# no-key path: planner LLM failure abstains, never raises; a crashing question does not stop the run
def test_llm_failure_becomes_plan_failed(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("LLM cache miss and no API key available")
    monkeypatch.setattr(llm, "complete", boom)
    plan, ab = planner.make_plan("zzz unparseable question about nothing")
    assert plan is None and ab[0] == "plan_failed"


def test_run_survives_exception(monkeypatch):
    def boom(*a, **k):
        raise ValueError("boom")
    monkeypatch.setattr(query, "answer", boom)
    rows = ev.run([item()], G)
    assert rows[0]["abstained"] is True and rows[0]["reason"] == "plan_failed"

"""D-086 difference/share/growth/ranking/unknown-company fixes. Made-up wording; real graph, no network, no LLM."""
import pytest

from src import llm, query


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no llm in tests")
    monkeypatch.setattr(llm, "complete", boom)


def ans(q):
    return query.answer(q)


def test_difference_two_companies():
    a = ans("How much more revenue did Apple report than Microsoft in FY2024?")
    assert a["plan"]["intent"] == "difference" and not a["abstained"]
    assert a["fact_ids"] == ["AAPL|Revenue|FY2024", "MSFT|Revenue|FY2024"] and len(a["citations"]) == 2
    assert a["value"] == pytest.approx(391.035e9 - 245.122e9, rel=1e-3)


def test_difference_two_metrics_one_company():
    a = ans("By how much did Microsoft's revenue exceed its net income in 2024?")
    assert a["plan"]["intent"] == "difference"
    assert a["fact_ids"] == ["MSFT|Revenue|FY2024", "MSFT|NetIncome|FY2024"]
    assert a["signed_value"] > 0 and a["value"] == a["signed_value"]


@pytest.mark.parametrize("q,ids", [
    ("What percentage of Apple's revenue went to R&D in 2024?", ["AAPL|R&D|FY2024", "AAPL|Revenue|FY2024"]),
    ("Capital expenditures as a percentage of operating cash flow for Microsoft in 2024",
     ["MSFT|CapEx|FY2024", "MSFT|OperatingCashFlow|FY2024"]),
    ("Net income as a % of revenue for Apple 2024", ["AAPL|NetIncome|FY2024", "AAPL|Revenue|FY2024"])])
def test_share(q, ids):
    a = ans(q)
    assert a["plan"]["op"] == "share" and a["fact_ids"] == ids and a["unit"] == "%" and len(a["citations"]) == 2
    from src import graph as g
    G = g.load_graph()
    v = [G.nodes[i]["value"] for i in ids]
    assert a["value"] == pytest.approx(100 * v[0] / v[1])


@pytest.mark.parametrize("q", [
    "What was the total increase in Apple revenue from 2024 to 2025?",
    "Apple's revenue grew from 2024 to 2025 in total",
    "Percent change in Apple net income, 2024 to 2025"])
def test_growth_beats_total(q):
    a = ans(q)
    assert a["plan"]["intent"] == "growth" and a["unit"] == "%" and len(a["fact_ids"]) == 2


@pytest.mark.parametrize("q,w,intent", [
    ("Which generated more operating cash flow in 2024, Apple, Microsoft or Amazon?", "MSFT", "rank"),
    ("Which spent more on R&D in 2024, Apple or Microsoft?", "AAPL", "rank"),
    ("Which had lower net income in 2024: Apple, Microsoft, or Nvidia?", "NVDA", "rank")])
def test_comparison_wording(q, w, intent):
    a = ans(q)
    assert a["plan"]["intent"] == intent and a["winner"] == w and len(a["fact_ids"]) >= 2


@pytest.mark.parametrize("q,name", [
    ("Compare Apple and Zorbo revenue 2024", "Zorbo"),
    ("Apple, Zorbo and Microsoft revenue 2024", "Zorbo"),
    ("What was Frobnitz Corp revenue in 2024?", "Frobnitz")])
def test_unknown_company_abstains(q, name):
    a = ans(q)
    assert a["abstained"] and a["reason"] == "unknown_company" and name in a["detail"]


@pytest.mark.parametrize("q", [
    "Compare Apple and Microsoft revenue in March 2024",
    "Which company, Apple or Microsoft, had higher revenue in Fiscal 2024?",
    "What was Apple's R&D and EPS in 2024?",
    "How much cash did Apple generate from operations in FY2025?"])
def test_no_false_unknown_company(q):
    assert ans(q).get("reason") != "unknown_company"


def test_axp_operating_cash_flow():
    a = ans("What was American Express operating cash flow in 2024?")
    assert a["fact_ids"] == ["AXP|OperatingCashFlow|FY2024"] and not a["abstained"]


def test_possessive_company_not_flagged_unknown():
    from src import query
    r = query.answer("What was McDonald's net income in fiscal 2025?")
    assert r.get("abstain_reason") != "unknown_company" and "McDonald" not in str(r.get("reason", ""))

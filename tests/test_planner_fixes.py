"""D-083 generic planner/executor/scorer/cache fixes. Made-up wording; real graph, no network, no LLM."""
import pytest

from src import evaluate as ev
from src import llm, planner, query

LEX = planner.default_lexicon()


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no llm in tests")
    monkeypatch.setattr(llm, "complete", boom)


def plan(q):
    return planner.make_plan(q)


# 1. comparison cue beats a bare 'total'
@pytest.mark.parametrize("q", [
    "Which has a higher total revenue, Apple or Microsoft?",
    "Is Apple's total revenue larger than Microsoft's?",
    "Who reported more total revenue: Apple or Microsoft?"])
def test_total_with_comparison_cue_is_not_sum(q):
    p, ab = plan(q)
    assert ab is None and p["intent"] != "aggregate" and p["op"] != "sum"


@pytest.mark.parametrize("q", ["What is the combined revenue of Apple and Microsoft?",
                               "What is the total revenue of Apple and Microsoft?",
                               "Add up Apple and Microsoft revenue.",
                               "Apple and Microsoft revenue together?"])
def test_sum_cues_still_sum(q):
    p, ab = plan(q)
    assert ab is None and p["intent"] == "aggregate" and p["op"] == "sum"


# 2. bare first word aliases
@pytest.mark.parametrize("word,t", [("amazon", "AMZN"), ("alphabet", "GOOGL"), ("meta", "META"), ("apple", "AAPL")])
def test_bare_company_alias(word, t):
    assert LEX.company_alias[word] == t
    p, ab = plan(f"What was {word.capitalize()}'s revenue?")
    assert ab is None and p["companies"] == [t]
    p, ab = plan("What was Amazon.com Inc. revenue?")
    assert p["companies"] == ["AMZN"]


# 3. never answer with a different metric
@pytest.mark.parametrize("q", ["What were Apple's total current assets?", "How much were Apple's cash dividends?",
                               "What is Apple's return on equity?", "What was Apple's pretax profit?",
                               "What was Apple's pre-tax earnings?", "What was Apple's cost of sales?"])
def test_qualified_metric_abstains(q):
    p, ab = plan(q)
    assert p is None and ab[0] == "unsupported_metric"


@pytest.mark.parametrize("q,m", [("What were Apple's total assets?", "TotalAssets"), ("What was Apple's revenue?", "Revenue"),
                                 ("What was Apple's cash and cash equivalents?", "Cash")])
def test_plain_metric_still_maps(q, m):
    p, ab = plan(q)
    assert ab is None and p["metric"] == m


# 4. two named years for one company/metric
def test_two_years_both_returned():
    a = query.answer("What was Apple's revenue in 2025 and 2026?")
    assert not a["abstained"]
    assert "FY2025" in a["answer"] and "FY2026" in a["answer"]
    assert len(a["fact_ids"]) == 2 and len(a["value"]) == 2
    assert "FY2025 FY2025" not in a["answer"]  # no duplicated labels


def test_growth_between_years_uses_both():
    a = query.answer("What was the revenue growth for Apple from 2024 to 2026?")
    assert not a["abstained"] and "2024->2026" in a["answer"]


# 5. president vs vice president
@pytest.mark.parametrize("role,title,ok", [
    ("president", "Executive Vice President and Chief Financial Officer", False),
    ("president", "Senior Vice-President, Legal", False),
    ("president", "President and Chief Executive Officer", True),
    ("president", "Vice Chair and President", True),
    ("president", "Presidential Advisor", False),
    ("vice president", "Vice President, Worldwide Controller", True),
    ("chair", "Chairman and CEO", True),
    ("chair", "Vice Chair and President", False),
    ("chief executive", "CEO, Commercial", False)])
def test_role_ok(role, title, ok):
    assert query.role_ok(role, title) is ok


def test_planner_vice_president_role():
    assert plan("Who is the vice president at Amazon?")[0]["role"] == "vice president"
    assert plan("Who is the president of Amazon?")[0]["role"] == "president"


def test_president_answer_excludes_vps():
    a = query.answer("Who is the president of Amazon?")
    assert "Jassy" in a["answer"] and "Zapolsky" not in a["answer"] and "Reynolds" not in a["answer"]


# 6. scorer
def _g():
    import networkx as nx
    G = nx.MultiDiGraph()
    G.add_node("AAA", node_type="Company", name="Alpha Corp")
    G.add_node("BBB", node_type="Company", name="Beta Inc")
    G.add_node("AAA|Revenue|FY2025", doc="AAA.pdf", page=1, value=1.0)
    G.add_node("BBB|Revenue|FY2025", doc="BBB.pdf", page=1, value=2.0)
    return G


def _item(gold):
    return dict(id="T", type="multi_hop", question="q", gold_answer="g", gold_value=None, gold_fact_ids=[gold],
                docs=["BBB.pdf"], pages=[1], expected_behaviour="answer")


def _res(winner):
    return dict(abstained=False, answer="BBB has the highest Revenue: $2 (FY2025) | AAA FY2025 $1; BBB FY2025 $2",
                value=2.0, unit="USD", fact_ids=["AAA|Revenue|FY2025", "BBB|Revenue|FY2025"], citations=[],
                reason=None, **({"winner": winner} if winner else {}))


def test_ranking_gold_credits_only_winner():
    G = _g()
    assert ev.score(_item("Beta Inc"), _res("BBB"), G)["correct"] is True
    assert ev.score(_item("Alpha Corp"), _res("BBB"), G)["correct"] is False  # loser also in the text/facts


def test_non_ranking_gold_unchanged_without_winner():
    G = _g()
    assert ev.score(_item("Alpha Corp"), _res(None), G)["correct"] is True  # no winner: old behaviour


def test_year_in_text_not_a_number():
    assert not ev.text_has_number("Revenue (FY2025): $5 billion", 2025)
    assert not ev.text_has_number("in 2025 and 2026", 2025e6)
    assert ev.text_has_number("Employees: 2,025", 2025)
    assert ev.text_has_number("margin 12.5%", 0.125)


# 7. corrupt cache
@pytest.mark.parametrize("junk", ["", '{"provider": "x", "te', "[1]", '{"nope": 1}', "\x00\x01"])
def test_corrupt_cache_is_a_miss_and_rewritten(tmp_path, monkeypatch, junk):
    monkeypatch.setattr(llm, "LLM_CACHE_DIR", tmp_path)
    key = llm._cache_key("p", None, False)
    (tmp_path / f"{key}.json").write_text(junk, encoding="utf-8")
    assert llm._cache_read(key) is None
    llm._cache_write(key, "fresh", "groq")
    assert llm._cache_read(key) == "fresh"
    assert [p.name for p in tmp_path.iterdir()] == [f"{key}.json"]  # no tmp leftovers

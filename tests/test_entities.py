"""Offline tests for src/entities.py: page finder, grounding gate, JSON retry (stubbed LLM), id slugging."""
import json

import src.entities as ent

PAGES = {
    1: "Apple Inc.\n(Exact name of Registrant as specified in its charter)\nCalifornia 94-2404110\nOne Apple Park Way\nCupertino, California 95014",
    2: "Table of Contents\nItem 1. Business\nItem 1A. Risk Factors\nItem 1B. Unresolved\nItem 1C. Cyber\nItem 2. Properties\nItem 3. Legal",
    3: "Information about our Executive Officers is in Part I.",
    4: "Item 1. Business\nWe have three reportable segments: Americas, Europe and Greater China.\nWe had approximately 166,000 full-time equivalent employees.",
    5: "Information about our Executive Officers\nTim Cook Chief Executive Officer\nKevan Parekh Senior Vice President and Chief Financial Officer",
    6: "Report of Independent Registered Public Accounting Firm\nWe have audited the financial statements. In our opinion they present fairly.\n/s/ Ernst & Young LLP\nSan Jose, California",
}


def test_find_windows_locates_each_category():
    w = ent.find_windows(PAGES)
    assert w["cover"] == [1]
    assert w["segments"][0] == 4
    assert w["employees"][0] == 4
    assert w["auditor"][0] == 6
    assert w["officers"][0] == 5  # page 3 is skipped (start=4) and page 2 is a TOC, so the first real list is p5


def test_excerpt_truncates_and_marks_pages():
    text = ent.excerpt(PAGES, [1, 2])
    assert text.startswith("[page 1]\n") and "[page 2]" in text and len(text) <= ent.MAX_CHARS


def test_ground_accepts_whitespace_and_case_and_reports_page():
    cands = [(4, "approximately 166,000\nfull-time   equivalent employees"), (6, "Ernst & Young LLP")]
    assert ent.ground("166,000", cands) [0] == 4
    assert ent.ground("ernst & young llp", cands)[0] == 6


def test_ground_rejects_absent_name_and_never_invents_page():
    assert ent.ground("Deloitte & Touche LLP", [(6, "Ernst & Young LLP")]) == (None, None)
    assert ent.ground("", [(6, "Ernst & Young LLP")]) == (None, None)


def test_employee_count_rejected_when_number_not_on_page():
    e = ent.build_entities("AAPL", "employees", {"employee_count": 999}, [4], PAGES, 2026)
    assert e[0]["grounded"] is False and e[0]["page"] is None
    ok = ent.build_entities("AAPL", "employees", {"employee_count": 166000}, [4], PAGES, 2026)
    assert ok[0]["id"] == "AAPL|Employees|FY2026" and ok[0]["value"] == 166000 and ok[0]["unit"] == "count"
    assert ok[0]["grounded"] and ok[0]["page"] == 4


def test_slug_and_ids():
    assert ent.slug("Ernst & Young LLP") == "ernst-young-llp"
    assert ent.slug("Cupertino, California") == "cupertino-california"
    assert ent.entity_id("Person", "AAPL", "Tim Cook") == "PERSON|AAPL|tim-cook"
    assert ent.entity_id("Segment", "JPM", "Consumer & Community Banking") == "SEG|JPM|consumer-community-banking"
    assert ent.entity_id("Organization", "AAPL", "Ernst & Young LLP") == "ORG|ernst-young-llp"
    assert ent.entity_id("Location", "AAPL", "California") == "LOC|california"


def test_ask_retries_once_on_bad_json_with_changed_prompt(monkeypatch):
    calls = []

    def stub(prompt, system=None, json_mode=False):
        calls.append(prompt)
        return "not json at all" if len(calls) == 1 else '```json\n{"segments": ["Americas"]}\n```'

    monkeypatch.setattr(ent, "_complete", stub)
    assert ent.ask("segments", "excerpt") == {"segments": ["Americas"]}
    assert len(calls) == 2 and calls[0] != calls[1]  # changed prompt so the LLM cache does not replay the bad reply


def test_ask_gives_up_after_two_bad_replies(monkeypatch):
    monkeypatch.setattr(ent, "_complete", lambda *a, **k: "still not json")
    assert ent.ask("officers", "excerpt") is None


def test_build_entities_marks_ungrounded_names(monkeypatch):
    obj = {"executive_officers": [{"name": "Tim Cook", "title": "CEO"}, {"name": "Jane Doe", "title": "CFO"}]}
    out = ent.build_entities("AAPL", "officers", obj, [5], PAGES, 2026)
    assert [e["grounded"] for e in out] == [True, False]
    assert out[0]["id"] == "PERSON|AAPL|tim-cook" and out[0]["role"] == "CEO" and out[0]["page"] == 5


def test_employee_as_written_must_agree_with_count():
    bad = ent.build_entities("AAPL", "employees", {"employee_count": 166000, "as_written": "1,166,000"}, [4], PAGES, 2026)
    assert bad[0]["grounded"] is False and "as_written" in bad[0]["reason"]
    ok = ent.build_entities("AAPL", "employees", {"employee_count": 166000, "as_written": "over 166,000"}, [4], PAGES, 2026)
    assert ok[0]["grounded"] and ok[0]["page"] == 4 and "166,000" in ok[0]["snippet"]


def test_employee_snippet_set_on_fallback_lookup():
    e = ent.build_entities("AAPL", "employees", {"employee_count": 166000, "as_written": None}, [4], PAGES, 2026)
    assert e[0]["grounded"] and e[0]["snippet"] and "166,000" in e[0]["snippet"]


def test_ground_number_boundary_blocks_inside_larger_number():
    cands = [(4, "we employed 1,166,000 people")]
    assert ent.ground("166,000", cands) == (None, None)
    assert ent.ground("166,000", [(4, "we employed 166,000 people")])[0] == 4


def test_exchange_org_ids_merge():
    a = ent.entity_id("Organization", "AAPL", "The Nasdaq Stock Market LLC")
    b = ent.entity_id("Organization", "AMZN", "Nasdaq Global Select Market")
    c = ent.entity_id("Organization", "MSFT", "Nasdaq")
    assert a == b == c == "ORG|nasdaq"
    assert ent.entity_id("Organization", "JPM", "The New York Stock Exchange") == ent.entity_id(
        "Organization", "ABT", "New York Stock Exchange")

"""Schema and PDF-grounding checks for benchmark/benchmark.json (gold must cite real parsed pages)."""
import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark" / "benchmark.json"
FACT_ID = re.compile(r"^[A-Z]{1,5}\|[A-Za-z&]+\|FY\d{4}$")
TYPES = {"single_fact", "multi_hop", "cross_filing"}
REQUIRED = {"id", "type", "question", "gold_answer", "gold_value", "gold_fact_ids", "docs",
            "pages", "evidence", "verified", "answerable", "expected_behaviour", "notes"}


@pytest.fixture(scope="module")
def items():
    return json.loads(BENCH.read_text(encoding="utf-8"))["items"]


@lru_cache(maxsize=None)
def parsed_pages(ticker):
    return json.loads((ROOT / "data" / "parsed" / f"{ticker}.json").read_text(encoding="utf-8"))["pages"]


def test_count_and_ids(items):
    assert 28 <= len(items) <= 30
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"Q\d{2}", i) for i in ids)


def test_types_present(items):
    counts = {t: sum(i["type"] == t for i in items) for t in TYPES}
    assert set(t for t in TYPES if counts[t]) == TYPES, counts
    assert set(i["type"] for i in items) <= TYPES


def test_required_fields_and_verified_false(items):
    for i in items:
        assert REQUIRED <= set(i), i["id"]
        assert i["verified"] is False, i["id"]
        assert isinstance(i["answerable"], bool), i["id"]
        assert i["expected_behaviour"] == ("answer" if i["answerable"] else "abstain"), i["id"]
        assert i["pages"] and len(i["gold_fact_ids"]) >= 1 and i["docs"], i["id"]


def test_fact_id_format(items):
    for i in items:
        for fid in i["gold_fact_ids"]:
            if "|" in fid:
                assert FACT_ID.fullmatch(fid), (i["id"], fid)


def test_unanswerable_items_marked(items):
    unans = [i for i in items if not i["answerable"]]
    assert 3 <= len(unans) <= 4
    for i in unans:
        assert i["gold_value"] is None and i["answerable_by_graph"] == "unknown", i["id"]


def test_evidence_pages_exist_and_contain_key(items):
    # evidence carries no doc field, so the key must appear on that page of one of the item's docs
    for i in items:
        tickers = [Path(d).stem for d in i["docs"]]
        for e in i["evidence"]:
            assert e["page"] in i["pages"], (i["id"], e["page"])
            texts = [parsed_pages(t)[str(e["page"])] for t in tickers if str(e["page"]) in parsed_pages(t)]
            assert texts, (i["id"], e["page"])
            assert any(e["key"] in txt for txt in texts), (i["id"], e["page"], e["key"])

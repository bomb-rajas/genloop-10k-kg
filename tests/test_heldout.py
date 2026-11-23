"""Schema and PDF-grounding checks for benchmark/heldout.json."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = json.loads((ROOT / "benchmark" / "heldout.json").read_text(encoding="utf-8"))["items"]
REQUIRED = {"id", "type", "question", "gold_answer", "gold_value", "gold_fact_ids", "docs", "pages",
            "evidence", "verified", "answerable", "expected_behaviour", "notes"}


def test_count_ids_types():
    assert [i["id"] for i in ITEMS] == [f"H{n:02d}" for n in range(1, 16)]
    for t in ("single_fact", "multi_hop", "cross_filing"):
        assert sum(i["type"] == t for i in ITEMS) == 5
    assert sum(not i["answerable"] for i in ITEMS) == 2


def test_schema():
    for i in ITEMS:
        assert REQUIRED <= set(i) and i["verified"] is False, i["id"]
        assert i["expected_behaviour"] == ("answer" if i["answerable"] else "abstain")
        assert (i["gold_value"] is None) == (not i["answerable"]), i["id"]
    assert len({Path(d).stem for i in ITEMS for d in i["docs"]}) >= 12


def test_evidence_on_pages():
    for i in ITEMS:
        stems = [Path(d).stem for d in i["docs"]]
        for e in i["evidence"]:
            assert e["page"] in i["pages"], i["id"]
            texts = [p[str(e["page"])] for s in stems
                     for p in [json.loads((ROOT / "data/parsed" / f"{s}.json").read_text())["pages"]] if str(e["page"]) in p]
            assert any(e["key"] in t for t in texts), (i["id"], e)

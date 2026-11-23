"""Schema and PDF-grounding checks for benchmark/fresh.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = json.loads((ROOT / "benchmark" / "fresh.json").read_text(encoding="utf-8"))["items"]
REQUIRED = {"id", "type", "question", "gold_answer", "gold_value", "gold_fact_ids", "docs", "pages",
            "evidence", "verified", "answerable", "expected_behaviour", "notes"}


def test_count_ids_types():
    assert [i["id"] for i in ITEMS] == [f"F{n:02d}" for n in range(1, 16)]
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
        for e in i["evidence"]:
            assert e["page"] in i["pages"] and e["doc"] in i["docs"], i["id"]
            pages = json.loads((ROOT / "data/parsed" / f"{Path(e['doc']).stem}.json").read_text())["pages"]
            assert e["key"] in pages.get(str(e["page"]), ""), (i["id"], e)
            assert e["quote"].replace(" ", "")[:12] in pages[str(e["page"])].replace(" ", ""), (i["id"], e)

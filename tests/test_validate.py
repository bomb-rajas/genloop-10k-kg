"""XBRL gate: tolerance edges, mismatch rejected, no_xbrl admitted, period matching, identity check (synthetic)."""
from src import validate

REVENUE = {"name": "Revenue", "category": "income", "unit": "USD", "xbrl_tags": ["Revenues"]}
EPS = {"name": "EPS", "category": "income", "unit": "USD/share", "xbrl_tags": ["EarningsPerShareDiluted"]}
TA = {"name": "TotalAssets", "category": "balance", "unit": "USD", "xbrl_tags": ["Assets"]}
FILING = {"accession": "A-1", "report_date": "2025-09-27"}


def xb(tag, unit, val, end, start=None, accn="A-1", form="10-K", fp="FY", filed="2025-10-31"):
    e = {"val": val, "end": end, "accn": accn, "form": form, "fp": fp, "filed": filed}
    if start:
        e["start"] = start
    return {"facts": {"us-gaap": {tag: {"units": {unit: [e]}}}}}


def fact(value, metric, fy=2025, unit="USD"):
    return {"id": f"T|{metric['name']}|FY{fy}", "ticker": "T", "metric": metric["name"], "value": value,
            "unit": unit, "period": {"fiscal_year": fy, "period_end": None}, "method": "pdf_table",
            "validated": False, "xbrl_status": None, "xbrl_value": None}


def test_tolerance_edge_relative():
    assert validate.within(100_400, 100_000, "USD")      # 0.4% < 0.5%
    assert not validate.within(100_600, 100_000, "USD")  # 0.6% > 0.5%


def test_tolerance_edge_eps_absolute():
    assert validate.within(2.004, 2.0, "USD/share")
    assert not validate.within(2.01, 2.0, "USD/share")


def test_match_admitted_and_validated():
    f = fact(100_000_000, REVENUE)
    admitted, rejected, stats = validate.gate([f], xb("Revenues", "USD", 100_000_000, "2025-09-27", start="2024-09-29"),
                                              FILING, {"Revenue": REVENUE})
    assert admitted == [f] and rejected == []
    assert f["xbrl_status"] == "match" and f["validated"] is True and stats["matched"] == 1


def test_mismatch_rejected_not_admitted():
    f = fact(90_000_000, REVENUE)
    admitted, rejected, stats = validate.gate([f], xb("Revenues", "USD", 100_000_000, "2025-09-27", start="2024-09-29"),
                                              FILING, {"Revenue": REVENUE})
    assert admitted == [] and len(rejected) == 1
    assert rejected[0]["reason"].startswith("xbrl_mismatch")
    assert stats["mismatch"] == 1


def test_no_xbrl_admitted_with_validated_false():
    f = fact(5_000, TA)
    admitted, rejected, stats = validate.gate([f], {"facts": {"us-gaap": {}}}, FILING, {"TotalAssets": TA})
    assert admitted == [f] and rejected == []
    assert f["xbrl_status"] == "no_xbrl" and f["validated"] is False and stats["no_xbrl"] == 1


def test_period_matching_ignores_other_years_and_10q():
    f = fact(100_000_000, REVENUE)
    x = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"val": 1, "end": "2024-09-28", "start": "2023-09-30", "accn": "old", "form": "10-K", "fp": "FY", "filed": "2024-10-31"},
        {"val": 2, "end": "2025-09-27", "start": "2025-06-28", "accn": "q", "form": "10-Q", "fp": "Q3", "filed": "2025-08-01"},
        {"val": 100_000_000, "end": "2025-09-27", "start": "2024-09-29", "accn": "A-1", "form": "10-K", "fp": "FY", "filed": "2025-10-31"}
    ]}}}}}
    admitted, _, _ = validate.gate([f], x, FILING, {"Revenue": REVENUE})
    assert f["xbrl_status"] == "match" and f["xbrl_value"] == 100_000_000


def test_identity_check_logs_only():
    ta = fact(500, TA)
    tl = fact(300, {"name": "TotalLiabilities"})
    eq = fact(200, {"name": "Equity"})
    eq["metric"] = "Equity"
    ta["metric"], tl["metric"] = "TotalAssets", "TotalLiabilities"
    checked, failed = validate.identity_check([ta, tl, eq])
    assert (checked, failed) == (1, 0) and ta["identity_ok"] is True
    tl["value"] = 310
    checked, failed = validate.identity_check([ta, tl, eq])
    assert (checked, failed) == (1, 1)


def test_gate_fact_reports_the_matched_candidate():
    # Two candidate entries (second matches): xbrl_value and period_end must come from the match.
    xbrl = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"val": 713163e6, "end": "2026-01-31", "accn": "A-1", "form": "10-K", "fp": "FY", "filed": "2026-03-01", "start": "2025-02-01"},
        {"val": 706413e6, "end": "2026-01-31", "accn": "A-1", "form": "10-K", "fp": "FY", "filed": "2026-03-01", "start": "2025-02-01"},
    ]}}}}}
    f = validate.gate_fact(fact(706413e6, REVENUE, fy=2026), xbrl, REVENUE, "A-1", "2026-01-31")
    assert f["xbrl_status"] == "match" and f["validated"] is True
    assert f["xbrl_value"] == 706413e6

"""Label matching, scale, identity fallback, layout normalisation (synthetic data, no network)."""
import json

import pytest

from src import config, extract
from src.extract import extract_company, find_metric_row, match_row, norm, normalise_layout, infer_header

METRICS = {m["name"]: m for m in config.load_metrics()["metrics"]}


def cand(labels):
    return [(i, norm(l)) for i, l in enumerate(labels)]


def test_norm_strips_footnotes_and_punctuation():
    assert norm("Shareholders’ equity (Notes 1 and 2)") == "shareholders equity"
    assert norm("Net income (loss) (a)") == "net income"


def test_exact_synonym_beats_prefix():
    spec = {"synonyms": ["net income"], "exclude": []}
    assert match_row(cand(["Net income per share", "Net income"]), spec) == (1, "exact")


def test_prefix_rejected_by_exclusion_word():
    # 'net income margin' must not satisfy the synonym 'net income' via prefix (margin excluded)
    spec = {"synonyms": ["net income"], "exclude": []}
    assert match_row(cand(["Net income margin"]), spec) is None


def test_prefix_match_with_plain_remainder():
    spec = {"synonyms": ["net income attributable to company"], "exclude": []}
    assert match_row(cand(["Net income attributable to company, net of tax"]), spec) == (0, "prefix")


def test_fallback_label_used_when_no_synonym():
    spec = {"synonyms": ["total assets"], "fallback_labels": ["total net assets"]}
    assert match_row(cand(["Total net assets"]), spec) == (0, "exact")


def test_regex_tier_for_revenue_and_eps_exclusions():
    rev = METRICS["Revenue"]
    assert match_row(cand(["Total NIKE, Inc. Revenues"]), rev)[1] == "regex"
    assert match_row(cand(["Total cost of revenues"]), rev) is None  # excluded by 'cost'
    eps = METRICS["EPS"]
    assert match_row(cand(["Net income per share - basic"]), eps) is None
    assert match_row(cand(["Net income per diluted common share"]), eps)[1] == "regex"


def test_scale_and_column_years_and_absolute_capex():
    """Scale applied to USD, EPS not scaled, CapEx stored positive, window keeps 3 IS years."""
    parsed = {"statements": {
        "income_statement": {"columns": [2025, 2024, 2023], "scale": 1000000, "rows": [
            {"label": "Net sales", "values": [100.0, 90.0, 80.0], "page": 5},
            {"label": "Diluted earnings per share", "values": [2.5, 2.0, 1.5], "page": 5}]},
        "cash_flow_statement": {"columns": [2025, 2024, 2023], "scale": 1000000, "rows": [
            {"label": "Purchases of property, plant and equipment", "values": [-7.0, -6.0, -5.0], "page": 6}]},
        "balance_sheet": {"columns": [2025, 2024], "scale": 1000000, "rows": []}}}
    company = {"ticker": "TST", "is_bank": False}
    filing = {"report_date": "2025-12-31"}
    old = config.PARSED_DIR
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "TST.json").write_text(json.dumps(parsed))
    config.PARSED_DIR = d
    try:
        helpers = {h['name']: h for h in config.load_metrics()['helper_metrics']}
        facts, missing = extract_company(company, filing, list(METRICS.values()), helpers)
    finally:
        config.PARSED_DIR = old
    by_id = {f["id"]: f for f in facts}
    assert by_id["TST|Revenue|FY2025"]["value"] == 100_000_000
    assert by_id["TST|Revenue|FY2023"]["value"] == 80_000_000
    assert by_id["TST|EPS|FY2025"]["value"] == 2.5 and by_id["TST|EPS|FY2025"]["unit"] == "USD/share"
    assert by_id["TST|CapEx|FY2025"]["value"] == 7_000_000
    assert by_id["TST|Revenue|FY2025"]["period"]["period_end"] == "2025-12-31"


def test_identity_fallback_total_liabilities():
    """No 'Total liabilities' row: TotalLiabilities = TotalLiabilitiesAndEquity - Equity, method identity."""
    parsed = {"statements": {"balance_sheet": {"columns": [2025], "scale": 1000, "rows": [
        {"label": "Total liabilities and stockholders’ equity", "values": [500.0], "page": 9},
        {"label": "Total stockholders’ equity", "values": [200.0], "page": 9},
        {"label": "Total assets", "values": [500.0], "page": 9}]}}}
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    (d / "IDN.json").write_text(json.dumps(parsed))
    old = config.PARSED_DIR
    config.PARSED_DIR = d
    helpers = {h["name"]: h for h in config.load_metrics()["helper_metrics"]}
    try:
        facts, _ = extract_company({"ticker": "IDN", "is_bank": False}, {"report_date": "2025-06-30"},
                                   list(METRICS.values()), helpers)
    finally:
        config.PARSED_DIR = old
    tl = next(f for f in facts if f["metric"] == "TotalLiabilities")
    assert tl["method"] == "identity" and tl["value"] == 300_000
    assert tl["as_reported_label"].startswith("Total liabilities and stockholders")


def test_layout_drops_future_column_and_keeps_value_of_pct_pairs():
    st = {"columns": [2025, 2024, 2026, 2023], "rows": [{"label": "Sales", "values": [1.0, 2.0, 3.0], "page": 1}]}
    normalise_layout(st, 2025)
    assert st["columns"] == [2025, 2024, 2023]
    st2 = {"columns": [2025, 2024], "rows": [{"label": "Operating income", "values": [50.0, 10.0, 40.0, 9.0], "page": 1}]}
    normalise_layout(st2, 2025)
    assert st2["rows"][0]["values"] == [50.0, 40.0]
    st3 = {"columns": [2025, 2024], "rows": [{"label": "Diluted earnings per share", "values": [5.0, 6.0, 7.0, 8.0], "page": 1}]}
    normalise_layout(st3, 2025)
    assert len(st3["rows"][0]["values"]) == 4  # per-share rows never pair-collapsed


def test_infer_header_from_year_row():
    rows = [{"label": "Amounts in millions; fiscal years", "values": [30.0, 2026.0, 2025.0, 2024.0]},
            {"label": "NET SALES", "values": [87032.0, 84284.0, 84039.0]}]
    years, rest = infer_header(rows)
    assert years == [2026, 2025, 2024] and len(rest) == 1


def _run_company(ticker, parsed, report_date):
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    (d / f"{ticker}.json").write_text(json.dumps(parsed))
    old = config.PARSED_DIR
    config.PARSED_DIR = d
    try:
        helpers = {h["name"]: h for h in config.load_metrics()["helper_metrics"]}
        return extract_company({"ticker": ticker, "is_bank": False}, {"report_date": report_date},
                               list(METRICS.values()), helpers)
    finally:
        config.PARSED_DIR = old


def test_header_shifted_one_year_is_relabelled_fiscal_year():
    """HD-style: header prints 2025 for a filing whose period ends in Jan 2026 -> FY2026 (D-058)."""
    parsed = {"statements": {"income_statement": {"columns": [2025, 2024, 2023], "scale": 1000, "rows": [
        {"label": "Net sales", "values": [100.0, 90.0, 80.0], "page": 5}]}}}
    facts, _ = _run_company("SHF", parsed, "2026-01-31")
    rev = {f["id"]: f for f in facts if f["metric"] == "Revenue"}
    assert rev["SHF|Revenue|FY2026"]["value"] == 100_000
    assert rev["SHF|Revenue|FY2025"]["value"] == 90_000 and rev["SHF|Revenue|FY2024"]["value"] == 80_000
    assert not any(k.endswith("FY2027") for k in rev)


def test_years_window_three_is_and_two_bs_and_period_end_only_newest():
    parsed = {"statements": {
        "income_statement": {"columns": [2025, 2024, 2023, 2022], "scale": 1000, "rows": [
            {"label": "Net sales", "values": [4.0, 3.0, 2.0, 1.0], "page": 5}]},
        "balance_sheet": {"columns": [2025, 2024, 2023], "scale": 1000, "rows": [
            {"label": "Total assets", "values": [9.0, 8.0, 7.0], "page": 6}]}}}
    facts, _ = _run_company("WIN", parsed, "2025-12-31")
    ids = {f["id"] for f in facts}
    assert {"WIN|Revenue|FY2025", "WIN|Revenue|FY2023"} <= ids and "WIN|Revenue|FY2022" not in ids
    assert "WIN|TotalAssets|FY2024" in ids and "WIN|TotalAssets|FY2023" not in ids
    by = {f["id"]: f for f in facts}
    assert by["WIN|Revenue|FY2025"]["period"]["period_end"] == "2025-12-31"
    assert by["WIN|Revenue|FY2024"]["period"]["period_end"] is None


def test_identity_values_are_whole_numbers():
    """Identity-derived values are rounded to int like direct facts."""
    parsed = {"statements": {"balance_sheet": {"columns": [2025], "scale": 1000000, "rows": [
        {"label": "Total liabilities and stockholders’ equity", "values": [500.5], "page": 9},
        {"label": "Total stockholders’ equity", "values": [200.2], "page": 9},
        {"label": "Total assets", "values": [500.5], "page": 9}]}}}
    facts, _ = _run_company("RND", parsed, "2025-06-30")
    tl = next(f for f in facts if f["metric"] == "TotalLiabilities")
    assert tl["method"] == "identity" and isinstance(tl["value"], int)

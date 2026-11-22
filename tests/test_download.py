"""Tests for src.download. No network: HTTP and Chrome are monkeypatched or unused."""
import pytest

from src import download
from src.download import financials_page, filing_url, latest_10k


def fake_submissions():
    return {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000003", "0000000001-26-000002", "0000000001-26-000001",
                                    "0000000001-25-000009"],
                "form": ["10-K/A", "10-Q", "10-K", "10-K"],
                "filingDate": ["2026-03-10", "2026-02-01", "2026-01-30", "2025-01-28"],
                "reportDate": ["2025-12-31", "2025-12-31", "2025-12-31", "2024-12-31"],
                "primaryDocument": ["amend.htm", "q.htm", "tenk.htm", "old.htm"],
            }
        }
    }


def test_latest_10k_skips_amendments_and_10q():
    f = latest_10k(fake_submissions())
    assert f == {
        "accession": "0000000001-26-000001",
        "filing_date": "2026-01-30",
        "report_date": "2025-12-31",
        "primary_document": "tenk.htm",
    }


def test_latest_10k_raises_when_none():
    sub = {"filings": {"recent": {"accessionNumber": ["x"], "form": ["10-Q"], "filingDate": ["2026-01-01"],
                                  "reportDate": ["2025-09-30"], "primaryDocument": ["q.htm"]}}}
    with pytest.raises(LookupError):
        latest_10k(sub)


def test_filing_url_strips_dashes_and_leading_zeros():
    url = filing_url("0000320193", "0000320193-25-000079", "aapl-20250927.htm")
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm"


def test_financials_page_needs_total_assets_with_equity_line_and_skips_first_15_percent():
    summary = "Selected data: Total assets 1,000 ..."  # summary table before the statements
    stmt = "CONSOLIDATED BALANCE SHEETS\nTotal assets 1,000\nTotal liabilities 400\nTotal shareholders' equity 600"
    texts = ["cover"] * 6 + [summary, stmt] + ["x"] * 12  # 20 pages: skip first 3 (15%)
    assert financials_page(texts) == 8
    assert financials_page([summary, "no statements", None]) is None
    assert financials_page(["Total assets only", "x", "y", "z"]) is None  # no equity/liabilities line


def test_throttle_sleeps_when_too_fast(monkeypatch):
    sleeps = []
    monkeypatch.setattr(download.time, "sleep", sleeps.append)
    t = download.Throttle(0.2)
    t.last = download.time.monotonic()
    t.wait()
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.2


def test_process_skips_existing_pdf_without_network(monkeypatch, tmp_path):
    """Idempotent: a company already recorded as ok with its PDF on disk makes no HTTP call."""
    monkeypatch.setattr(download, "PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(download, "XBRL_DIR", tmp_path / "xbrl")
    monkeypatch.setattr(download, "RAW_HTML_DIR", tmp_path / "html")
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "xbrl").mkdir()
    (tmp_path / "xbrl" / "AAPL.json").write_text("{}")
    (tmp_path / "pdfs" / "AAPL.pdf").write_bytes(b"%PDF-1.4")

    def no_network(*a, **k):
        raise AssertionError("network or Chrome called for an existing PDF")

    monkeypatch.setattr(download, "http_get", no_network)
    monkeypatch.setattr(download, "html_to_pdf", no_network)
    filings = {"AAPL": {"status": "ok", "pdf": "data/pdfs/AAPL.pdf"}}
    assert download.process({"ticker": "AAPL", "cik": "0000320193"}, "test-agent", filings) == "ok"


def test_no_financials_status_is_kept_on_skip(monkeypatch, tmp_path):
    monkeypatch.setattr(download, "PDF_DIR", tmp_path)
    monkeypatch.setattr(download, "XBRL_DIR", tmp_path)
    (tmp_path / "XX.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "XX.json").write_text("{}")
    monkeypatch.setattr(download, "http_get", lambda *a, **k: pytest.fail("no network"))
    filings = {"XX": {"status": "no_financials"}}
    assert download.process({"ticker": "XX", "cik": "0000000001"}, "ua", filings) == "no_financials"

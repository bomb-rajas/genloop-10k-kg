"""Download the latest 10-K per company from EDGAR, convert it to PDF, and fetch XBRL companyfacts.

Run: .venv/bin/python -m src.download [--tickers AAPL,JPM]
Writes data/raw_html/{T}.html, data/pdfs/{T}.pdf, data/xbrl/{T}.json and data/filings.json.
EDGAR HTML is only converted to PDF here; facts are never parsed from it.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pdfplumber
import requests

from src.config import DATA_DIR, PDF_DIR, RAW_HTML_DIR, ROOT, XBRL_DIR, load_companies, load_env

FILINGS_PATH = DATA_DIR / "filings.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# Same flags for every company so page numbers are comparable across filings.
CHROME_FLAGS = [
    "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
    "--no-first-run", "--no-default-browser-check", "--virtual-time-budget=30000",
]
CHROME_TIMEOUT = 180
MIN_INTERVAL = 0.2  # 5 requests/s ceiling, under SEC's 10/s limit
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF = [2, 4, 8]  # seconds before retry 1, 2, 3
TIMEOUT = 120
FIN_SKIP_FRAC = 0.15  # first 15% of pages are selected-data/MD&A summaries, not statements
DONE = {"ok", "no_financials"}


class Throttle:
    """Keeps consecutive requests at least min_interval seconds apart."""

    def __init__(self, min_interval: float = MIN_INTERVAL):
        self.min_interval = min_interval
        self.last = 0.0

    def wait(self) -> None:
        gap = time.monotonic() - self.last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self.last = time.monotonic()


_throttle = Throttle()


def http_get(url: str, user_agent: str) -> requests.Response:
    """GET with throttle and retries on RETRY_STATUS. The User-Agent is never printed."""
    err = "no attempt"
    for attempt in range(len(BACKOFF) + 1):
        _throttle.wait()
        try:
            r = requests.get(url, headers={"User-Agent": user_agent}, timeout=TIMEOUT)
        except requests.RequestException as e:
            err = repr(e)
        else:
            if r.status_code not in RETRY_STATUS:
                r.raise_for_status()
                return r
            err = f"HTTP {r.status_code}"
        if attempt < len(BACKOFF):
            time.sleep(BACKOFF[attempt])
    raise RuntimeError(f"GET {url} failed after {len(BACKOFF)} retries: {err}")


def latest_10k(submissions: dict) -> dict:
    """Newest filing whose form is exactly '10-K'. 10-K/A, 10-Q and 8-K rows are skipped."""
    recent = submissions["filings"]["recent"]
    rows = [dict(zip(recent.keys(), vals)) for vals in zip(*recent.values())]
    tenks = [r for r in rows if r["form"] == "10-K"]
    if not tenks:
        raise LookupError("no 10-K in submissions filings.recent")
    best = max(tenks, key=lambda r: r["filingDate"])
    return {
        "accession": best["accessionNumber"],
        "filing_date": best["filingDate"],
        "report_date": best["reportDate"],
        "primary_document": best["primaryDocument"],
    }


def filing_url(cik: str, accession: str, primary_document: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_document}"


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Print one HTML file to PDF with headless Chrome, using a throwaway profile."""
    profile = tempfile.mkdtemp(prefix="chrome-profile-")
    tmp_pdf = pdf_path.with_name(pdf_path.stem + ".tmp.pdf")
    try:
        subprocess.run(
            [CHROME, *CHROME_FLAGS, f"--user-data-dir={profile}", f"--print-to-pdf={tmp_pdf}",
             html_path.resolve().as_uri()],
            timeout=CHROME_TIMEOUT, check=True, capture_output=True,
        )
        if not tmp_pdf.exists() or tmp_pdf.stat().st_size == 0:
            raise RuntimeError("Chrome wrote no PDF")
        tmp_pdf.replace(pdf_path)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        tmp_pdf.unlink(missing_ok=True)


def is_balance_sheet(text: str | None) -> bool:
    # "total assets" is the table line; a liabilities/equity/shareholders line confirms it is the statement, not a summary.
    t = (text or "").lower()
    return "total assets" in t and any(k in t for k in ("total liabilities", "total equity", "shareholders", "stockholders"))


def financials_page(page_texts: list[str]) -> int | None:
    """1-based number of the first balance-sheet page after the first 15% of pages, or None."""
    skip = int(len(page_texts) * FIN_SKIP_FRAC)
    return next((i for i, t in enumerate(page_texts, 1) if i > skip and is_balance_sheet(t)), None)


def find_financials_page(pdf_path: Path) -> int | None:
    with pdfplumber.open(pdf_path) as pdf:
        skip = int(len(pdf.pages) * FIN_SKIP_FRAC)
        for i, page in enumerate(pdf.pages, 1):
            if i > skip and is_balance_sheet(page.extract_text()):
                return i
    return None


def process(co: dict, user_agent: str, filings: dict) -> str:
    """Fetch, convert and record one company. Returns the status written to filings.json."""
    t, cik = co["ticker"], co["cik"]
    pdf = PDF_DIR / f"{t}.pdf"
    prev = filings.get(t, {})
    if prev.get("status") in DONE and pdf.exists():
        print(f"SKIP {t}: PDF already present")
    else:
        sub = http_get(f"https://data.sec.gov/submissions/CIK{cik}.json", user_agent).json()
        f = latest_10k(sub)
        url = filing_url(cik, f["accession"], f["primary_document"])
        html = RAW_HTML_DIR / f"{t}.html"
        html.write_bytes(http_get(url, user_agent).content)
        html_to_pdf(html, pdf)
        page = find_financials_page(pdf)
        status = "ok" if page else "no_financials"
        filings[t] = {
            "accession": f["accession"], "filing_date": f["filing_date"], "report_date": f["report_date"],
            "url": url, "form": "10-K", "pdf": str(pdf.relative_to(ROOT)), "status": status,
            "financials_page": page,
        }
        print(f"DONE {t}: {status}, {f['filing_date']}, financials page {page}")
    xbrl = XBRL_DIR / f"{t}.json"
    if not xbrl.exists():
        xbrl.write_bytes(http_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", user_agent).content)
    return filings[t]["status"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers", help="comma-separated tickers; default all companies in config/companies.yaml")
    args = ap.parse_args(argv)
    load_env()
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        sys.exit("SEC_USER_AGENT is missing from .env")
    companies = load_companies()
    if args.tickers:
        want = {t.strip().upper() for t in args.tickers.split(",") if t.strip()}
        known = {c["ticker"] for c in companies}
        if want - known:
            sys.exit(f"unknown tickers: {sorted(want - known)}")
        companies = [c for c in companies if c["ticker"] in want]
    for d in (DATA_DIR, RAW_HTML_DIR, PDF_DIR, XBRL_DIR):
        d.mkdir(parents=True, exist_ok=True)
    filings = json.loads(FILINGS_PATH.read_text(encoding="utf-8")) if FILINGS_PATH.exists() else {}
    failures = []
    for co in companies:
        t = co["ticker"]
        try:
            status = process(co, user_agent, filings)
            if status == "no_financials":
                print(f"WARNING {t}: no 'CONSOLIDATED BALANCE SHEET' text in the PDF (likely Exhibit 13); flagged, not substituted")
        except Exception as e:  # keep going; one bad company must not stop the run
            failures.append(t)
            filings[t] = {**filings.get(t, {}), "status": f"error: {e}"}
            print(f"FAILED {t}: {e}")
        FILINGS_PATH.write_text(json.dumps(filings, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for c in companies if filings.get(c["ticker"], {}).get("status") == "ok")
    flagged = [c["ticker"] for c in companies if filings.get(c["ticker"], {}).get("status") == "no_financials"]
    print(f"SUMMARY: {len(companies)} companies, ok={ok}, no_financials={flagged or 'none'}, failed={failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

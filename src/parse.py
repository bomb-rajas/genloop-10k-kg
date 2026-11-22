"""Parse 10-K PDFs: per-page text, and the income statement, balance sheet and cash flow statement rows.

Run: .venv/bin/python -m src.parse [--tickers AAPL,JPM] [--force]
Writes data/parsed/{T}.json. Page numbers are 1-based PDF page indexes (the citation page).
PDF only: no HTML is read. Existing outputs are skipped unless --force.
"""
import argparse
import json
import logging
import re
import sys
import time
from multiprocessing import Pool

import pdfplumber

from src.config import PARSED_DIR, PDF_DIR, load_companies
from src.tables import (
    extract_years, find_scale, header_text, is_header_row, merge_split_tables,
    parse_text_lines, pick_year_column, rows_from_table,
)

# Titles are matched anywhere in one of the first 8 cleaned lines. Lines ending in a page number (table of
# contents) or naming condensed or parent-only statements are skipped.
_TITLE_BODY = {
    "income_statement": (r"(?=.*(?:statement|consolidated))(?:consolidated\s+)?(?:statements?\s+of\s+)?"
                         r"(?:consolidated\s+)?(?:income|operations|earnings)(?:\s+statements?)?(?:\s*\(loss\))?"),
    "balance_sheet": (r"(?:consolidated\s+)?(?:balance\s+sheets?|statements?\s+of\s+(?:consolidated\s+)?"
                      r"financial\s+(?:position|condition))"),
    "cash_flow_statement": r"(?:consolidated\s+)?(?:statements?\s+of\s+cash\s+flows?|cash\s+flows?\s+statements?)",
}
TITLES = {k: re.compile(v, re.I) for k, v in _TITLE_BODY.items()}
TITLE_SKIP = re.compile(r"condensed|parent\s+company|\s\d{1,3}$", re.I)
# A row that must exist on the statement page. Banks and some filers have no 'Total assets' label
# (Merck: '$ 136,866 $ 117,106' under 'Total equity'), and CF rows say 'cash provided by operations'.
KEY_ROWS = {
    "income_statement": re.compile(r"\bnet\s+(income|earnings|\(loss\)|loss)\b", re.I),
    "balance_sheet": re.compile(r"^total\s+(current\s+)?(assets|liabilities)\b|^total\b.*\b(equity|stockholders|shareholders)\b", re.I),
    "cash_flow_statement": re.compile(r"operating\s+activities|\b(by|from)\s+operations\b", re.I),
}
MIN_VALUE_ROWS = 10        # value rows needed for a page to count as a statement
MAX_CONTINUATION = 2       # pages after the primary page searched for a continuation
TABLE_FALLBACK_BELOW = 5   # use pdfplumber tables for a page only when text parsing gives fewer rows
NON_CONTINUATION = re.compile(r"notes\s+to|statements?\s+of|balance\s+sheet|comprehensive", re.I)
STATEMENT_WORD = re.compile(r"\bstatements?\b|balance sheets?", re.I)
KINDS = list(TITLES)

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def _title_lines(text):
    """First 8 non-empty lines without table-of-contents page-header noise ('Table of Contents', 'ImageNN.jpg')."""
    out = []
    for ln in (text or "").splitlines():
        ln = re.sub(r"Table of Contents|Image\d+\.\w+", "", ln, flags=re.I).strip()
        if ln:
            out.append(ln)
    return out[:8]


def title_kinds(text):
    """Statement kinds whose title is on this page (first 8 lines)."""
    lines = [ln for ln in _title_lines(text) if not TITLE_SKIP.search(ln)]
    return [k for k in KINDS if any(TITLES[k].search(ln) for ln in lines)]


def key_kinds(text):
    """Statement kinds whose key row (with >=2 values) is on this page, if the page is dense enough."""
    rows = parse_text_lines(text)
    if len([r for r in rows if len(r["values"]) >= 2]) < MIN_VALUE_ROWS:
        return []
    out = []
    for k in KINDS:
        for r in rows:
            if len(r["values"]) >= 2 and KEY_ROWS[k].search(r["label"]) and not (k == "income_statement" and re.search(r"\bper\b", r["label"], re.I)):
                out.append(k)
                break
    return out


def is_continuation(text):
    """A page that carries on a statement: numeric rows, no statement heading, no notes heading."""
    lines = _title_lines(text)
    if NON_CONTINUATION.search(" ".join(lines)) or STATEMENT_WORD.search(" ".join(lines[:3])):
        return False
    rows = parse_text_lines(text)
    nonempty = [ln for ln in (text or "").splitlines() if ln.strip()]
    return len(rows) >= 3 and len(rows) / max(len(nonempty), 1) >= 0.3


def find_statements(page_texts):
    """{kind: [1-based pages]}: the first page with a key row whose title is on that page, or on the page
    before (statement starts after its title, e.g. GS cash flows), then up to MAX_CONTINUATION pages."""
    titles = [title_kinds(t) for t in page_texts]
    keys = [key_kinds(t) for t in page_texts]
    found = {}
    for kind in KINDS:
        for i in range(len(page_texts)):
            if kind not in keys[i]:
                continue
            if kind in titles[i]:
                start = i
            elif i > 0 and kind in titles[i - 1]:
                start = i - 1
            else:
                continue
            pages = [start]
            j = start + 1
            while j < len(page_texts) and len(pages) <= MAX_CONTINUATION and is_continuation(page_texts[j]):
                pages.append(j)
                j += 1
            found[kind] = [p + 1 for p in pages]
            break
    return found


def _page_rows(pdf, page_no, text):
    """Text-line rows for one page; pdfplumber table rows only when text parsing finds too few."""
    rows = parse_text_lines(text)
    if len(rows) < TABLE_FALLBACK_BELOW and pdf is not None:
        rows = []
        for table in pdf.pages[page_no - 1].extract_tables() or []:
            rows += rows_from_table(table)
    return rows


def build_statement(pdf, page_texts, pages):
    primary = page_texts[pages[0] - 1]
    # The title page often has no unit or year line; the units and years sit on the page after it.
    head = "\n".join(header_text(page_texts[p - 1]) for p in pages)
    scale, snippet = find_scale(head)
    for p in [pages[0]] + pages:
        if scale is None:
            scale, snippet = find_scale(page_texts[p - 1])
    columns = extract_years(head)
    newest = pick_year_column(head)
    merged, width = [], len(columns)
    for p in pages:
        rows = []
        for r in _page_rows(pdf, p, page_texts[p - 1]):
            vals = r["values"]
            if width and len(vals) == width + 1 and vals[0].is_integer() and abs(vals[0]) <= 99:
                vals = vals[1:]  # leading note-reference column
            rows.append({"label": r["label"], "values": vals, "page": p})
        merged = merge_split_tables(merged, [r for r in rows if not is_header_row(r)])
    return {"pages": pages, "scale": scale, "scale_source_text": snippet, "columns": columns,
            "newest_col": newest, "rows": merged}


def parse_pdf(ticker, cached=None):
    """Page text (from the PDF, or from the cached JSON when given) then statement classification.
    The PDF is opened only for table fallback, which needs it."""
    path = PDF_DIR / f"{ticker}.pdf"
    with pdfplumber.open(path) as pdf:
        if cached is None:
            page_texts = [(page.extract_text() or "") for page in pdf.pages]
        else:
            page_texts = [cached["pages"][str(i + 1)] for i in range(cached["n_pages"])]
        found = find_statements(page_texts)
        statements = {}
        for kind in KINDS:
            if kind in found:
                statements[kind] = build_statement(pdf, page_texts, found[kind])
            else:
                statements[kind] = {"pages": [], "scale": None, "scale_source_text": None,
                                    "columns": [], "newest_col": None, "rows": []}
    return {"ticker": ticker, "n_pages": len(page_texts),
            "pages": {str(i + 1): t for i, t in enumerate(page_texts)}, "statements": statements}


def run_company(ticker, force=False, reuse_pages=False):
    """Worker: parse one company and write data/parsed/{ticker}.json. Returns (ticker, secs, n_pages, error).
    reuse_pages: rebuild statements from the page text already in the JSON (no text extraction)."""
    out = PARSED_DIR / f"{ticker}.json"
    if out.exists() and not force and not reuse_pages:
        return ticker, 0.0, None, "skipped"
    t0 = time.time()
    try:
        cached = json.loads(out.read_text()) if reuse_pages and out.exists() else None
        result = parse_pdf(ticker, cached)
    except Exception as exc:  # one bad PDF must not stop the batch
        return ticker, time.time() - t0, None, f"{type(exc).__name__}: {exc}"
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False))
    return ticker, time.time() - t0, result["n_pages"], None


def summarize(ticker):
    """One line of facts for a parsed company, from its JSON."""
    path = PARSED_DIR / f"{ticker}.json"
    if not path.exists():
        return {"ticker": ticker, "missing": ["no output"]}
    data = json.loads(path.read_text())
    st = data["statements"]
    missing = [k for k in KINDS if not st[k]["pages"]]
    missing += [f"{k} scale" for k in KINDS if st[k]["pages"] and st[k]["scale"] is None]
    return {"ticker": ticker, "data": data, "missing": missing}


def show_detail(s):
    data = s["data"]
    print(f"== {data['ticker']} pages={data['n_pages']}")
    for kind in KINDS:
        st = data["statements"][kind]
        print(f"   {kind}: pages={st['pages']} scale={st['scale']} ({st['scale_source_text']}) "
              f"columns={st['columns']} newest_col={st['newest_col']} rows={len(st['rows'])}")
    checks = [("total_assets", "balance_sheet", r"^total assets"),
              ("net_income", "income_statement", r"^net (income|earnings)\b(?!.*per)"),
              ("total_revenues", "income_statement", r"^(total\s+(net\s+)?(revenues?|net sales)|net sales|total revenues?)\b")]
    for name, kind, pat in checks:
        hit = next((r for r in data["statements"][kind]["rows"] if re.search(pat, r["label"], re.I)), None)
        print(f"   {name}: {hit['label'] + ' ' + str(hit['values'][:3]) + ' p' + str(hit['page']) if hit else 'NOT FOUND'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parse 10-K PDFs into data/parsed/{ticker}.json")
    ap.add_argument("--tickers", help="comma-separated tickers (default: all companies)")
    ap.add_argument("--force", action="store_true", help="re-parse even if output exists")
    ap.add_argument("--reuse-pages", action="store_true", help="rebuild statements from page text already in the JSON")
    args = ap.parse_args(argv)
    companies = [c["ticker"] for c in load_companies()]
    if args.tickers:
        wanted = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        unknown = [t for t in wanted if t not in companies]
        if unknown:
            print(f"unknown tickers: {unknown}", file=sys.stderr)
            return 2
        companies = wanted
    t0 = time.time()
    with Pool(4) as pool:
        for ticker, secs, n_pages, err in pool.imap_unordered(_run, [(t, args.force, args.reuse_pages) for t in companies]):
            if err == "skipped":
                print(f"[{ticker}] skip (exists; use --force)", flush=True)
            elif err:
                print(f"[{ticker}] FAILED after {secs:.1f}s: {err}", flush=True)
            else:
                print(f"[{ticker}] done {n_pages} pages in {secs:.1f}s", flush=True)
    print(f"parsed {len(companies)} companies in {time.time() - t0:.0f}s")
    summaries = [summarize(t) for t in companies]
    if args.tickers:
        for s in summaries:
            if "data" in s:
                show_detail(s)
            else:
                print(f"== {s['ticker']}: {s['missing']}")
    lacking = [(s["ticker"], s["missing"]) for s in summaries if s["missing"]]
    print(f"\ncompanies lacking a statement or scale: {len(lacking)} of {len(summaries)}")
    for ticker, missing in lacking:
        print(f"  {ticker}: {', '.join(missing)}")
    return 0


def _run(args):
    return run_company(*args)


if __name__ == "__main__":
    sys.exit(main())

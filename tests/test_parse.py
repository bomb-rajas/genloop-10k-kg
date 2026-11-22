from src.parse import find_statements, is_continuation, is_statement_layout, key_kinds, title_kinds, TITLE_SKIP
from src.tables import find_scale, parse_line

INCOME_ROWS = "\n".join(f"Line item {i} 1,000 900 800" for i in range(10)) + "\nNet income 2,000 1,800 1,600"
BS_ROWS = "\n".join(f"Asset {i} 100 90" for i in range(10)) + "\nTotal assets 5,000 4,800"
CF_ROWS = "\n".join(f"Adj {i} 50 40 30" for i in range(10)) + "\nNet cash provided by operating activities 7,000 6,000 5,000"


def test_title_matched_anywhere_in_first_lines():
    # company prefix and 'Table of Contents' header must not hide the title
    assert title_kinds("Table of Contents\nCompany Inc.\nCONSOLIDATED STATEMENTS OF INCOME\n") == ["income_statement"]
    assert title_kinds("Pfizer Inc. Consolidated Statement of Cash Flows") == ["cash_flow_statement"]


def test_singular_and_bank_titles():
    assert title_kinds("CONSOLIDATED STATEMENT OF CASH FLOWS") == ["cash_flow_statement"]
    assert title_kinds("Consolidated Balance Sheet") == ["balance_sheet"]
    assert title_kinds("Consolidated Statement of Financial Condition") == ["balance_sheet"]


def test_toc_line_ending_in_page_number_is_skipped():
    assert title_kinds("Consolidated Statements of Income 52") == []
    assert TITLE_SKIP.search("Consolidated Balance Sheets 44")


def test_condensed_and_parent_only_statements_are_skipped():
    assert title_kinds("Condensed Consolidated Balance Sheet") == []
    assert title_kinds("Parent Company Only Balance Sheets") == []


def test_key_rows_bank_and_cf_variants():
    # Merck style: no 'Total assets' label, but BS still identified by 'Total liabilities'
    assert key_kinds(BS_ROWS.replace("Total assets", "Total liabilities")) == ["balance_sheet"]
    assert key_kinds(CF_ROWS.replace("operating activities", "operations")) == ["cash_flow_statement"]
    assert key_kinds(INCOME_ROWS) == ["income_statement"]


def test_key_row_needs_dense_page():
    assert key_kinds("Net income 2,000 1,800") == []


def test_title_on_previous_page_starts_statement():
    # GS/META style: title-only page, then data page with no title
    cf_title = "Consolidated Statement of Cash Flows\nin millions"
    pages = [cf_title, CF_ROWS]
    assert find_statements(pages) == {"cash_flow_statement": [1, 2]}


def test_continuation_pages_collected_until_non_numeric():
    pages = ["CONSOLIDATED BALANCE SHEETS\n(in millions)\n" + BS_ROWS, BS_ROWS, BS_ROWS, "Notes to Consolidated Financial Statements\nText only"]
    found = find_statements(pages)
    assert found["balance_sheet"] == [1, 2, 3]


def test_find_scale_parenthesised_units():
    assert find_scale("(Millions, except per share)")[0] == 1e6
    assert find_scale("(MILLIONS, EXCEPT PER SHARE DATA)")[0] == 1e6
    assert find_scale("(Dollars in millions)")[0] == 1e6
    assert find_scale("(thousands)")[0] == 1e3


def test_parse_line_glued_dollar_splits():
    # Citigroup prints '(67,632)$ (19,669)$' with no space
    label, values = parse_line("Net cash provided by (used in) operating activities $ (67,632)$ (19,669)$ (73,416)")
    assert values == [-67632.0, -19669.0, -73416.0]


import json
import types

from src import parse


def _bs_page(note_col, total="Total assets 5,000 4,800"):
    head = "CONSOLIDATED BALANCE SHEETS\n(In millions, except per share amounts)\nDecember 31,\n2025 2024\n"
    note = " 1" if note_col else ""  # a note-reference number before the two year values
    rows = [f"Asset line {chr(65 + i)}{note} 100 90" for i in range(10)]
    return head + "\n".join(rows) + "\n" + total


def test_build_statement_drops_majority_note_column():
    st = parse.build_statement(None, [_bs_page(note_col=True)], [1])
    assert st["scale"] == 1e6 and st["columns"] == [2025, 2024]
    total = [r for r in st["rows"] if r["label"] == "Total assets"][0]
    assert total["values"] == [5000.0, 4800.0]
    assert [r for r in st["rows"] if r["label"] == "Asset line A"][0]["values"] == [100.0, 90.0]


def test_build_statement_keeps_values_when_note_column_is_minority():
    # One stray row with width+1 values must not drop a real column from every row.
    page = _bs_page(note_col=False, total="Odd row 3 5,000 4,800")
    st = parse.build_statement(None, [page], [1])
    assert [r for r in st["rows"] if r["label"] == "Odd row"][0]["values"] == [3.0, 5000.0, 4800.0]
    assert [r for r in st["rows"] if r["label"] == "Asset line A"][0]["values"] == [100.0, 90.0]


def test_build_statement_too_narrow_header_keeps_all_values():
    # Header shows one year but rows have two: no note column is inferred from a single header year.
    page = "CONSOLIDATED BALANCE SHEETS\n(In thousands)\n2025\n" + "\n".join(
        f"Asset {i} 100 90" for i in range(10)) + "\nTotal assets 5,000 4,800"
    st = parse.build_statement(None, [page], [1])
    assert st["scale"] == 1e3 and st["columns"] == [2025]
    assert [r for r in st["rows"] if r["label"] == "Total assets"][0]["values"] == [5000.0, 4800.0]


def test_run_company_writes_atomic_json_and_skips_unreadable_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(parse, "PARSED_DIR", tmp_path)
    monkeypatch.setattr(parse, "PDF_DIR", tmp_path)
    page1 = "CONSOLIDATED STATEMENTS OF INCOME\n(In millions)\n2025 2024\n" + "\n".join(
        f"Item {chr(65 + i)} 10 9" for i in range(10)) + "\nNet income 2,000 1,800"
    page2 = _bs_page(note_col=False)
    cf = "CONSOLIDATED STATEMENTS OF CASH FLOWS\n(In millions)\n2025 2024\n" + "\n".join(
        f"Adj {chr(65 + i)} 5 4" for i in range(10)) + "\nNet cash provided by operating activities 7,000 6,000"
    texts = [page1, page2, cf]
    monkeypatch.setattr(parse.pdfplumber, "open", lambda path: _FakePdf(texts))
    (tmp_path / "TST.json").write_text("{not json")  # unreadable cache: parse from the PDF text instead
    ticker, _, n, err = parse.run_company("TST", force=True, reuse_pages=True)
    assert err is None and n == 3
    out = json.loads((tmp_path / "TST.json").read_text())
    assert out["statements"]["income_statement"]["scale"] == 1e6
    assert out["statements"]["income_statement"]["columns"] == [2025, 2024]
    assert out["statements"]["balance_sheet"]["pages"] == [2]
    ni = [r for r in out["statements"]["income_statement"]["rows"] if r["label"] == "Net income"][0]
    assert ni["values"] == [2000.0, 1800.0] and ni["page"] == 1
    assert not (tmp_path / "TST.json.tmp").exists()


def test_read_cached_returns_none_when_unreadable(tmp_path):
    assert parse._read_cached(tmp_path / "missing.json") is None
    (tmp_path / "bad.json").write_text("{")
    assert parse._read_cached(tmp_path / "bad.json") is None


class _FakePdf:
    def __init__(self, texts):
        self.pages = [types.SimpleNamespace(extract_text=lambda t=t: t) for t in texts]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_mdna_sentence_and_overview_headings_are_not_titles():
    # NVDA p57, C p16, MS p82: title words inside MD&A sentences or overview headings
    assert title_kinds("Consolidated Statements of Income expressed as a percentage of revenue") == []
    assert title_kinds("BALANCE SHEET OVERVIEW") == []
    assert title_kinds("Income Statement Information") == []


def test_company_prefixed_lowercase_title_is_kept():
    # JNJ prints 'Johnson & Johnson and subsidiaries consolidated balance sheets'
    assert title_kinds("Johnson & Johnson and subsidiaries consolidated balance sheets") == ["balance_sheet"]


def test_percent_of_revenue_and_segment_pages_are_rejected():
    pct = "Revenue 100.0 % 100.0 %\nCost of revenue 28.9 % 25.1 %\nGross margin 71.1 % 74.9 %\nR&D 8.6 % 9.9 %"
    assert not is_statement_layout(pct)
    seg = "Segment table 2025 2024\n" + "\n".join(f"Segment {i} 1,000 900 800 700 600" for i in range(3))
    assert not is_statement_layout(seg)
    assert is_statement_layout(INCOME_ROWS)


def test_percent_change_header_is_rejected():
    assert not is_statement_layout("Consolidated Balance Sheet\n2025 2024 % change\n" + BS_ROWS)


def test_continued_bank_page_is_a_continuation():
    text = "Consolidated Balance Sheet (Continued)\nLiabilities\n" + BS_ROWS
    assert is_continuation(text)
    assert not is_continuation("Notes to consolidated financial statements\n" + BS_ROWS)

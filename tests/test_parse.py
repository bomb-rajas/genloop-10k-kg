from src.parse import find_statements, key_kinds, title_kinds, TITLE_SKIP
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

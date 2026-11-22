import pytest

from src.tables import (
    detect_scale, extract_years, find_scale, header_text, is_header_row, merge_split_tables,
    parse_line, parse_number, parse_text_lines, pick_year_column, rows_from_table,
)


# parse_number
@pytest.mark.parametrize("cell, expected", [
    ("$ 1,234.5", 1234.5),
    ("$1,234", 1234.0),
    ("1,234.5", 1234.5),
    ("12.3%", 12.3),
    ("(1,234)", -1234.0),
    ("(1,234.5)", -1234.5),
    ("$ (36)", -36.0),
    ("−1,234", -1234.0),          # unicode minus
    ("-1,234", -1234.0),
    ("1 234", 1234.0),            # inner space
    ("—", 0.0),
    ("–", 0.0),
    ("-", 0.0),
    ("--", 0.0),
    ("(—)", 0.0),
    ("1,234(1)", 1234.0),         # footnote in parentheses
    ("1,234*", 1234.0),
    ("1,234†", 1234.0),
    ("1,234 (a)", 1234.0),
    ("(1,234)(a)", -1234.0),      # negative with footnote after the parentheses
    ("0", 0.0),
    ("$ 36,305", 36305.0),
])
def test_parse_number_values(cell, expected):
    assert parse_number(cell) == expected


@pytest.mark.parametrize("cell", ["", "   ", None, "Total", "abc", "$", "(", "1,23", "n/a"])
def test_parse_number_non_numbers(cell):
    assert parse_number(cell) is None


def test_parse_number_negative_zero_is_not_negative():
    assert parse_number("(0)") == 0.0


# parse_line: label and values from one text line
def test_parse_line_parentheses_and_dollar_cells():
    assert parse_line("Retained earnings/(Accumulated deficit) 13,700 (14,264)") == (
        "Retained earnings/(Accumulated deficit)", [13700.0, -14264.0])


def test_parse_line_split_dollar_and_paren_tokens():
    assert parse_line("Total assets $ 404,548 $ 359,241") == ("Total assets", [404548.0, 359241.0])
    assert parse_line("Other ( 1,234 ) 5") == ("Other", [-1234.0, 5.0])


def test_parse_line_dash_is_zero_value():
    assert parse_line("Impairment — 2,000") == ("Impairment", [0.0, 2000.0])


def test_parse_line_footnote_letter_after_numbers_is_dropped():
    assert parse_line("Revenue 1,000 (a)") == ("Revenue", [1000.0])


def test_parse_line_keeps_footnote_letter_inside_label():
    label, vals = parse_line("Notes payable (a) 100")
    assert label == "Notes payable (a)" and vals == [100.0]


def test_parse_line_no_trailing_numbers_is_none():
    assert parse_line("Consolidated Balance Sheets") is None
    assert parse_line("(In millions, except per share)") is None


def test_parse_line_percent_value():
    assert parse_line("Effective tax rate 15.6 % 16.2 %") == ("Effective tax rate", [15.6, 16.2])


# scale
@pytest.mark.parametrize("text, scale", [
    ("(In millions, except number of shares)", 1_000_000),
    ("(in millions)", 1_000_000),
    ("(In thousands, except per share)", 1_000),
    ("$ in billions", 1_000_000_000),
    ("(Dollars in millions)", 1_000_000),
    ("(Amounts in thousands)", 1_000),
    ("(in dollars)", 1),
    ("(In units)", 1),
])
def test_detect_scale_headers(text, scale):
    assert detect_scale(text) == scale


def test_detect_scale_absent_is_none():
    assert detect_scale("CONSOLIDATED BALANCE SHEETS\nCash and cash equivalents 36,305") is None
    assert detect_scale("") is None
    assert detect_scale(None) is None


def test_find_scale_returns_source_text():
    assert find_scale("Apple Inc.\n(In millions, except per share)") == (1_000_000, "In millions")


def test_find_scale_none_when_absent():
    assert find_scale("no unit here") == (None, None)


# year columns
def test_extract_years_order_and_unique():
    assert extract_years("September 26, 2026 September 27, 2025 2026") == [2026, 2025]


def test_pick_year_column_default_newest_from_date_header():
    assert pick_year_column("Dec 31, 2025 Dec 31, 2024") == 0


def test_pick_year_column_newest_when_order_is_oldest_first():
    assert pick_year_column("2023 2024 2025") == 2


def test_pick_year_column_target_year():
    assert pick_year_column("2025 2024 2023", target_year=2024) == 1


def test_pick_year_column_target_absent_is_none():
    assert pick_year_column("2025 2024", target_year=2019) is None


def test_pick_year_column_no_year_is_none():
    assert pick_year_column("Cash and cash equivalents") is None


def test_pick_year_column_accepts_cell_list():
    assert pick_year_column(["Dec 31, 2025", "Dec 31, 2024"]) == 0


# header text: lines above the first line item
def test_header_text_stops_at_first_line_item():
    text = ("Apple Inc.\nCONSOLIDATED BALANCE SHEETS\n(In millions, except number of shares)\n"
            "September 26, September 27,\n2026 2025\nCash and cash equivalents $ 36,305 $ 35,934\nTotal assets 1 2")
    head = header_text(text)
    assert "2026 2025" in head and "In millions" in head
    assert "Cash and cash" not in head


def test_is_header_row_dates_and_years():
    assert is_header_row({"label": "", "values": [2026.0, 2025.0]})
    assert is_header_row({"label": "September 26, 2026", "values": []})
    assert not is_header_row({"label": "Total assets", "values": [404548.0, 359241.0]})


# text-line parsing
def test_parse_text_lines_label_only_line_is_skipped():
    rows = parse_text_lines("CONSOLIDATED BALANCE SHEETS\nCash $ 1 $ 2\nTotal assets 404,548 359,241\n")
    assert rows == [{"label": "Cash", "values": [1.0, 2.0]},
                    {"label": "Total assets", "values": [404548.0, 359241.0]}]


def test_parse_text_lines_joins_wrapped_label():
    text = "Common stock and paid-in capital, $0.00001 par value: 50,000,000 shares\nauthorized; 24,000 and 25,000 shares issued 104,815 93,568\n"
    rows = parse_text_lines(text)
    assert len(rows) == 1
    assert rows[0]["label"].startswith("Common stock and paid-in capital")
    assert rows[0]["label"].endswith("authorized; 24,000 and 25,000 shares issued")
    assert rows[0]["values"] == [104815.0, 93568.0]


def test_parse_text_lines_empty():
    assert parse_text_lines("") == []
    assert parse_text_lines(None) == []


# pdfplumber table rows
def test_rows_from_table_merges_split_dollar_and_paren_cells():
    table = [
        ["Total assets", "$", "404,548", "$", "359,241"],
        ["Accumulated deficit", "(14,264", ")", "", ""],
        ["Impairment", "—", "", "2,000", ""],
        [None, None, None],
    ]
    rows = rows_from_table(table)
    assert rows[0] == {"label": "Total assets", "values": [404548.0, 359241.0]}
    assert rows[1] == {"label": "Accumulated deficit", "values": [-14264.0]}
    assert rows[2] == {"label": "Impairment", "values": [0.0, 2000.0]}
    assert len(rows) == 3


def test_rows_from_table_merges_label_cells_with_newline():
    rows = rows_from_table([["Net sales\nand other", "100", "90"]])
    assert rows == [{"label": "Net sales and other", "values": [100.0, 90.0]}]


def test_rows_from_table_empty_and_none():
    assert rows_from_table(None) == []
    assert rows_from_table([]) == []


# table continued across two pages
def test_merge_split_tables_joins_continuation():
    prev = [{"label": "Total assets", "values": [1.0, 2.0], "page": 51}]
    nxt = [{"label": "Total liabilities", "values": [3.0, 4.0], "page": 52},
           {"label": "", "values": []}]
    merged = merge_split_tables(prev, nxt)
    assert [r["label"] for r in merged] == ["Total assets", "Total liabilities"]
    assert merged[1]["page"] == 52


def test_merge_split_tables_does_not_alias_inputs():
    prev = [{"label": "A", "values": [1.0]}]
    merged = merge_split_tables(prev, [])
    merged[0]["values"].append(9.0)
    assert prev[0]["values"] == [1.0]

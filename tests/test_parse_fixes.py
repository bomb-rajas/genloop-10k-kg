from src.extract import find_metric_row
from src.tables import label_unlabeled_totals, parse_line, parse_text_lines
from src.parse import is_repeated_title
import yaml


def test_footnote_marker_not_value():
    assert parse_line("Net sales 100 90 (1)")[1] == [100.0, 90.0]


def test_eps_heading_prefixed():
    text = ("Diluted earnings per share:\nIncome from continuing operations 1.00 0.90\nNet income 1.10 0.95\n"
            "Weighted-average shares 500 480\nNet income 7,000 6,000")
    labels = [r["label"] for r in parse_text_lines(text)]
    assert labels[1] == "Diluted earnings per share Net income"
    assert labels[-1] == "Net income"


def test_eps_picks_net_over_continuing():
    m = next(x for x in yaml.safe_load(open("config/metrics.yaml"))["metrics"] if x["name"] == "EPS")
    stmt = {"columns": [2024, 2023], "rows": [
        {"label": "Diluted earnings per share Income from continuing operations", "values": [6.0, 5.0]},
        {"label": "Diluted earnings per share Net income", "values": [7.0, 6.0]}]}
    assert find_metric_row(stmt, m)[0]["values"][0] == 7.0


def test_unlabeled_totals():
    text = ("Cash 10 8\nGoodwill 5 5\nTotal current assets 50 40\n$ 100 90\nTotal liabilities 60 50\n"
            "Total equity 40 40\n$ 100 90")
    rows, _ = label_unlabeled_totals(parse_text_lines(text, keep_unlabeled=True))
    assert [r["label"] for r in rows if r["label"].startswith("Total")][-1] == "Total liabilities and equity"
    assert any(r["label"] == "Total assets" for r in rows)


def test_unlabeled_subtotal_in_equity_block_dropped():
    text = "Total liabilities 60 50\nRetained earnings 115 104\n115 104\nTotal equity 40 40\n$ 200 190"
    rows, _ = label_unlabeled_totals(parse_text_lines(text, keep_unlabeled=True), seen_assets=True)
    assert sum(r["label"] == "Total liabilities and equity" for r in rows) == 1


def test_repeated_title_continuation():
    text = "Consolidated Balance Sheet\n(dollars in millions)\nA 1 2\nB 3 4\nC 5 6\n"
    assert is_repeated_title(text, "balance_sheet", ["balance_sheet"])


def test_capex_related_to_and_bank_revenue():
    cfg = yaml.safe_load(open("config/metrics.yaml"))
    capex = next(x for x in cfg["metrics"] if x["name"] == "CapEx")
    stmt = {"columns": [2024, 2023], "rows": [
        {"label": "Purchases related to property and equipment and intangible assets", "values": [-6.0, -3.0]}]}
    assert find_metric_row(stmt, capex)[0] is not None
    rev = next(x for x in cfg["metrics"] if x["name"] == "Revenue")
    assert rev["identity"]["banks_only"]

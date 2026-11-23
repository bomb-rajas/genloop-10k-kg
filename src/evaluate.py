"""Benchmark evaluation: python -m src.evaluate. Scores query.answer() on benchmark/benchmark.json; writes results/metrics.json and results/per_question.csv.

Scoring rules (D-079, amended by D-080): numeric gold_value matches if |pred - gold| <= 0.5% of |gold|; pred in USD may be
quoted in thousands/millions/billions (x1e3..1e9); '%' answers are divided by 100 to compare with fraction gold. The number
also matches the value of any returned fact node, or any number in the answer text (D-080).
Text terms (non-fact entries of gold_fact_ids, e.g. 'PepsiCo', 'Americas') match on normalised text of the answer
or on the graph name of a returned company. Items with neither a numeric nor a term gold are 'unscored': no
correct, precision, recall, doc_hit or page_hit, and excluded from every mean (still listed in per_question).
Fact precision/recall use gold fact ids that match 'TICKER|Metric|FYyyyy'; abstain-expected items use an empty gold set
(P=1, R=1 when nothing is returned, P=0 when something is). Otherwise P/R are None and left out of the means.
page_hit_strict is reported separately from accuracy: the cited page must be a gold page or in acceptable_pages (D-081).
wrong_page rows count as correct for accuracy.
"""
import csv
import json
import math
import re
from pathlib import Path

from src import graph as g
from src import query
from src.config import BENCHMARK_DIR, RESULTS_DIR

TOL = 0.005
SCALES = (1, 1e3, 1e6, 1e9)
SUFFIXES = {"inc", "corp", "corporation", "co", "plc", "ltd", "llp", "company"}
QUERY_REASONS = {"no_fact", "unsupported_period"}  # abstain reasons raised by query.py (others come from planner.py)
TYPES = ("single_fact", "multi_hop", "cross_filing")


def norm(s):
    toks = re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split()
    return " ".join(t for t in toks if t not in SUFFIXES)


def numeric_ok(pred, unit, gold):
    if gold is None or pred is None or isinstance(pred, (dict, list, str)):
        return False
    if unit == "%":
        pred = pred / 100
    scales = SCALES if unit == "USD" else (1,)
    return any(abs(pred * s - gold) * 200 <= abs(gold) for s in scales)  # |diff| <= 0.5% of |gold|


def text_has_number(text, gold):
    """True if any number in the answer text matches gold (x% for '%' answers, USD scales otherwise)."""
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?(%?)", str(text)):
        if re.fullmatch(r"(?:19|20)\d\d", m.group(0)):  # a bare year (FY2025) is not a value (D-083)
            continue
        if numeric_ok(float(m.group(0).rstrip("%").replace(",", "")), "%" if m.group(1) else "USD", gold):
            return True
    return False


def is_fact_id(s):
    return "|" in s


def predicted_tickers(G, res):
    t = {f.split("|")[0] for f in res.get("fact_ids", []) if f in G.nodes and is_fact_id(f)}
    if isinstance(res.get("value"), dict):
        t |= set(res["value"])
    return t


def company_names(G):
    return {norm(d.get("name", "")): n for n, d in G.nodes(data=True) if d.get("node_type") == "Company"}


def score(item, res, G):
    """Score one benchmark item against one query.answer() result. Returns a row dict."""
    expect_abstain = item["expected_behaviour"] == "abstain"
    abstained = bool(res.get("abstained"))
    gold_facts = [] if expect_abstain else [f for f in item["gold_fact_ids"] if is_fact_id(f)]
    terms = [] if expect_abstain else [t for t in item["gold_fact_ids"] if not is_fact_id(t)]
    gold_value = None if expect_abstain else item.get("gold_value")
    pred_ids = res.get("fact_ids", []) or []
    pred_text = res.get("answer", "")

    # answer correctness
    if expect_abstain:
        correct = abstained
    elif gold_value is None and not terms:
        correct = None
    else:
        pred_names = {norm(G.nodes[t].get("name", "")) for t in predicted_tickers(G, res) if t in G.nodes}
        text_n = " " + norm(pred_text) + " "
        if res.get("winner") in G.nodes:  # which-is-higher style: only the winning entity counts (D-083)
            pred_names = {norm(G.nodes[res["winner"]].get("name", ""))}
            text_n = " " + norm(pred_text.split(" | ")[0]) + " "
        term_ok = all((" " + norm(t) + " ") in text_n or norm(t) in pred_names for t in terms)
        # structured value may be a dict/str (e.g. HQ city); also accept returned fact values and numbers in the text
        # fallbacks only when the structured value is not a number: a numeric answer is judged on its own (no credit for a fact node)
        sv = res.get("value")
        numeric_sv = isinstance(sv, (int, float)) and not isinstance(sv, bool)
        fact_vals = [] if numeric_sv else [G.nodes[f].get("value") for f in pred_ids if f in G.nodes and is_fact_id(f)]
        num_ok = gold_value is None or numeric_ok(sv, res.get("unit"), gold_value) \
            or (not numeric_sv and (any(numeric_ok(v, None, gold_value) for v in fact_vals)
                                    or text_has_number(pred_text, gold_value)))
        correct = (not abstained) and term_ok and num_ok
    # company check: gold tickers from fact ids plus tickers whose name equals a gold term
    gold_tickers = {f.split("|")[0] for f in gold_facts}
    names = company_names(G)
    for t in terms:
        if norm(t) in names:
            gold_tickers.add(names[norm(t)])
    wrong_company = bool(gold_tickers - predicted_tickers(G, res)) if not expect_abstain else False

    # fact precision / recall
    gold_set = set(gold_facts)
    if expect_abstain:
        prec, rec = (1.0 if not pred_ids else 0.0), 1.0
    elif gold_set and correct is not None:
        inter = len(gold_set & set(pred_ids))
        prec = inter / len(pred_ids) if pred_ids else 0.0
        rec = inter / len(gold_set)
    else:
        prec = rec = None

    # citation check: doc ticker in gold docs and page in gold pages, or (doc, page) in acceptable_pages (D-081)
    gold_docs = {Path(d).stem for d in item.get("docs", [])}
    gold_pages = set(item.get("pages", []))
    ok_pages = {(Path(a["doc"]).stem, a["page"]) for a in item.get("acceptable_pages", [])}
    cites = res.get("citations", []) or []
    scorable = correct is not None and not expect_abstain
    doc_hit = any(Path(str(c.get("doc"))).stem in gold_docs for c in cites) if cites and scorable else None
    page_strict = any((c.get("page") in gold_pages and Path(str(c.get("doc"))).stem in gold_docs)
                      or (Path(str(c.get("doc"))).stem, c.get("page")) in ok_pages for c in cites) \
        if cites and scorable else None

    missing = [f for f in gold_facts if f not in G.nodes]
    if expect_abstain:
        cat = "abstained_unanswerable" if abstained else "answered_unanswerable"
    elif correct is None:
        cat = "unscored"
    elif abstained:
        if missing:
            cat = "missing_fact_in_graph"
        elif res.get("reason") in QUERY_REASONS:
            cat = "abstained_wrongly"
        else:
            cat = "planner_failed"
    elif correct:
        cat = None if page_strict in (True, None) else "wrong_page"
    elif missing:
        cat = "missing_fact_in_graph"
    elif wrong_company:
        cat = "wrong_company"
    else:
        cat = "wrong_value"

    return dict(id=item["id"], type=item["type"], question=item["question"], gold=item["gold_answer"],
                predicted=pred_text, correct=correct, precision=prec, recall=rec, doc_hit=doc_hit,
                page_hit_strict=page_strict, abstained=abstained, expected_abstain=expect_abstain,
                failure_category=cat, reason=res.get("reason"))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def aggregate(rows):
    scored = [r for r in rows if r["correct"] is not None]  # unscored rows are excluded from every mean
    ans = [r for r in scored if not r["expected_abstain"] and not r["abstained"]]
    return dict(
        n=len(rows), scored=len(scored), correct=sum(bool(r["correct"]) for r in scored),
        accuracy=_mean([float(bool(r["correct"])) for r in scored]),
        accuracy_over_all=round(sum(bool(r["correct"]) for r in scored) / len(rows), 4) if rows else None,  # task rule: correct / total
        precision=_mean([r["precision"] for r in scored]), recall=_mean([r["recall"] for r in scored]),
        precision_excl_abstain=_mean([r["precision"] for r in scored if not r["expected_abstain"]]),
        recall_excl_abstain=_mean([r["recall"] for r in scored if not r["expected_abstain"]]),
        doc_hit_rate=_mean([None if r["doc_hit"] is None else float(r["doc_hit"]) for r in ans]),
        page_strict_rate=_mean([None if r["page_hit_strict"] is None else float(r["page_hit_strict"]) for r in ans]),
        abstained=sum(r["abstained"] for r in rows),
        abstain_expected=sum(r["expected_abstain"] for r in rows),
        abstain_correct=sum(r["expected_abstain"] and r["abstained"] for r in rows),
        unscored=len(rows) - len(scored),
    )


NOTES = {
    "accuracy_over_all": "correct / n (all questions, unscored count as not correct); the task-defined accuracy. 'accuracy' is correct / scored.",
    "precision_excl_abstain": "precision and recall means over scored rows that are not abstain-expected (abstain-expected rows score P=R=1 when refused, which lifts the plain means).",
    "accuracy": "correct is value/term based. wrong_page rows count as correct for accuracy.",
    "wrong_page": "value correct but the cited page is not in gold pages. Reported in failure_category only; not an accuracy miss.",
    "page_strict_rate": "strict page check: cited page must be a gold page or in acceptable_pages (other pages of the "
                        "same filing that carry the value, D-081). Not used for accuracy.",
    "doc_hit_rate": "cited doc is a gold doc (answered rows only).",
    "unscored": "rows with no checkable gold (no number, no term) have no correct, precision, recall or citation "
                "score and are excluded from all means. They stay listed in per_question.csv with failure_category unscored.",
}


def run(items, G, lex=None):
    rows = []
    for it in items:
        try:
            res = query.answer(it["question"], G=G, lex=lex)
        except Exception as exc:  # never let one question stop the run
            res = dict(abstained=True, reason="plan_failed", answer=f"error: {exc}", fact_ids=[], citations=[])
        rows.append(score(it, res, G))
    return rows


def build_report(rows):
    return dict(notes=NOTES, overall=aggregate(rows),
                per_type={t: aggregate([r for r in rows if r["type"] == t]) for t in TYPES}, per_question=rows)


def table(report):
    cols = ("n", "scored", "correct", "accuracy", "accuracy_over_all", "precision", "recall", "precision_excl_abstain",
            "recall_excl_abstain", "doc_hit_rate", "page_strict_rate", "abstained", "unscored")
    lines = [f"{'group':<14}" + "".join(f"{c[:22]:>23}" for c in cols)]
    for name, agg in [("overall", report["overall"]), *report["per_type"].items()]:
        lines.append(f"{name:<14}" + "".join(f"{str(agg[c]):>23}" for c in cols))
    lines.append("")
    lines.append(f"{'id':<5}{'type':<12}{'ok':<6}{'P':>6}{'R':>6}{'doc':>6}{'pg_strict':>10}  failure_category")
    for r in report["per_question"]:
        f = lambda x: "-" if x is None else f"{x:.2f}"
        ok = "-" if r["correct"] is None else ("yes" if r["correct"] else "no")
        d = lambda x: "-" if x is None else ("yes" if x else "no")
        lines.append(f"{r['id']:<5}{r['type']:<12}{ok:<6}{f(r['precision']):>6}{f(r['recall']):>6}"
                     f"{d(r['doc_hit']):>6}{d(r['page_hit_strict']):>10}  {r['failure_category'] or ''}")
    lines.append("")
    lines += [f"note {k}: {v}" for k, v in report["notes"].items()]
    return "\n".join(lines)


def write(report, out_dir=RESULTS_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    rows = report["per_question"]
    with open(out_dir / "per_question.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="benchmark.json", help="file in benchmark/ (e.g. heldout.json)")
    ap.add_argument("--out", default=None, help="output dir (default results/)")
    a = ap.parse_args()
    G = g.load_graph()
    items = json.loads((BENCHMARK_DIR / a.bench).read_text(encoding="utf-8"))["items"]
    report = build_report(run(items, G))
    write(report, Path(a.out)) if a.out else write(report)
    print(table(report))


if __name__ == "__main__":
    main()

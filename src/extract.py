"""M4 fact extraction: map parsed statement rows (data/parsed/{T}.json) to canonical metrics (config/metrics.yaml).

PDF-only (D-005, D-016): values come from data/parsed only. XBRL is used by src.validate as a gate.
Run: python -m src.extract [--tickers AAPL,JPM] [--verbose]
Output: data/facts/{T}.json (admitted), data/facts/{T}.rejected.json (XBRL mismatches).
"""
import argparse
import json
import re
from collections import Counter

from src import config
from src.validate import gate

STATEMENT_YEARS = {"income_statement": 3, "cash_flow_statement": 3, "balance_sheet": 2}  # D-054
GENERIC_EXCLUDE = ["margin", "growth", "change", "percent", "ratio", "before", "and"]  # D-055


def norm(s):
    """Lowercase, footnote markers (1) (a) removed, punctuation to spaces: 'Shareholders’ equity' -> 'shareholders equity'."""
    s = str(s).replace("’", "'").lower()
    s = re.sub(r"\([^)]*\)", " ", s)  # footnotes and parentheticals: (1), (a), (Notes 1 and 2), (loss)
    return re.sub(r"[^a-z0-9]+", " ", s.replace("'", "")).strip()


def _rem_ok(rem, excl):
    padded = f" {rem} "
    return not any(f" {tok} " in padded for tok in excl)


def match_row(cand, spec):
    """cand: [(row_index, normalised_label)] in statement order. Returns (row_index, tier) or None.
    Tiers: exact synonym (priority order) -> label_regex -> prefix of a multi-word synonym (the rest of the
    label must not contain an exclude word) -> fallback_labels exact -> fallback_labels prefix."""
    syns = [norm(s) for s in spec.get("synonyms", [])]
    fbs = [norm(s) for s in spec.get("fallback_labels", [])]
    spec_excl = [norm(e) for e in spec.get("exclude", [])]
    excl = GENERIC_EXCLUDE + spec_excl
    rx = [re.compile(p) for p in spec.get("label_regex", [])]

    def exact(labels):
        for s in labels:
            for i, label in cand:
                if label == s:
                    return i, "exact"

    def regex():
        for p in rx:
            for i, label in cand:
                if p.search(label) and _rem_ok(label, spec_excl):
                    return i, "regex"

    def prefix(labels):
        for s in labels:
            if " " not in s:
                continue
            for i, label in cand:
                if label.startswith(s + " ") and _rem_ok(label[len(s):], excl):
                    return i, "prefix"

    return exact(syns) or regex() or prefix(syns) or exact(fbs) or prefix(fbs)


def find_metric_row(stmt, spec):
    """Row (dict) for one metric in one statement, or None. Only full-width rows are candidates."""
    ncols = len(stmt["columns"])
    cand = [(i, norm(r["label"])) for i, r in enumerate(stmt["rows"])
            if r["label"] and len(r["values"]) == ncols]
    pref = [norm(w) for w in spec.get("prefer_exclude", [])]  # e.g. EPS: net-income row over continuing-ops row
    hit = None
    if pref:
        hit = match_row([c for c in cand if _rem_ok(c[1], pref)], spec)
    hit = hit or match_row(cand, spec)
    if hit is None:
        return None, None
    return stmt["rows"][hit[0]], hit[1]


def fmt(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def applies(metric, is_bank):
    return metric["applies_to"] == "all" or (metric["applies_to"] == "nonbank" and not is_bank)


def extract_company(company, filing, metrics, helpers):
    """Candidate facts for one company (before the XBRL gate). Returns (facts, missing)."""
    t = company["ticker"]
    parsed = json.loads((config.PARSED_DIR / f"{t}.json").read_text(encoding="utf-8"))
    stmts = parsed["statements"]
    newest = int(filing["report_date"][:4])
    for st in stmts.values():
        if not st.get("columns"):
            st["columns"], st["rows"] = infer_header(st["rows"])
        normalise_layout(st, newest)

    def shift_of(stmt):
        """Header years can be fiscal labels (HD IS '2025' = period ending Feb 2026). Align the statement's newest
        column with the report year so FY = period-end year for every statement (D-058)."""
        cols = [c for c in stmt["columns"] if c <= newest]
        return newest - max(cols) if cols else 0
    facts, missing = [], {}
    rows_by_metric = {}

    def years_of(stmt_name, stmt):
        """Header years whose period-end label falls in the window (report year - N, report year]."""
        n, sh = STATEMENT_YEARS[stmt_name], shift_of(stmt)
        return sorted({y for y in stmt["columns"] if newest - n < y + sh <= newest}, reverse=True)

    def col_index(stmt, year):
        return stmt["columns"].index(year)

    # Direct rows.
    for m in metrics:
        if not applies(m, company["is_bank"]):
            continue
        stmt = stmts.get(m["statement"])
        if stmt is None:
            missing[m["name"]] = f"no {m['statement']} in parsed data"
            continue
        if stmt.get("scale") is None and m["unit"] == "USD":
            missing[m["name"]] = "statement has no scale"
            continue
        row, tier = find_metric_row(stmt, m)
        if row is None:
            missing[m["name"]] = "no matching row"
            continue
        rows_by_metric[m["name"]] = (row, tier, stmt)

    # Identity fallbacks (method 'identity'): value = sum(plus) - sum(minus), same statement and year.
    for m in metrics:
        if m["name"] in rows_by_metric or "identity" not in m or not applies(m, company["is_bank"]) \
                or (m["identity"].get("banks_only") and not company["is_bank"]):
            continue
        ident = m["identity"]
        parts = []
        for name in ident.get("plus", []) + ident.get("minus", []):
            spec = helpers.get(name) or next(x for x in metrics if x["name"] == name)
            stmt = stmts.get(spec["statement"])
            hit = find_metric_row(stmt, spec) if stmt else (None, None)
            parts.append((name, hit, ident.get("minus", [])))
        stmt = stmts.get(m["statement"])
        scale_ok = stmt is not None and (m["unit"] != "USD" or stmt.get("scale") is not None)
        if scale_ok and parts and all(h[0] for _, h, _ in parts):
            rows_by_metric[m["name"]] = ("identity", parts, stmt)
            missing.pop(m["name"], None)
        else:
            missing.setdefault(m["name"], "no direct row; identity inputs missing")

    for name, payload in rows_by_metric.items():
        m = next(x for x in metrics if x["name"] == name)
        if payload[0] == "identity":
            parts = payload[1]
            plus_rows = [h[0] for n, h, _ in parts if n in m["identity"].get("plus", [])]
            minus_rows = [h[0] for n, h, _ in parts if n in m["identity"].get("minus", [])]
            stmt = stmts[m["statement"]]
            years = years_of(m["statement"], stmt)
            for y in years:
                idx = col_index(stmt, y)
                val = sum(r["values"][idx] for r in plus_rows) - sum(r["values"][idx] for r in minus_rows)
                if m["unit"] == "USD":
                    val = int(round(val * stmt["scale"]))
                if m.get("absolute"):
                    val = abs(val)
                label = " + ".join(r["label"] for r in plus_rows) + "".join(f" - {r['label']}" for r in minus_rows)
                facts.append(_fact(t, filing, m, y + shift_of(stmt), val, label, plus_rows[0]["page"],
                                   " | ".join(f"{r['label']} {fmt(r['values'][idx])}" for r in plus_rows + minus_rows),
                                   "identity", stmt["scale"], newest))
            continue
        row, tier, stmt = payload
        for y in years_of(m["statement"], stmt):
            idx = col_index(stmt, y)
            raw = row["values"][idx]
            val = raw * stmt["scale"] if m["unit"] == "USD" else raw
            if m.get("absolute"):  # outflows reported negative (CapEx): D-057
                val = abs(val)
            if m["unit"] == "USD":
                val = int(round(val))
            f = _fact(t, filing, m, y + shift_of(stmt), val, row["label"], row["page"],
                      f"{row['label']} " + " ".join(fmt(v) for v in row["values"]),
                      "pdf_table", stmt["scale"] if m["unit"] == "USD" else 1, newest)
            if m.get("basic_xbrl_tags") and "basic" in norm(row["label"]).split():
                f["xbrl_tags"] = m["basic_xbrl_tags"]  # basic EPS row: validate against the basic concept only
            facts.append(f)
    return facts, missing


def normalise_layout(st, newest):
    """Parser layout gaps: (1) a header year after the report year (MRK '2026' in a 2025 filing) is dropped when rows
    omit it; (2) rows that interleave a '% of revenue' column (value, pct, value, pct, ...) keep the value column."""
    cols = st["columns"]
    keep = [c for c in cols if c <= newest]
    if keep and len(keep) < len(cols) and any(len(r["values"]) == len(keep) for r in st["rows"]):
        st["columns"] = cols = keep
    n = len(cols)
    if not n:
        return
    for r in st["rows"]:
        v = r["values"]
        if len(v) == 2 * n and not re.search(r"per |share", norm(r["label"])) and all(abs(x) <= 100 for x in v[1::2]):
            r["values"] = v[0::2]


def infer_header(rows):
    """Parser gap fallback (PG): when a statement has no column header, the header row is the first row whose
    trailing values are years (e.g. 'fiscal years ended June 30 2026 2025 2024'). Returns (years, rows without it)."""
    for r in rows:
        run = []
        for x in reversed(r["values"]):
            if float(x).is_integer() and 1990 <= x <= 2100:
                run.insert(0, int(x))
            else:
                break
        if len(run) >= 2:
            return run, [q for q in rows if q is not r]
    return [], rows


def _fact(t, filing, m, year, value, label, page, snippet, method, scale, newest):
    return {
        "id": f"{t}|{m['name']}|FY{year}",
        "ticker": t,
        "metric": m["name"],
        "value": value,
        "unit": m["unit"],
        "scale": scale,
        "as_reported_label": label,
        "period": {"fiscal_year": year,
                   "period_end": filing["report_date"] if year == newest else None},
        "doc": f"data/pdfs/{t}.pdf",
        "page": page,
        "snippet": snippet,
        "method": method,
        "validated": False,
        "xbrl_status": None,
        "xbrl_tag": None,
        "xbrl_value": None,
        "xbrl_tags": None,  # gate-only override, removed by validate.gate_fact
    }


def run(tickers=None, verbose=False):
    companies = config.load_companies()
    if tickers:
        companies = [c for c in companies if c["ticker"] in tickers]
    cfg = config.load_metrics()
    metrics = cfg["metrics"]
    helpers = {h["name"]: h for h in cfg.get("helper_metrics", [])}
    by_name = {m["name"]: m for m in metrics}
    filings = json.loads((config.DATA_DIR / "filings.json").read_text(encoding="utf-8"))
    config.FACTS_DIR.mkdir(parents=True, exist_ok=True)

    tot = Counter()
    per_metric = {}
    summary = {}
    for c in companies:
        t = c["ticker"]
        filing = filings[t]
        cands, missing = extract_company(c, filing, metrics, helpers)
        xbrl = json.loads((config.XBRL_DIR / f"{t}.json").read_text(encoding="utf-8"))
        admitted, rejected, stats = gate(cands, xbrl, filing, by_name)
        admitted.sort(key=lambda f: (f["metric"], -f["period"]["fiscal_year"]))
        (config.FACTS_DIR / f"{t}.json").write_text(json.dumps(admitted, indent=1), encoding="utf-8")
        (config.FACTS_DIR / f"{t}.rejected.json").write_text(json.dumps(rejected, indent=1), encoding="utf-8")
        tot.update(stats)
        for f in cands:
            pm = per_metric.setdefault(f["metric"], Counter())
            pm[f["xbrl_status"]] += 1
        admitted_metrics = {f["metric"] for f in admitted}
        applicable = [m["name"] for m in metrics if applies(m, c["is_bank"])]
        miss = {k: v for k, v in missing.items() if k in applicable and k not in admitted_metrics}
        for k in applicable:
            if k not in admitted_metrics and k not in miss:
                miss[k] = "all facts rejected by gate"
        summary[t] = miss
        print(f"{t}: candidates {stats['candidates']} admitted {len(admitted)} rejected {len(rejected)} "
              f"no_xbrl {stats['no_xbrl']} missing {len(miss)}")
        if verbose:
            for f in admitted:
                print(f"  {f['id']:<32} {f['value']!s:>18} p{f['page']} {f['xbrl_status']} {f['method']}")
            for f in rejected:
                print(f"  REJECTED {f['id']} {f['reason']} p{f['page']}")

    compared = tot["matched"] + tot["mismatch"]
    print(f"\nXBRL match rate: {tot['matched']}/{compared} = {100 * tot['matched'] / max(compared, 1):.1f}% "
          f"(rejected {tot['rejected']}, no_xbrl {tot['no_xbrl']}, candidates {tot['candidates']})")
    print("Per metric (matched/compared, rejected, no_xbrl):")
    for name, pm in per_metric.items():
        cmp_ = pm["match"] + pm["mismatch"]
        print(f"  {name:<18} {pm['match']}/{cmp_} rejected {pm['mismatch']} no_xbrl {pm['no_xbrl']}")
    print(f"Identity check (TA = TL + Eq): checked {tot['identity_checked']}, failed {tot['identity_failed']} (logged only)")
    print(f"Sanity failures (rejected): {tot['sanity_failed']}")
    print("Missing metrics per company:")
    for t, miss in summary.items():
        if miss:
            print(f"  {t}: " + "; ".join(f"{k} ({v})" for k, v in miss.items()))
    return summary


def main():
    ap = argparse.ArgumentParser(description="Extract canonical facts from data/parsed and gate them with XBRL.")
    ap.add_argument("--tickers", help="comma-separated tickers, e.g. AAPL,JPM")
    ap.add_argument("--verbose", action="store_true", help="print every admitted fact")
    args = ap.parse_args()
    tickers = set(args.tickers.split(",")) if args.tickers else None
    run(tickers, args.verbose)


if __name__ == "__main__":
    main()

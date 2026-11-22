"""XBRL validation gate for extracted facts (D-016: validation only, never a value source).

A fact is compared with the us-gaap value for the same period in data/xbrl/{T}.json.
match -> validated; mismatch -> rejected (not admitted); no XBRL value -> admitted, validated False.
"""
from datetime import date

TOLERANCE = 0.005          # relative to the XBRL value (USD facts)
EPS_ABS_TOLERANCE = 0.005  # absolute, USD/share facts
DATE_WINDOW_DAYS = 7       # XBRL period end vs. anchor date (52/53-week years drift by a few days)
FLOW_DAYS = (350, 380)     # duration of a fiscal-year flow entry
IDENTITY_TOLERANCE = 0.005
MAX_ABS_USD = 1e13         # sanity: no 10-K value this large in USD
MAX_ABS_EPS = 1000.0       # sanity: per-share values
XBRL_UNIT = {"USD": "USD", "USD/share": "USD/shares"}


def anchor_date(report_date, year):
    """Same month and day as the filing's period end, in `year` (Feb 29 -> Feb 28)."""
    d = date.fromisoformat(report_date)
    try:
        return d.replace(year=year)
    except ValueError:
        return d.replace(year=year, day=28)


def xbrl_entries(xbrl, tags, unit, is_flow, anchor, accession):
    """10-K FY entries for the period. Returns the entries of the filing's own accession when it has
    any, otherwise entries from all 10-K filings (latest first)."""
    found = []
    gaap = (xbrl or {}).get("facts", {}).get("us-gaap", {})
    for tag in tags:
        for e in gaap.get(tag, {}).get("units", {}).get(unit, []):
            if e.get("form") != "10-K" or e.get("fp") != "FY" or "end" not in e:
                continue
            end = date.fromisoformat(e["end"])
            if abs((end - anchor).days) > DATE_WINDOW_DAYS:
                continue
            if is_flow:
                if "start" not in e:
                    continue
                days = (end - date.fromisoformat(e["start"])).days
                if not FLOW_DAYS[0] <= days <= FLOW_DAYS[1]:
                    continue
            found.append({"tag": tag, "val": float(e["val"]), "end": e["end"],
                          "accn": e.get("accn"), "filed": e.get("filed", "")})
    own = [e for e in found if e["accn"] == accession]
    if own:
        return own
    return sorted(found, key=lambda e: e["filed"], reverse=True)


def within(value, xval, unit):
    if unit == "USD/share":
        return abs(value - xval) <= EPS_ABS_TOLERANCE
    return abs(value - xval) <= TOLERANCE * abs(xval)


def gate_fact(fact, xbrl, metric, accession, report_date):
    """Sets validated, xbrl_status, xbrl_value and period_end on `fact`. Returns the fact."""
    unit = XBRL_UNIT[fact["unit"]]
    year = fact["period"]["fiscal_year"]
    anchor = anchor_date(report_date, year)
    entries = xbrl_entries(xbrl, metric["xbrl_tags"], unit, metric["category"] != "balance", anchor, accession)
    fact["validated"] = False
    if not entries:
        fact["xbrl_status"], fact["xbrl_value"] = "no_xbrl", None
        return fact
    hit = next((e for e in entries if within(fact["value"], e["val"], fact["unit"])), None)
    shown = hit or entries[0]
    fact["xbrl_value"] = shown["val"]
    fact["period"]["period_end"] = shown["end"]
    fact["xbrl_status"] = "match" if hit else "mismatch"
    fact["validated"] = hit is not None
    return fact


def identity_check(facts):
    """Accounting identity TotalAssets == TotalLiabilities + Equity per year, logged only.
    Identity-derived TotalLiabilities is circular, so it is not checked."""
    by_year = {}
    for f in facts:
        if f["metric"] in ("TotalAssets", "TotalLiabilities", "Equity"):
            by_year.setdefault(f["period"]["fiscal_year"], {})[f["metric"]] = f
    checked = failed = 0
    for year, m in by_year.items():
        ta, tl, eq = m.get("TotalAssets"), m.get("TotalLiabilities"), m.get("Equity")
        if not (ta and tl and eq) or tl["method"] == "identity":
            continue
        ok = abs(ta["value"] - (tl["value"] + eq["value"])) <= IDENTITY_TOLERANCE * abs(ta["value"])
        for f in (ta, tl, eq):
            f["identity_ok"] = ok
        checked += 1
        failed += not ok
    return checked, failed


def sanity_ok(fact):
    v = fact["value"]
    if fact["unit"] == "USD/share":
        return abs(v) < MAX_ABS_EPS
    if fact["metric"] in ("Revenue", "TotalAssets") and v <= 0:
        return False
    return abs(v) < MAX_ABS_USD


def gate(facts, xbrl, filing, metrics_by_name):
    """Runs the gate on candidate facts. Returns (admitted, rejected, stats)."""
    accession, report_date = filing["accession"], filing["report_date"]
    for f in facts:
        gate_fact(f, xbrl, metrics_by_name[f["metric"]], accession, report_date)
        f["sanity_ok"] = sanity_ok(f)
    checked, id_failed = identity_check(facts)
    admitted = [f for f in facts if f["xbrl_status"] != "mismatch"]
    rejected = []
    for f in facts:
        if f["xbrl_status"] == "mismatch":
            rejected.append({**f, "reason": f"xbrl_mismatch: pdf {f['value']} vs xbrl {f['xbrl_value']}"})
    stats = {
        "candidates": len(facts),
        "matched": sum(f["xbrl_status"] == "match" for f in facts),
        "mismatch": sum(f["xbrl_status"] == "mismatch" for f in facts),
        "no_xbrl": sum(f["xbrl_status"] == "no_xbrl" for f in facts),
        "identity_checked": checked, "identity_failed": id_failed,
        "sanity_failed": sum(not f["sanity_ok"] for f in facts),
    }
    return admitted, rejected, stats

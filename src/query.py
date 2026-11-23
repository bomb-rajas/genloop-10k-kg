"""Answer questions by traversing graph/kg.json only (D-075). XBRL and vector search are never used.

    python -m src.query "What was Apple's revenue in fiscal 2025?" [--json]
Planning lives in src/planner.py. Anything unsupported abstains with a reason instead of guessing.
"""
import argparse
import json
import re

from src import graph as g
from src import planner

DERIVED_EXTRA = {"OperatingMargin": ["OperatingIncome", "Revenue"]}  # not a graph Metric node; same 'A / B' shape


class Abstain(Exception):
    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason, self.detail = reason, detail


def spec_of(G, plan, metric=None):
    """(inputs, kind): kind 'plain' (1 input), 'pct' (A/B*100, derived) or 'x' (A/B, op=ratio)."""
    m = metric or plan["metric"]
    if plan.get("op") == "ratio" and not metric:
        return list(plan["metrics"]), "x"
    if plan.get("op") == "share" and not metric:
        return list(plan["metrics"]), "pct"  # metrics[0] / metrics[1] * 100 (D-086)
    f = DERIVED_EXTRA.get(m) or (G.nodes[g.metric_id(m)].get("formula") if G.has_node(g.metric_id(m)) else None)
    if isinstance(f, str) and "/" in f and m not in ("Revenue",):
        a, b = [s.strip() for s in f.split("/")]
        return [a, b], "pct"
    if isinstance(f, list):
        return f, "pct"
    return [m], "plain"


def fact_for(G, t, metric, fy):
    fs = g.facts_of(G, t, metric, fy)
    return max(fs, key=lambda f: G.nodes[f].get("validated") is True, default=None)


def fys(G, t, inputs):
    return set.intersection(*[{G.nodes[f]["fiscal_year"] for f in g.facts_of(G, t, m)} for m in inputs])


def measure(G, t, inputs, kind, fy):
    """Value of one company-year from graph facts: (value, unit, [fact ids]); raises Abstain when an input is missing."""
    ids = []
    for m in inputs:
        f = fact_for(G, t, m, fy)
        if f is None:
            any_fy = any(G.nodes[x]["fiscal_year"] == fy for x in g.neighbors(G, t, "HAS_FACT"))
            raise Abstain("no_fact" if any_fy else "unsupported_period",
                          f"{t} has no {m} fact for FY{fy}" + ("" if any_fy else f" (no FY{fy} filing in the graph)"))
        ids.append(f)
    v = [G.nodes[f]["value"] for f in ids]
    if kind == "plain":
        return v[0], G.nodes[ids[0]]["unit"], ids
    if not v[1]:
        raise Abstain("no_fact", f"{t} {inputs[1]} is zero for FY{fy}")
    return (100 * v[0] / v[1], "%", ids) if kind == "pct" else (v[0] / v[1], "x", ids)


def resolve_fy(G, t, inputs, want, back=0):
    """Fiscal year to use for t: the asked one, else its newest where inputs (and fy-back) exist."""
    have = fys(G, t, inputs)
    if want is not None:
        if want not in have:
            any_fy = any(G.nodes[x]["fiscal_year"] == want for x in g.neighbors(G, t, "HAS_FACT"))
            raise Abstain("no_fact" if any_fy else "unsupported_period",
                          f"{t} has no {'/'.join(inputs)} for FY{want}" + ("" if any_fy else " (year not in graph)"))
        return want
    ok = [y for y in have if back == 0 or y - back in have]
    if not ok:
        raise Abstain("no_fact", f"{t} has no {'/'.join(inputs)} fact" + (" with a prior year" if back else ""))
    return max(ok)


def company_value(G, t, plan, inputs, kind, fy):
    """One value per company honoring growth; returns dict(value, unit, ids, fy, label)."""
    if plan.get("growth"):
        yrs = plan.get("years") or []
        if len(yrs) >= 2:
            y0, y1 = min(yrs), max(yrs)
        else:
            y1 = resolve_fy(G, t, inputs, yrs[0] if yrs else None, back=1)
            y0 = y1 - 1
        (v1, u, i1), (v0, _, i0) = measure(G, t, inputs, kind, y1), measure(G, t, inputs, kind, y0)
        if plan["growth"] == "pct":
            if not v0:
                raise Abstain("no_fact", f"{t} FY{y0} base value is zero")
            return dict(value=100 * (v1 - v0) / abs(v0), unit="%", ids=i0 + i1, fy=f"{y0}->{y1}")
        return dict(value=v1 - v0, unit="pp" if u == "%" else u, ids=i0 + i1, fy=f"{y0}->{y1}")
    y = resolve_fy(G, t, inputs, fy)
    v, u, ids = measure(G, t, inputs, kind, y)
    return dict(value=v, unit=u, ids=ids, fy=y)


def fmt(v, unit):
    if unit == "USD":
        a = abs(v)
        return f"${v / 1e9:,.2f} billion" if a >= 1e9 else f"${v / 1e6:,.2f} million" if a >= 1e6 else f"${v:,.0f}"
    return {"USD/share": f"${v:,.2f} per share", "%": f"{v:,.2f}%", "pp": f"{v:+,.2f} percentage points",
            "x": f"{v:,.3f}x", "count": f"{v:,.0f}"}.get(unit, f"{v:,.4g} {unit}")


def cite(G, node):
    d = G.nodes[node]
    return dict(doc=d.get("doc"), page=d.get("page"), fact_id=node, snippet=d.get("snippet"))


def scope(G, plan):
    cos, sec = plan["companies"], plan.get("sector")
    if cos:
        return cos, True
    ts = g.sector_members(G, sec) if sec else [t for t, d in G.nodes(data=True) if d["node_type"] == "Company"]
    if not ts:
        raise Abstain("no_fact", f"no companies found for sector {sec}")
    return sorted(ts), False


def gather(G, plan, inputs, kind, ts, strict):
    """Per-company values; strict (named set) abstains on any gap, open sets record the missing ones."""
    fy = (plan.get("years") or [None])[0]
    out, missing = {}, {}
    for t in ts:
        try:
            out[t] = company_value(G, t, plan, inputs, kind, fy)
        except Abstain as e:
            if strict:
                raise
            missing[t] = e.reason
    if not out:
        raise Abstain("no_fact", f"no company has {'/'.join(inputs)} for {'FY' + str(fy) if fy else 'any year'}")
    return out, missing


def difference_answer(G, plan):
    """A - B (reported as the magnitude, with who is larger): two metrics of one company/year, or one metric of two companies."""
    ms, cos = plan["metrics"], plan["companies"]
    if len(cos) == 1 and len(ms) == 2:
        t = cos[0]
        specs = [spec_of(G, plan, m) for m in ms]
        fy = resolve_fy(G, t, sorted({x for inp, _ in specs for x in inp}), (plan.get("years") or [None])[0])
        rows = {f"{t} {m}": dict(zip(("value", "unit", "ids"), measure(G, t, inp, k, fy)), fy=fy)
                for m, (inp, k) in zip(ms, specs)}
    elif len(cos) == 2 and len(ms) == 1:
        inp, k = spec_of(G, plan, ms[0])
        rows, _ = gather(G, {**plan, "growth": None}, inp, k, cos, True)
        rows = {f"{t} {ms[0]}": r for t, r in rows.items()}
    else:
        raise Abstain("unsupported", "difference needs two companies with one metric or one company with two metrics")
    (a, ra), (b, rb) = list(rows.items())[:2]
    if ra["unit"] != rb["unit"]:
        raise Abstain("unsupported", f"cannot subtract {ra['unit']} from {rb['unit']}")
    d = ra["value"] - rb["value"]
    verb = "exceeds" if d > 0 else "is below" if d < 0 else "equals"
    return dict(rows=rows, unit=ra["unit"], missing={}, value=abs(d), signed=d, fmt_value=True,
                lead=f"{a} {verb} {b} by (A - B = {fmt(d, ra['unit'])})")


def numeric_answer(G, plan):
    if plan["intent"] == "difference":
        return difference_answer(G, plan)
    inputs, kind = spec_of(G, plan)
    i, op = plan["intent"], plan.get("op")
    if i == "aggregate" and len(plan.get("years") or []) >= 2 and len(plan["companies"]) == 1:
        t = plan["companies"][0]  # cross-filing: one company across years
        rows = {y: company_value(G, t, {**plan, "growth": None}, inputs, kind, y) for y in plan["years"]}
        vals = [r["value"] for r in rows.values()]
        v = sum(vals) if op == "sum" else sum(vals) / len(vals)
        return dict(value=v, unit=next(iter(rows.values()))["unit"], rows={f"{t} FY{y}": r for y, r in rows.items()},
                    lead=f"{op} of {plan['metric']} for {t}, FY{min(plan['years'])}-FY{max(plan['years'])}", fmt_value=True)
    if i == "lookup" and len(plan["companies"]) == 1 and len(plan.get("years") or []) >= 2 and not plan.get("growth"):
        t = plan["companies"][0]  # one company, several named years: answer every year (D-083)
        rows = {f"{t} FY{y}": company_value(G, t, plan, inputs, kind, y) for y in plan["years"]}
        label = plan["metric"] if kind != "x" and op != "share" else (" as % of " if op == "share" else "/").join(plan["metrics"])
        return dict(rows=rows, unit=next(iter(rows.values()))["unit"], missing={}, lead=label, fmt_value=False,
                    value={k: r["value"] for k, r in rows.items()})
    ts, strict = scope(G, plan)
    rows, missing = gather(G, plan, inputs, kind, ts, strict or i in ("aggregate", "compare"))
    unit = next(iter(rows.values()))["unit"]
    label = plan["metric"] if kind != "x" and op != "share" else (" as % of " if op == "share" else "/").join(plan["metrics"])
    if plan.get("growth"):
        label += f" {'growth' if plan['growth'] == 'pct' else 'change'}"
    res = dict(rows=rows, unit=unit, missing=missing)
    vals = {t: r["value"] for t, r in rows.items()}
    order = sorted(vals, key=vals.get, reverse=(op != "min"))
    if i == "aggregate":
        v = sum(vals.values()) if op == "sum" else sum(vals.values()) / len(vals)
        return {**res, "value": v, "lead": f"{op} of {label} across {', '.join(rows)}", "fmt_value": True}
    if op == "diff":
        a, b = list(rows)[:2]
        return {**res, "value": abs(vals[a] - vals[b]), "lead": f"|{label}: {a} - {b}|", "fmt_value": True}
    if op in ("max", "min") and not plan.get("topn"):
        w = order[0]
        return {**res, "value": vals[w], "winner": w,
                "lead": f"{w} has the {'highest' if op == 'max' else 'lowest'} {label}", "fmt_value": True}
    if plan.get("topn"):
        order = order[:plan["topn"]]
        res["rows"] = {t: rows[t] for t in order}
    elif i == "rank":
        res["rows"] = {t: rows[t] for t in order}
    if len(rows) == 1 and i != "rank":  # single company: scalar value
        return {**res, "value": next(iter(vals.values())), "lead": label, "fmt_value": False}
    return {**res, "value": {t: res["rows"][t]["value"] for t in res["rows"]}, "lead": f"{label}", "fmt_value": False}


def role_ok(role, title):
    """Word-boundary title match on the part before the first comma; 'vice president' is not 'president' (D-083)."""
    t = (title or "").lower().split(",")[0]
    if role in ("president", "chair"):
        t = re.sub(r"vice[\s-]*(president|chair)\w*", " ", t)
    return bool(re.search(rf"\b{re.escape(role)}" + (r"\b" if "president" in role else ""), t))


def entity_answer(G, plan, sel):
    rel, role, parts, ids, cites = plan["entity_rel"], plan.get("role"), [], [], []
    targets = [sel["winner"]] if sel else plan["companies"]
    found, missing = {}, []
    for t in targets:
        if rel == "EXECUTIVE_OF":
            hits = [(u, d) for u, _, d in G.in_edges(t, data=True) if d["rel"] == rel]
            hits = [(u, d) for u, d in hits if not role or role_ok(role, d.get("title") or G.nodes[u].get("role"))]  # "CEO, Commercial Business" is not the CEO
        else:
            hits = [(v, d) for _, v, d in G.out_edges(t, data=True) if d["rel"] == rel]
        if not hits:
            msg = f"{t} has no {rel} entity" + (f" with role '{role}'" if role else "") + " in the graph"
            if sel or len(targets) == 1:
                raise Abstain("no_fact", msg)
            missing.append(t)  # several companies asked: answer the ones we have and name the gaps (partial answer)
            continue
        found[t] = []
        for n, d in {h[0]: h for h in hits}.values():
            nd = G.nodes[n]
            title = d.get("title") or nd.get("role")
            found[t].append(f"{nd['name']}" + (f" ({title})" if rel == "EXECUTIVE_OF" and title else ""))
            ids.append(n)
            cites.append(cite(G, n))
        parts.append(f"{t}: " + "; ".join(found[t]))
    if not found:
        raise Abstain("no_fact", f"none of {', '.join(missing)} has a {rel} entity in the graph")
    parts += [f"{t}: not in the graph" for t in missing]
    return parts, ids, cites, found


def answer(question, G=None, lex=None):
    G = G or g.load_graph()
    plan, ab = planner.make_plan(question, lex)
    if ab:
        return dict(abstained=True, reason=ab[0], detail=ab[1], answer=f"Cannot answer ({ab[0]}): {ab[1]}",
                    value=None, fact_ids=[], citations=[], plan=plan)
    try:
        res = numeric_answer(G, plan) if plan["intent"] != "entity" or plan.get("op") else None
        if plan["intent"] != "entity":
            return finish(G, plan, res)
        sel = res
        parts, ids, cites, found = entity_answer(G, plan, sel)
        sel_ids = [i for r in sel["rows"].values() for i in r["ids"]] if sel else []
        text = "; ".join(parts) + (f" ({sel['lead']}: {fmt(sel['value'], sel['unit'])})" if sel else "")
        return dict(abstained=False, answer=text, value=found, unit=None, fact_ids=sel_ids + ids,
                    citations=[cite(G, f) for f in sel_ids] + cites, plan=plan,
                    validated=all(G.nodes[f].get("validated") is not False for f in sel_ids) if sel else None)
    except Abstain as e:
        return dict(abstained=True, reason=e.reason, detail=e.detail, answer=f"Cannot answer ({e.reason}): {e.detail}",
                    value=None, fact_ids=[], citations=[], plan=plan)


def finish(G, plan, res):
    rows, unit = res["rows"], res["unit"]
    ids = [f for r in rows.values() for f in r["ids"]]
    fyl = {r["fy"] for r in rows.values()}
    where = "FY" + "/FY".join(sorted(map(str, fyl))) if len(fyl) > 1 or any(isinstance(x, str) for x in fyl) else f"FY{next(iter(fyl))}"
    if res.get("fmt_value"):
        text = f"{res['lead']}: {fmt(res['value'], unit)} ({where})"
    else:
        text = f"{res['lead']} ({where}): " + "; ".join(f"{t if ' FY' in t else f'{t} FY{r['fy']}'} {fmt(r['value'], unit)}" for t, r in rows.items())
    if res.get("winner") and len(rows) > 1:
        text += " | " + "; ".join(f"{t} FY{r['fy']} {fmt(r['value'], unit)}" for t, r in rows.items())
    out = dict(abstained=False, answer=text, value=res["value"], unit=unit, fact_ids=ids,
               citations=[cite(G, f) for f in ids], plan=plan,
               validated=all(G.nodes[f].get("validated") is not False for f in ids))
    if "signed" in res:
        out["signed_value"] = res["signed"]
    if res.get("winner"):
        out["winner"] = res["winner"]  # lets the scorer credit only the winning entity (D-083)
    if len(fyl) > 1 and not all(" FY" in t for t in rows):
        out["mixed_years"] = True
    if res.get("missing"):
        out["incomplete"] = True
        out["missing"] = res["missing"]
    return out


def show(a):
    print(a["answer"])
    if a["abstained"]:
        return
    print(f"  validated: {a['validated']}" + (f"   mixed FYs: {a['mixed_years']}" if a.get("mixed_years") else "")
          + (f"   incomplete (no data: {a['missing']})" if a.get("incomplete") else ""))
    print("  fact ids:", ", ".join(a["fact_ids"]))
    for c in a["citations"]:
        print(f"  - {c['fact_id']}: {c['doc']} p.{c['page']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("question")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    a = answer(args.question)
    print(json.dumps(a, indent=2, default=str)) if args.json else show(a)


if __name__ == "__main__":
    main()

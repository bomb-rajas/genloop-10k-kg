"""Question -> structured plan (D-075). Rules first; the LLM only when rules give no valid plan.

plan = {intent, companies[], sector, metric, metrics[], years[], op, growth, entity_rel, role, topn}
intent: lookup | compare | rank | derived | growth | aggregate | entity
op: max | min | sum | avg | diff | ratio | None;  growth: None | pct | abs
make_plan(question) -> (plan, None) or (None, (abstain_reason, detail)).
"""
import json
import re

from src import llm
from src.config import load_companies, load_metrics

INTENTS = ("lookup", "compare", "rank", "derived", "growth", "aggregate", "entity")
OPS = (None, "max", "min", "sum", "avg", "diff", "ratio")
RELS = ("HEADQUARTERED_IN", "AUDITED_BY", "EXECUTIVE_OF", "HAS_SEGMENT", "INCORPORATED_IN", "LISTED_ON")
YEAR_RANGE = range(2000, 2040)

METRIC_ALIASES = {
    "Revenue": ["revenue", "sales", "net sales", "top line", "turnover"],
    "NetIncome": ["net income", "net earnings", "profit", "net profit", "bottom line", "earnings"],
    "EPS": ["eps", "earnings per share", "diluted eps"],
    "TotalAssets": ["total assets", "assets"],
    "TotalLiabilities": ["total liabilities", "liabilities"],
    "Equity": ["equity", "shareholders equity", "stockholders equity", "shareholder equity", "book value"],
    "GrossProfit": ["gross profit", "gross income"],
    "OperatingIncome": ["operating income", "operating profit", "operating earnings", "income from operations"],
    "OperatingCashFlow": ["operating cash flow", "cash flow from operations", "cash from operations",
                          "cash provided by operating activities"],
    "CapEx": ["capex", "capital expenditure", "capital spending"],
    "R&D": ["r&d", "research and development"],
    "Cash": ["cash", "cash and cash equivalents", "cash and equivalents"],
    "Employees": ["employee", "headcount", "number of employees", "workforce", "staff"],
    "NetMargin": ["net margin", "net profit margin", "net income margin", "profit margin"],
    "GrossMargin": ["gross margin", "gross profit margin"],
    "OperatingMargin": ["operating margin", "operating profit margin"],  # in-code derived (DERIVED_EXTRA in query.py)
}
VAGUE = {"income": "NetIncome vs OperatingIncome", "margin": "NetMargin vs GrossMargin vs OperatingMargin"}
SECTOR_ALIASES = {"Tech": ["tech", "technology", "software"], "Banks": ["bank", "banking", "financial", "payments", "payment"],
                  "Consumer": ["consumer", "retail", "retailer"], "Healthcare": ["healthcare", "health care", "pharma",
                                                                                 "pharmaceutical", "biotech"]}
EXTRA_NAMES = {"GOOGL": ["google"], "JPM": ["jp morgan", "chase"], "BAC": ["bofa"], "C": ["citi", "citibank"],
               "AXP": ["amex"], "PG": ["p&g"], "KO": ["coke"], "PEP": ["pepsi"], "JNJ": ["j&j"], "LLY": ["lilly"],
               "UNH": ["united health"], "META": ["facebook"], "WMT": ["wal mart"]}
GENERIC_FIRST = {"bank", "capital", "american", "home", "morgan", "johnson", "eli", "amazon"}
NAME_SUFFIX = {"inc", "corp", "corporation", "co", "company", "group", "holdings", "and", "ltd", "llc", "wholesale",
               "financial", "platforms", "laboratories", "health"}
CASE_SENSITIVE = {"target"}  # common English words: match only when capitalised
ENTITY_PATTERNS = [
    (r"headquarter|\bhq\b|where\b.*\b(based|located)", "HEADQUARTERED_IN", None),
    (r"auditor|audited|\baudits?\b|audit firm|accounting firm", "AUDITED_BY", None),
    (r"\bceo\b|chief executive", "EXECUTIVE_OF", "chief executive"),
    (r"\bcfo\b|chief financial", "EXECUTIVE_OF", "chief financial"),
    (r"\bcoo\b|chief operating", "EXECUTIVE_OF", "chief operating"),
    (r"\bpresident\b", "EXECUTIVE_OF", "president"),
    (r"\bchair(man|woman|person)?\b", "EXECUTIVE_OF", "chair"),
    (r"executive officers?|\bexecutives\b|\bofficers?\b|management team", "EXECUTIVE_OF", None),
    (r"\bsegments?\b", "HAS_SEGMENT", None),
    (r"incorporated|incorporation", "INCORPORATED_IN", None),
    (r"stock exchange|\blisted\b|\bexchange\b", "LISTED_ON", None),
]
MAX_RE = r"\b(largest|highest|biggest|greatest|most|top|higher|larger|greater|maximum)\b"
MIN_RE = r"\b(lowest|smallest|least|fewest|lower|smaller|minimum|bottom)\b"
OCF_RE = r"operating cash flow|cash flow from operations|cash from operations|cash provided by operating"
NUM_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}
NOT_COMPANY = {"Fiscal", "Item", "What", "Which", "Who", "How", "When", "Where", "The", "List", "Compare", "Rank", "Does",
               "Did", "Is", "Was", "Tell", "Give", "Name", "Find", "Show", "FY", "CEO", "CFO", "COO", "EPS", "CapEx",
               "Inc", "USD", "Tech", "Healthcare", "Consumer", "Banks", "Banking", "Please", "Calculate", "Among"}


def norm(s):
    s = s.lower().replace("'", "").replace("’", "").replace(" & ", " and ").replace("%", " percent ")
    return " " + re.sub(r"[^a-z0-9&]+", " ", s).strip() + " "


class Lexicon:
    """Alias tables built from companies.yaml and metrics.yaml (plus METRIC_ALIASES)."""

    def __init__(self, companies, metrics):
        self.tickers = {c["ticker"]: c for c in companies}
        self.sectors = {c["sector"] for c in companies}
        self.company_alias = {}
        for c in companies:
            toks = norm(c["name"]).split()
            while len(toks) > 1 and toks[-1] in NAME_SUFFIX:
                toks.pop()
            names = {" ".join(toks), *(norm(a).strip() for a in EXTRA_NAMES.get(c["ticker"], []))}
            if len(toks[0]) >= 4 and toks[0] not in GENERIC_FIRST:
                names.add(toks[0])
            for n in names:
                self.company_alias.setdefault(n, c["ticker"])
        self.base_metrics = {m["name"] for m in metrics["metrics"] + metrics.get("count_metrics", [])}
        self.derived = {d["name"] for d in metrics.get("derived", [])} | {"OperatingMargin"}
        self.metrics = self.base_metrics | self.derived
        self.metric_alias = {}
        for m in metrics["metrics"] + metrics.get("count_metrics", []):
            for s in m.get("synonyms", []):
                self.metric_alias[norm(s).strip()] = m["name"]
        for name, al in METRIC_ALIASES.items():  # explicit aliases win (e.g. 'gross margin' is GrossMargin)
            for a in al:
                self.metric_alias[norm(a).strip()] = name
        self.sector_alias = {norm(a).strip(): s for s, al in SECTOR_ALIASES.items() for a in al if s in self.sectors}


_LEX = None


def default_lexicon():
    global _LEX
    if _LEX is None:
        _LEX = Lexicon(load_companies(), load_metrics())
    return _LEX


def _find(text, aliases, case_text=None):
    """Longest-first alias spans in normalised text; returns [(start, canonical)] and the text with spans blanked."""
    found = []
    for alias in sorted(aliases, key=len, reverse=True):
        if alias in CASE_SENSITIVE and (case_text is None or alias.capitalize() not in case_text):
            continue
        for m in re.finditer(rf"(?<![a-z0-9&]){re.escape(alias)}(?:s|es)?(?![a-z0-9&])", text):
            found.append((m.start(), aliases[alias]))
            text = text[:m.start()] + "#" * (m.end() - m.start()) + text[m.end():]
    return sorted(found), text


def _years(q):
    ys = []
    for m in re.finditer(r"\bfy\s?(\d{4}|\d{2})\b|\b(?:fiscal(?: year)?|year)\s+(\d{4})\b|\b(20[0-3]\d)\b", q.lower()):
        y = int(next(g for g in m.groups() if g))
        y = y + 2000 if y < 100 else y
        if y in YEAR_RANGE and y not in ys:
            ys.append(y)
    return ys


def rule_plan(q, lex):
    """Return (plan, abstain) from rules only; plan is None when nothing usable was found."""
    n = norm(q)
    cos, n2 = _find(n, lex.company_alias, q)
    tickers = {t: lex.tickers[t] for t in lex.tickers}
    for m in re.finditer(r"\b[A-Z]{2,5}\b", q):  # explicit uppercase tickers (single letters C, V only via names)
        if m.group() in tickers:
            cos.append((n.find(norm(m.group()).strip()), m.group()))
    companies = []
    for _, t in sorted(cos, key=lambda x: x[0]):
        if t not in companies:
            companies.append(t)
    if re.search(r"\bcash flow\b", n) and not re.search(OCF_RE, n):  # e.g. 'free cash flow yield' has no metric
        return None, ("unsupported_metric", "cash flow here is not operating cash flow; only 'operating cash flow' is in the graph")
    ms, n3 = _find(n2, lex.metric_alias)
    metrics = []
    for _, m in ms:
        if m not in metrics:
            metrics.append(m)
    if not metrics:
        vague = [w for w in VAGUE if re.search(rf"\b{w}\b", n3)]
        if vague:
            return None, ("ambiguous", f"'{vague[0]}' could mean {VAGUE[vague[0]]}; name the metric")
    sector = None
    if not companies:
        sec, _ = _find(n3, lex.sector_alias)
        sector = sec[0][1] if sec else None
    low = re.sub(r"most recent|at least", " ", n3)
    sup = "max" if re.search(MAX_RE, low) else "min" if re.search(MIN_RE, low) else None
    plan = dict(intent=None, companies=companies, sector=sector, metric=metrics[0] if metrics else None,
                metrics=metrics, years=_years(q), op=None, growth=None, entity_rel=None, role=None, topn=None)
    for pat, rel, role in ENTITY_PATTERNS:
        if re.search(pat, low):
            plan.update(entity_rel=rel, role=role)
            break
    pct = re.search(r"grow\w*|grew|percent|yoy|year over year|rate", low)
    absolute = re.search(r"increase|decrease|change|rise|rose|fell|drop|decline|difference", low)
    tn = re.search(r"\btop (\d+|two|three|four|five|ten)\b", low)
    if tn:
        plan["topn"] = NUM_WORDS.get(tn.group(1)) or int(tn.group(1))
    two_years = len(plan["years"]) >= 2
    if plan["entity_rel"]:
        plan["intent"] = "entity"
        plan["op"] = sup if (sup and metrics and len(companies) != 1) else None
    elif re.search(r"\bsum\b|\bcombined\b|\btogether\b|\baggregate\b|\btotal\b|cumulative|\baverage\b|\bmean\b", low + (" total " if re.search(r"total (revenue|sales)", n) else "")) and (
            len(companies) >= 2 or sector or two_years):
        plan.update(intent="aggregate", op="avg" if re.search(r"\baverage\b|\bmean\b", low) else "sum")
        if two_years and re.search(r"\bthrough\b|\bto\b", low):
            plan["years"] = list(range(min(plan["years"]), max(plan["years"]) + 1))
    else:
        if re.search(r"\bratio\b|percent of|divided by", low) and len(metrics) == 2 and not any(
                m in lex.derived for m in metrics):
            plan["op"] = "ratio"
        if (pct or absolute) and (metrics or companies) and plan["op"] != "ratio" and (
                len(companies) <= 1 or sup):
            plan["growth"] = "pct" if pct and plan["metric"] not in lex.derived else "abs"  # margins change in points
            if plan["growth"] == "abs" and sup is None and len(companies) > 1:
                plan["growth"] = None
        if len(companies) >= 2 or sector or (not companies and sup):
            plan["intent"] = "rank" if (sup or sector or not companies or re.search(r"\brank", low)) else "compare"
            if re.search(r"difference|\bgap\b|how much (more|higher|larger)", low) and len(companies) == 2:
                plan.update(intent="compare", op="diff", growth=None)
            elif sup:
                plan["op"] = sup
        elif len(companies) == 1:
            plan["intent"] = ("growth" if plan["growth"] else
                              "derived" if plan["op"] == "ratio" or plan["metric"] in lex.derived else "lookup")
            if plan["intent"] == "lookup" and sup and len(metrics) == 0:
                plan["intent"] = None
    if plan["op"] == "ratio":
        plan["metrics"] = metrics[:2]
    if not companies and not sector and not sup and not plan["entity_rel"] and metrics:
        odd = [m.start() for m in re.finditer(r"\b[A-Z][A-Za-z&'.-]{2,}", q) if m.start() > 0
               and m.group() not in NOT_COMPANY]
        if odd:
            return None, ("unknown_company", f"no company in the graph matches '{re.match(r'[^ ?,.]+', q[odd[0]:]).group()}'")
    return plan, None


def check(plan, lex):
    """Return None if the plan is complete and consistent, else a short reason."""
    i, cos, ops = plan.get("intent"), plan.get("companies") or [], plan.get("op")
    scoped = bool(cos or plan.get("sector") or ops in ("max", "min"))
    if i not in INTENTS:
        return "bad intent"
    if i == "entity":
        return None if plan.get("entity_rel") and scoped and (len(cos) >= 1 or (ops and plan.get("metric"))) else "entity needs company or selector"
    if not plan.get("metric"):
        return "no metric"
    if ops == "ratio" and len(plan.get("metrics") or []) != 2:
        return "ratio needs two metrics"
    if i in ("lookup", "growth", "derived"):
        return None if len(cos) == 1 else f"{i} needs exactly one company"
    if i == "compare":
        return None if len(cos) >= 2 else "compare needs 2+ companies"
    if i == "aggregate":
        ok = ops in ("sum", "avg") and (len(cos) >= 2 or plan.get("sector") or len(plan.get("years") or []) >= 2)
        return None if ok else "aggregate needs a set of companies or years"
    return None if scoped or i == "rank" else "no scope"


LLM_SYSTEM = "You convert questions about SEC 10-K filings into a JSON query plan. Output JSON only."


def _llm_prompt(q, lex):
    return (f"Question: {q}\nAllowed tickers: {', '.join(f'{t}={c['name']}' for t, c in lex.tickers.items())}\n"
            f"Allowed sectors: {sorted(lex.sectors)}\nAllowed metrics: {sorted(lex.metrics)}\n"
            f"Allowed entity_rel: {list(RELS)}\nintent: {list(INTENTS)}\nop: max|min|sum|avg|diff|ratio|null\n"
            "Return exactly: {\"intent\":..., \"companies\":[tickers], \"sector\":null|name, \"metric\":null|name, "
            "\"metrics\":[names], \"years\":[fiscal-year ints, [] for latest], \"op\":..., \"growth\":null|\"pct\"|\"abs\", "
            "\"entity_rel\":null|name, \"role\":null|\"chief executive\"|\"chief financial\"|\"president\"|\"chair\", \"topn\":null|int}.\n"
            "Use only allowed values; use null/[] when the question does not say. Do not invent tickers.")


def validate_llm_plan(raw, lex):
    """Parse and validate an LLM plan; reject unknown ids. Returns (plan, None) or (None, (reason, detail))."""
    try:
        p = json.loads(raw)
        assert isinstance(p, dict)
    except (ValueError, AssertionError):
        return None, ("plan_failed", "LLM returned invalid JSON")
    cos = [str(t).upper() for t in p.get("companies") or []]
    bad = [t for t in cos if t not in lex.tickers]
    if bad:
        return None, ("unknown_company", f"unknown tickers from LLM plan: {bad}")
    ms = [m for m in (p.get("metrics") or []) + [p.get("metric")] if m]
    if any(m not in lex.metrics for m in ms):
        return None, ("plan_failed", f"unknown metric in LLM plan: {[m for m in ms if m not in lex.metrics]}")
    try:
        years = [int(y) for y in p.get("years") or []]
    except (TypeError, ValueError):
        return None, ("plan_failed", "bad years in LLM plan")
    topn = p.get("topn") if isinstance(p.get("topn"), int) else None
    plan = dict(intent=p.get("intent"), companies=cos, sector=p.get("sector"), metric=p.get("metric") or (ms[0] if ms else None),
                metrics=list(dict.fromkeys(ms)), years=[y for y in years if y in YEAR_RANGE], op=p.get("op"),
                growth=p.get("growth"), entity_rel=p.get("entity_rel"), role=p.get("role"), topn=topn)
    if plan["sector"] not in (None, *lex.sectors) or plan["op"] not in OPS or plan["growth"] not in (None, "pct", "abs") \
            or plan["entity_rel"] not in (None, *RELS):
        return None, ("plan_failed", "LLM plan has a value outside the allowed lists")
    err = check(plan, lex)
    return (plan, None) if err is None else (None, ("plan_failed", f"LLM plan incomplete: {err}"))


def make_plan(q, lex=None):
    lex = lex or default_lexicon()
    plan, abstain = rule_plan(q, lex)
    if abstain:
        return None, abstain
    if plan and check(plan, lex) is None:
        return plan, None
    try:
        raw = llm.complete(_llm_prompt(q, lex), system=LLM_SYSTEM, json_mode=True)
    except Exception as exc:  # no key / quota / network: abstain instead of guessing
        return None, ("plan_failed", f"rules found no valid plan and the LLM planner failed: {exc}")
    return validate_llm_plan(raw, lex)

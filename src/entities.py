"""LLM text-entity extraction (M4b) from PDF page text in data/parsed/{T}.json.

Per company: locate pages by keyword, ask the LLM for JSON per category, admit an entity only if its
name (or employee count) literally appears in the cited page text. Output data/entities/{T}.json and
{T}.rejected.json. Run: python -m src.entities [--tickers AAPL,JPM]
"""
import argparse
import json
import re
import unicodedata

from src.config import DATA_DIR, ENTITIES_DIR, PARSED_DIR, load_companies
from src.llm import _cache_key, _cache_read, complete

MAX_CHARS = 6000
CATEGORIES = ["cover", "segments", "employees", "auditor", "officers"]
SYSTEM = (
    "You extract named facts from excerpts of a US SEC Form 10-K. Reply with a single JSON object and nothing else. "
    "Copy every name and number exactly as it is written in the excerpt. If the excerpt does not contain a value, "
    "use null or an empty list. Do not guess or use outside knowledge."
)
SCHEMAS = {
    "cover": 'Keys: "state_of_incorporation" (string), "hq_city" (string), "hq_state" (string), '
             '"stock_exchange" (string, exchange name in the Section 12(b) table). Headquarters = principal executive offices on the cover.',
    "segments": 'Keys: "segments" (list of strings): names of the reportable (business) segments, exactly as written.',
    "employees": 'Keys: "employee_count" (integer, total employees, e.g. 166000; "2.1 million" = 2100000), '
                 '"as_written" (string, the number exactly as written in the excerpt, e.g. "166,000" or "2.1 million"), '
                 '"as_of" (string, the date or period stated, or null).',
    "auditor": 'Keys: "auditor_name" (string, firm that signed the report of independent registered public accounting firm), '
               '"auditor_city" (string, city of the firm as written under the signature, or null).',
    "officers": 'Keys: "executive_officers" (list of objects {"name": string, "title": string}), one per executive officer listed.',
}
RETRY_NOTE = "\n\nYour previous reply was not valid JSON. Reply with only the JSON object."
_complete = complete  # --regate swaps in cache_only (no network)
MISSES = [0]


class CacheMiss(RuntimeError):
    """Cache-only replay hit no cached reply; run_company counts the category as llm_failed."""


def cache_only(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    text = _cache_read(_cache_key(prompt, system, json_mode))
    if text is None:
        MISSES[0] += 1
        raise CacheMiss("no cached reply")
    return text


ITEM_RE = re.compile(r"\bItem\s+\d", re.I)
KIND_PREFIX = {"Person": "PERSON", "Organization": "ORG", "Location": "LOC", "Segment": "SEG"}


def load_pages(ticker: str) -> dict[int, str]:
    d = json.loads((PARSED_DIR / f"{ticker}.json").read_text(encoding="utf-8"))
    return {int(k): v for k, v in d["pages"].items()}


def _first(pages, pattern, start=1, skip_toc=False):
    """First page number >= start whose text matches pattern (and, if skip_toc, has fewer than 5 'Item N' mentions)."""
    rx = re.compile(pattern, re.I | re.S)
    for n in sorted(pages):
        t = pages[n]
        if n >= start and rx.search(norm_ws(t)) and not (skip_toc and len(ITEM_RE.findall(t)) >= 5):
            return n
    return None


def find_windows(pages: dict[int, str]) -> dict[str, list[int]]:
    """Pages sent to the LLM per category. Located page first; a second page is added for lists that spill over."""
    cover = next((n for n in (1, 2, 3) if n in pages and re.search(r"exact name of registrant", pages[n], re.I)), 1)
    seg = _first(pages, r"(reportable|operating)\s+(business\s+)?segments?")
    emp = _first(pages, r"(\d{1,3}(,\d{3})+|\d{4,}|\d+(\.\d+)?\s+million)\s+((full|part)[- ]time\s+)?(equivalent\s+)?(employees|associates|team members)\b") \
        or _first(pages, r"number of (employees|associates)") or _first(pages, r"human capital")
    aud = _first(pages, r"report of independent registered public accounting firm.*(present fairly|we have audited)")
    # shortcut: firm engagement sentence (Item 9 / audit fees) used when the signature is missing from the parsed report text
    eng = _first(pages, r"engaged\s+[^.]{0,60}?independent registered public accounting firm")
    off = _first(pages, r"executive officers of (the )?(registrant|company)(?!\s+\d)|information about (our )?executive officers",
                 start=4, skip_toc=True)
    sig = _first(pages, r"served as (the|our) company.s auditor since|/s/\s*[A-Z][\w&.,' -]{2,60}(LLP|LLC)")  # signature page of the audit report
    wins = {"cover": [cover], "segments": [seg], "employees": [emp, emp and emp + 1],
            "auditor": [sig] if sig else [eng, aud] if eng else [aud, aud and aud + 1], "officers": [off, off and off + 1]}
    # shortcut: window = located page (+1); a segment or officer list longer than that is cut off, upgrade if gaps show.
    return {k: [p for p in v if p and p in pages] for k, v in wins.items() if v[0]}


def excerpt(pages: dict[int, str], window: list[int]) -> str:
    return "\n".join(f"[page {n}]\n{pages[n]}" for n in window)[:MAX_CHARS]


def build_prompt(category: str, text: str) -> str:
    return f"Task: {SCHEMAS[category]}\n\nExcerpt:\n{text}"


def _parse(raw: str):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    obj = json.loads(s)
    return obj if isinstance(obj, dict) else None


def ask(category: str, text: str):
    """JSON object from the LLM, retried once with a changed prompt (llm.complete caches by prompt). None if both fail."""
    prompt = build_prompt(category, text)
    for attempt in range(2):
        try:
            obj = _parse(_complete(prompt if attempt == 0 else prompt + RETRY_NOTE, system=SYSTEM, json_mode=True))
        except ValueError:
            obj = None
        if obj is not None:
            return obj
    return None


def norm_ws(s: str) -> str:
    """Case and whitespace normalised; curly quotes unified. Punctuation kept (grounding is literal)."""
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("‘", "'").lower()).strip()


def ground(value: str, candidates: list[tuple[int, str]], prefer: int | None = None):
    """(page, snippet) where value literally appears in the candidate pages, else (None, None)."""
    needle = norm_ws(str(value))
    if not needle:
        return None, None
    rx = _literal_rx(needle)
    hits = [(n, norm_ws(t)) for n, t in candidates if rx.search(norm_ws(t))]
    if not hits:
        return None, None
    page, text = next(((n, t) for n, t in hits if n == prefer), hits[0])
    m = rx.search(text)
    return page, text[max(0, m.start() - 60): m.end() + 60]


def _literal_rx(needle: str):
    """Literal match whose edges fall on a boundary: '166,000' must not match inside '1,166,000'.
    A letter edge may not touch a letter; a digit edge may not touch a digit or a ',d' / '.d' continuation."""
    pre = r"(?<![0-9.,])" if needle[0].isdigit() else r"(?<![^\W\d_])" if needle[0].isalpha() else ""
    post = r"(?![0-9]|[.,][0-9])" if needle[-1].isdigit() else r"(?![^\W\d_])" if needle[-1].isalpha() else ""
    return re.compile(pre + re.escape(needle) + post)


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s.replace("'", "")).strip("-")


def entity_id(kind: str, ticker: str, name: str) -> str:
    if kind == "Person" or kind == "Segment":
        return f"{KIND_PREFIX[kind]}|{ticker}|{slug(name)}"
    if kind == "Organization" and re.search(r"exchange|market", name, re.I):
        return f"{KIND_PREFIX[kind]}|{exchange_slug(name)}"
    return f"{KIND_PREFIX[kind]}|{slug(name)}"


# shortcut: NYSE and New York Stock Exchange stay separate ids, upgrade with an alias table if a query needs them
EXCHANGE_NOISE = {"the", "llc", "global", "select", "market", "stock"}


def exchange_slug(name: str) -> str:
    """'The Nasdaq Stock Market LLC' and 'Nasdaq Global Select Market' both give 'nasdaq' (exchange-name noise dropped)."""
    out = []
    for tok in slug(name).split("-"):
        if tok and tok not in EXCHANGE_NOISE and (not out or out[-1] != tok):
            out.append(tok)
    return "-".join(out)


def _name_entity(ticker, category, kind, name, relation, window, pages, role=None):
    cands = [(n, pages[n]) for n in window]
    page, snippet = ground(name, cands, prefer=window[0])
    return {"id": entity_id(kind, ticker, name), "type": kind, "name": name, "relation": relation, "role": role,
            "category": category, "doc": f"data/pdfs/{ticker}.pdf", "page": page, "snippet": snippet,
            "grounded": page is not None}


NUM_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s+million|\d+")


def _count_value(token: str) -> int:
    if "million" in token:
        return round(float(token.split()[0]) * 1_000_000)
    return int(token.replace(",", ""))


def _str(obj, key):
    v = obj.get(key)
    return v.strip() if isinstance(v, str) and v.strip() else None


def build_entities(ticker, category, obj, window, pages, year):
    """Candidate entities for one category (grounded or not)."""
    out = []
    if category == "cover":
        if _str(obj, "state_of_incorporation"):
            out.append(_name_entity(ticker, category, "Location", _str(obj, "state_of_incorporation"), "INCORPORATED_IN",
                                    window, pages))
        city, state = _str(obj, "hq_city"), _str(obj, "hq_state")
        if city and state:
            out.append(_name_entity(ticker, category, "Location", f"{city}, {state}", "HEADQUARTERED_IN", window, pages))
        if _str(obj, "stock_exchange"):
            out.append(_name_entity(ticker, category, "Organization", _str(obj, "stock_exchange"), "LISTED_ON", window, pages))
    elif category == "segments":
        for name in obj.get("segments") or []:
            if isinstance(name, str) and name.strip():
                out.append(_name_entity(ticker, category, "Segment", name.strip(), "HAS_SEGMENT", window, pages))
    elif category == "auditor":
        if _str(obj, "auditor_name"):
            out.append(_name_entity(ticker, category, "Organization", _str(obj, "auditor_name"), "AUDITED_BY", window, pages))
        if _str(obj, "auditor_city"):
            out.append(_name_entity(ticker, category, "Location", _str(obj, "auditor_city"), "AUDITOR_BASED_IN", window, pages))
    elif category == "officers":
        for o in obj.get("executive_officers") or []:
            if isinstance(o, dict) and isinstance(o.get("name"), str) and o["name"].strip():
                out.append(_name_entity(ticker, category, "Person", o["name"].strip(), "EXECUTIVE_OF", window, pages,
                                        role=(o.get("title") or None)))
    elif category == "employees":
        try:
            n = int(str(obj.get("employee_count")).replace(",", "").strip())
        except (TypeError, ValueError):
            return out
        if n <= 0:
            return out
        cands = [(p, pages[p]) for p in window]
        written = _str(obj, "as_written")
        needle, reason = f"{n:,}", None
        if written:
            m = NUM_TOKEN_RE.search(written)
            if m and _count_value(m.group(0)) == n:
                needle = m.group(0)
            else:
                reason = f"as_written {written!r} does not give employee_count {n}"
        page, snippet = (None, None) if reason else ground(needle, cands, prefer=window[0])
        out.append({"id": f"{ticker}|Employees|FY{year}", "type": "Fact", "name": "Employees", "relation": "EMPLOYS_COUNT",
                    "value": n, "unit": "count", "category": category, "doc": f"data/pdfs/{ticker}.pdf",
                    "page": page, "snippet": snippet, "grounded": page is not None, "reason": reason})
    return out


def run_company(ticker: str, year: int):
    pages = load_pages(ticker)
    wins = find_windows(pages)
    cands, failed = [], []
    for cat in CATEGORIES:
        if cat not in wins:
            continue
        try:
            obj = ask(cat, excerpt(pages, wins[cat]))
        except RuntimeError:
            obj = None
        if obj is None:
            failed.append(cat)
            continue
        cands += build_entities(ticker, cat, obj, wins[cat], pages, year)
    admitted, rejected, seen = [], [], set()
    for e in cands:
        if not e["grounded"]:
            e.setdefault("reason", "not found in cited page text")
            rejected.append(e)
        elif e["id"] not in seen:
            seen.add(e["id"])
            admitted.append(e)
    missing = [c for c in CATEGORIES if not any(e["category"] == c for e in admitted)]
    return admitted, rejected, missing, failed


def write_company(ticker, admitted, rejected):
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    (ENTITIES_DIR / f"{ticker}.json").write_text(json.dumps({"ticker": ticker, "entities": admitted}, indent=2),
                                                 encoding="utf-8")
    (ENTITIES_DIR / f"{ticker}.rejected.json").write_text(json.dumps({"ticker": ticker, "entities": rejected}, indent=2),
                                                          encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="comma-separated tickers; default all 40")
    ap.add_argument("--regate", action="store_true", help="replay cached LLM replies only (no network); re-apply gate")
    args = ap.parse_args(argv)
    if args.regate:
        global _complete
        _complete = cache_only
    want = set(args.tickers.split(",")) if args.tickers else None
    filings = json.loads((DATA_DIR / "filings.json").read_text(encoding="utf-8"))
    rows, all_missing, counts = {}, {}, {}
    total_cands = grounded = rejected_n = 0
    for c in load_companies():
        t = c["ticker"]
        if want and t not in want:
            continue
        year = int(filings[t]["report_date"][:4])
        admitted, rejected, missing, failed = run_company(t, year)
        write_company(t, admitted, rejected)
        all_missing[t] = missing + [f"{x}(llm_failed)" for x in failed]
        for e in admitted:
            counts[e["type"]] = counts.get(e["type"], 0) + 1
        grounded += len(admitted)
        rejected_n += len(rejected)
        total_cands += len(admitted) + len(rejected)
        print(f"{t}: admitted {len(admitted)}, rejected {len(rejected)}, missing {all_missing[t]}", flush=True)
    print("per-type admitted:", counts)
    if args.regate:
        print(f"cache misses {MISSES[0]}")
    print(f"candidates {total_cands}, grounded {grounded} ({grounded / max(total_cands, 1):.1%}), rejected {rejected_n}")


if __name__ == "__main__":
    main()

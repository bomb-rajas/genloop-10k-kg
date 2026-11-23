"""Pure helpers that turn 10-K statement text (pdfplumber output) into numbers and rows.

No I/O here. parse.py calls these on pages it has already extracted from the PDF.
"""
import re

DASHES = {"—", "–", "―", "-", "--"}
SCALE_RE = re.compile(r"\b(?:in|amounts in|dollars in)\s+(dollars|units|thousands|millions|billions)\b|\(\s*(thousands|millions|billions)\b", re.I)
SCALE_VALUE = {"dollars": 1, "units": 1, "thousands": 1_000, "millions": 1_000_000, "billions": 1_000_000_000}
YEAR_RE = re.compile(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)")
MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?\s+\d{1,2}\b",
    re.I,
)
NUMBER_BODY = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+")


def parse_number(s):
    """Parse one as-reported cell. Returns float, or None when the cell is not a number.

    '(1,234)' -> -1234.0; '—', '–', '-' -> 0.0; '1,234(1)', '1,234*', '1,234 (a)' -> 1234.0
    (footnote stripped); '12.3%' -> 12.3; unicode minus and inner spaces are accepted.
    """
    if s is None:
        return None
    u = re.sub(r"\s+", "", str(s).replace("−", "-").replace("\xa0", " ")).replace("$", "")
    if not u:
        return None
    if u.strip("()") in DASHES:
        return 0.0
    while u and u[-1] in "*†‡":
        u = u[:-1]
    u = re.sub(r"\([a-z]\)$", "", u)  # letter footnote, so '(1,234)(a)' keeps its negative parentheses
    neg = False
    m = re.fullmatch(r"\((.*)\)%?", u)  # whole-cell parentheses are a negative, checked before footnotes
    if m:
        neg, u = True, m.group(1)
    else:
        u = re.sub(r"(\([a-z]\)|\(\d{1,2}\))$", "", u)  # trailing footnote marker
    u = u.rstrip("%")
    if u.startswith("-"):
        neg, u = True, u[1:]
    if not NUMBER_BODY.fullmatch(u):
        return None
    v = float(u.replace(",", ""))
    return -v if neg and v else v


def _is_value_token(tok):
    if parse_number(tok) is None:
        return False
    return any(c.isdigit() for c in tok) or tok.strip("$()") in DASHES


def parse_line(line):
    """Split one text line into (label, [values]) using the numeric tokens at the end of the line.

    Returns None when the line ends in no numeric token. Footnote letters like '(a)' stay in the label.
    """
    s = line.replace("−", "-").replace("\xa0", " ")
    s = re.sub(r"(?<=\S)\$", " $", s)  # '(19,669)$ (73,416)' glued by the PDF
    s = re.sub(r"([($])\s+", r"\1", s)  # '( 1,234' and '$ 36,305' -> one token each
    s = re.sub(r"\s+([)%])", r"\1", s)  # '1,234 )' and '12.3 %'
    toks = s.split()
    while toks and re.fullmatch(r"\([a-z]\)|[*†‡]+", toks[-1]):  # trailing footnote after the numbers
        toks.pop()
    # '(1)' after two plain values is a footnote marker, not -1. shortcut: a true third value of (1) is lost.
    if len(toks) >= 3 and re.fullmatch(r"\(\d\)", toks[-1]) and all(_is_value_token(t) and not t.startswith("(") for t in toks[-3:-1]):
        toks.pop()
    vals = []
    i = len(toks)
    while i > 0:
        t = toks[i - 1]
        if t == "$":
            i -= 1
            continue
        if not _is_value_token(t):
            break
        vals.insert(0, parse_number(t))
        i -= 1
    if not vals:
        return None
    label = " ".join(t for t in toks[:i] if t != "$").strip()
    return label, vals


def is_line_item(label):
    """True for a label that names a financial line (letters, not a date or year heading)."""
    return sum(c.isalpha() for c in label) >= 3 and not MONTH_RE.search(label) and not YEAR_RE.search(label)


def is_header_row(row):
    """True for rows that are column headings, not line items: date labels, or values that are all years."""
    vals = row["values"]
    return (not row["label"] or bool(MONTH_RE.search(row["label"]))
            or all(v.is_integer() and 1990 <= v <= 2100 for v in vals))


EPS_HEADING = re.compile(r"per\s+(common\s+|ordinary\s+)?share", re.I)
EPS_SUBHEAD = re.compile(r"basic|diluted", re.I)
EPS_RESET = re.compile(r"weighted|average|outstanding|dividend", re.I)


def parse_text_lines(text, keep_unlabeled=False):
    """Rows from page text. A label-only line is joined to the next line when that line starts lowercase
    (labels wrapped by the PDF, e.g. 'Common stock ... respectively' + 'authorized; ... 104,815 93,568').
    A numberless EPS heading ('Diluted earnings per share:', 'Basic') is prefixed to the labels of the rows
    after it until the next numberless line or a weighted-average/shares row.
    keep_unlabeled: rows with no label come back with label '' (unlabelled totals)."""
    rows, pending, heading = [], None, None
    for line in (text or "").splitlines():
        parsed = parse_line(line)
        if parsed is None:
            pending = line.strip() or None
            s = (pending or "").rstrip(":").strip()
            if not s or s.startswith("(") or len(s) > 90 or EPS_RESET.search(s):
                heading = None
            elif EPS_HEADING.search(s):
                heading = s
            elif EPS_SUBHEAD.fullmatch(s):
                heading = f"{heading} {s}" if heading and EPS_HEADING.search(heading) else s
            else:
                heading = None
            continue
        label, vals = parsed
        if pending and label[:1].islower():
            label = f"{pending} {label}"
        pending = None
        if label and heading:
            if EPS_RESET.search(label) or re.search(r"\bshares\b", label, re.I):
                heading = None
            else:
                label = f"{heading} {label}"
        if label or keep_unlabeled:
            rows.append({"label": label, "values": vals})
    return rows


def label_unlabeled_totals(rows, seen_assets=False):
    """Balance-sheet rows without a label: a bare total right after the equity block is 'Total liabilities and
    equity'; before any liabilities/equity row it is 'Total assets'. Other unlabelled rows are dropped.
    A total must be at least as large as every earlier row (a subtotal such as Merck's 115,605 is not).
    Returns (rows, seen_assets)."""
    out, cand = [], None  # cand: index in out of the latest bare row that could be total assets
    for r in rows:
        if r["label"]:
            seen_assets = seen_assets or bool(re.match(r"total assets", r["label"], re.I))
            out.append(r)
            continue
        if len(r["values"]) < 2 or len(out) < 3 or any(len(o["values"]) == len(r["values"]) and o["values"][0] > r["values"][0] for o in out):
            continue
        prev = out[-1]["label"] if out else ""
        past_liab = any(re.search(r"liabilit|equity|stockholders|shareholders", o["label"], re.I) for o in out)
        if re.search(r"equity|investment|deficit", prev, re.I):
            out.append({**r, "label": "Total liabilities and equity"})
        elif not past_liab and not seen_assets:
            if cand is not None:
                out[cand]["label"] = ""  # a later bare row supersedes (Merck: a gross-PP&E subtotal precedes the total)
            out.append({**r, "label": "?"})
            cand = len(out) - 1
    if cand is not None:
        out[cand]["label"] = "Total assets"
        seen_assets = True
    out = [o for o in out if o["label"] not in ("", "?")]
    return out, seen_assets


def rows_from_table(table):
    """Rows from a pdfplumber table (list of rows of cell strings or None). Cells are joined into one
    line first, which merges split '$' / ')' cells and label cells before parse_line runs."""
    rows = []
    for cells in table or []:
        parsed = parse_line(" ".join(c.replace("\n", " ") for c in cells if c))
        if parsed and parsed[0]:
            rows.append({"label": parsed[0], "values": parsed[1]})
    return rows


def merge_split_tables(prev_rows, next_rows):
    """Rows of a statement continued on the next page. The continuation has no header, so its rows keep
    their own value order; the caller maps columns from the first page. Empty rows are dropped."""
    return [{**r, "values": list(r["values"])} for r in prev_rows] + \
        [{**r, "values": list(r["values"])} for r in next_rows if r["values"] and r["label"]]


def header_text(text):
    """Text above the first line item of a statement page: title, unit line and column dates/years."""
    head = []
    for line in (text or "").splitlines():
        parsed = parse_line(line)
        if parsed and parsed[0] and len(parsed[1]) >= 2 and not is_header_row({"label": parsed[0], "values": parsed[1]}):
            break
        head.append(line)
    return "\n".join(head)


def find_scale(text):
    """(scale, matched_text) from a header such as 'in millions' or '(in thousands, except per share)'.
    (None, None) when the header has no unit. Callers must not assume a scale."""
    m = SCALE_RE.search(text or "")
    if not m:
        return None, None
    return SCALE_VALUE[(m.group(1) or m.group(2)).lower()], m.group(0)


def detect_scale(text):
    """Scale multiplier (1, 1e3, 1e6, 1e9) from header text, or None when absent."""
    return find_scale(text)[0]


def extract_years(text):
    """Unique 4-digit years in order of appearance, e.g. 'September 26, 2026 ... 2026 2025' -> [2026, 2025]."""
    years = []
    for y in (int(m) for m in YEAR_RE.findall(text or "")):
        if y not in years:
            years.append(y)
    return years


def pick_year_column(header, target_year=None):
    """Index into extract_years(header) of the newest year, or of target_year. None when no year is found
    or target_year is absent."""
    years = extract_years(header if isinstance(header, str) else " ".join(header))
    if not years:
        return None
    if target_year is not None:
        return years.index(target_year) if target_year in years else None
    return years.index(max(years))

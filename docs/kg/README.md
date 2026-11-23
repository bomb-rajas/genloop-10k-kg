# Knowledge graph views

**`explorer.html`** is the full interactive explorer: all 1,655 nodes / 4,693 edges from `graph/kg.json`, single file (~1.6 MB, vis-network 9.1.9 inlined, works offline on `file://`). Starts with Sectors + Companies; click a node to expand/collapse its neighbours, side panel shows all attributes (Fact: value, unit, period, doc, page, snippet, validated, xbrl_status, method) and clickable neighbours; type checkboxes, search (`AAPL`, `Apple`, `Revenue`, `AAPL|Revenue|FY2025`), Expand all / Reset / Freeze / Fit; hover an edge for its relation. Test hooks: URL hash `#expand=AAPL`, `#search=...`, `#all=1`, `#collapse=ID`.

Other views (double-click or `open docs/kg/overview.html`): `overview.html` (pan/zoom/search, hover for doc/page/snippet), `company_{AAPL,JPM,WMT,JNJ,MSFT}.html` (ego graphs with Fact nodes). Static: `overview.png`, `schema.png`, `ego_AAPL.png`.
The older per-view HTML files load vis-network 9.1.9 from unpkg (needs internet).

Regenerate from `graph/kg.json`:

    .venv/bin/pip install -r requirements-viz.txt
    .venv/bin/python scripts/render_kg.py   # template: scripts/explorer_template.html; lib cached in .cache/ (downloaded once)

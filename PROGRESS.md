# PROGRESS

| Milestone | Status | Time (IST) | Open issues |
|---|---|---|---|
| M0 Project memory files | done | 2026-11-23 03:01 | Original decision times not recorded in handoff.md (seeded entries use M0 time). Confirm whether Gemini secondary applies to the planner (D-014). |
| M1 Scaffold + config | done | 2026-11-23 03:03 IST | Not committed (user request). Smoke LLM call via Groq returned "pong" (cached). pytest 6 passed. CIKs fetched from SEC. Decisions D-022 to D-032 logged. Verification loop and ponytail review not run. |
| M2 Download EDGAR to PDF, fetch XBRL | done (financials check open) | 2026-11-23 03:08 IST | 40 ok in filings.json, but financials_page wrong for AXP p96, C p190, MRK p150, MCD p31 (D-042). Fix the rule before M3. V, TGT, WMT, AAPL look right. TGT FY label caveat (D-043). XBRL 175 MB gitignored (D-040). Verification and ponytail review not run. Not committed. |
| M3 Parse PDFs (text and tables) | done (value gaps noted) | 2026-11-23 03:59 IST (date: Mon Nov 23 03:59:04 IST 2026) | 40 of 40 have IS, BS, CF pages and a scale (loop 1, D-050 to D-052; rebuilt with --reuse-pages). Still open: labels not found for some key values: ABT and MRK total assets (MRK has no "Total assets" label), WMT net income ("Consolidated net income"), COF, KO and NKE revenue. Check per company before M4. Values as reported (no scaling). data/parsed about 20 MB, committed with the code (D-049); no git commit made. Tests: tests/test_tables.py and tests/test_parse.py, 90 pass. |
| M4 Extract facts + XBRL validation gate | pending | - | - |
| M5 Build graph | pending | - | - |
| M6 Query planner, traversal, abstain | pending | - | - |
| M7 Benchmark draft | pending | - | - |
| M8 Evaluate, fill Outcomes | pending | - | - |
| M9 README | pending | - | - |
| M10 docs/flow.md | pending | - | - |

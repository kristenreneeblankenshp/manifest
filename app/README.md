# Manifest Workbench — app

A web app that runs the **MOPS-003 / RCC-004 MASR Registry & Candidate Pipeline** workbook
(`data/workbook.xlsx`) as a live system. **The `.xlsx` is the single source of truth**: there is no
separate database. Every edit and workflow button writes into the workbook, and every gate, status,
KPI and roll-up you see is the workbook's own formula result.

```
npm install
npm start          # http://localhost:3000   (PORT / DATA_DIR env vars supported)
npm test           # end-to-end workflow test on a scratch copy
```

## How it works

| Piece | What it does |
|---|---|
| `lib/engine.js` | Loads all 34 sheets and ~14,000 formulas into [HyperFormula](https://hyperformula.handsontable.com) (plus `RANK` and Excel `TEXT` date formats), recalculates on every edit, and reports exactly which cells changed. |
| `lib/xlsxpatch.js` | Writes changes **surgically into the original `.xlsx` package** (input cells + refreshed cached formula values). Charts, styles, conditional formats, validation lists and formulas are preserved; the file is flagged to fully recalculate when opened in Excel. |
| `lib/tables.js` | Describes the record tables (pipeline, MASR registry, MIAR, evidence, review log, PEW-004 comparison, committee actions, companies to review). Input vs. calculated columns, dropdown options and date/number formats are **derived from the workbook**, not hard-coded. |
| `lib/actions.js` | Workflow buttons. They only write *input* cells; gates are evaluated by dry-running the workbook's formulas first (nothing is written if a gate fails unless the user explicitly records a gate exception). |
| `public/` | Vanilla-JS single-page app (no build step). |

## Screens

* **Overview** – RCC-004 control-center KPIs, exception table, stage funnel, registry composition, work queue, Decision Center and sleeve summary (all read from workbook cells).
* **Candidate Pipeline** – board (drag a card to advance; gate checked first) and list; record drawer with every field, calculated fields marked *fx*; buttons: Advance, Move to stage, Record committee disposition, Refer to PEW-004 (opens a PEW-004 comparison slot pre-filled from the registry), Close/Reject, Reopen, Log evidence.
* **MASR Registry / MIAR Dossiers / Evidence Ledger / MIAR Review Log / PEW-004 Comparison / Committee Actions / Companies to Review** – filterable tables, record drawers, "new record" forms with auto-generated IDs (`MCP-/EVD-/MIR-YYYYMMDD-###`, `OP-###`), CSV export.
* **Security 360** – one ticker across registry, MIAR, pipeline, evidence, reviews and PEW-004, with cross-links.
* **Any sheet** – faithful grid (fills, merges, widths, number formats) with a formula bar, *Show formulas*, clickable cross-sheet references, dropdowns from the workbook's validation lists, and in-place editing of input cells. Formula cells are protected.
* **Audit log** – every change is appended to the workbook sheet **`25 App Audit Log`** (time, user, action, cell, old → new).
* **Snapshots & download** – download the live `.xlsx`, snapshot and restore.

## Notes

* Recalculation uses HyperFormula, which follows Excel semantics. It was checked against the workbook's stored values: the only differences are `TODAY()`-driven values (candidates due 2026-09-23 are now overdue) and cells that reference empty cells, where the file's cached values came from a different engine. The app refreshes the stored cached values on start-up so the file is self-consistent.
* HyperFormula is used under its GPLv3 community license key (`gpl-v3`); obtain a commercial license if you distribute this app.
* No authentication is built in (single trusted team on a private network); the "Acting as" name is stamped on every audit entry.
* Excel can open the file while the app runs, but avoid saving it from Excel at the same time as app edits.

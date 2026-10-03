# Technical & Data Architecture

| | |
|---|---|
| **Document** | TDA-RCC004-001 |
| **Code** | `app/` (Node ≥ 18, Express 5, HyperFormula 3, SheetJS, JSZip, fast-xml-parser) |

# Part A — Technical architecture

## A1. Repository layout
```
app/
  server.js            HTTP API, snapshots, static hosting
  lib/engine.js        workbook load, recalculation, validation, audit, cache refresh
  lib/xlsxpatch.js     in-place OOXML writer (cells, rows, new sheet)
  lib/tables.js        record-table definitions and metadata derivation
  lib/actions.js       workflow actions
  public/              SPA: index.html, css/app.css, js/{main,ui,table,grid,views}.js
  data/                original.xlsx (pristine), workbook.xlsx (live), snapshots/
  test/workflow.test.js
docs/                  this documentation set
```

## A2. Engine (`lib/engine.js`)
- **Load:** SheetJS reads values, formulas, number formats; own parsers read `styles.xml` (fonts, fills, borders, numFmts → cellXfs) and each sheet's columns, row heights, merges, frozen panes, data validations. (The file uses `x:`-prefixed OOXML that common readers like ExcelJS cannot parse.)
- **Calculate:** HyperFormula with `useArrayArithmetic`. Extensions: `RANK`; `TEXT` rewritten to `XTEXT` (Excel date/percent/number masks); bare cross-sheet references to blank cells coerced to `0` (Excel semantics).
- **Edit pipeline:** `applyEdits` → validates → `setCellContents` in a batch → snapshot/diff of every sheet → `commit` (patch file, audit rows, version++) → debounced save.
- **Dry run:** `_trial(changes, probe)` applies, probes, always restores.
- **Serialisation:** all mutations through `run()` promise queue.
- **Cache refresh:** on start and on day change, stored formula values that differ from recalculation (e.g. `TODAY()` drift) are rewritten into the file.
- **Audit:** appends to sheet `25 App Audit Log` (created on first start).

## A3. Writer (`lib/xlsxpatch.js`)
- Maps sheet name → part via `workbook.xml` + rels.
- For each edited row/cell: replaces or inserts `<c>` preserving style (`s`) and existing `<f>`; new cells inherit style from the neighbouring row.
- Input values: numbers `t="n"`, text `t="inlineStr"`, blank → empty styled cell. Formula caches: `n`/`str`/`b`/`e`.
- Adds worksheet part, relationship and content-type override for the audit sheet; sets `fullCalcOnLoad="1"`.
- Saves via temp file + atomic rename.

## A4. API
| Method & path | Purpose |
|---|---|
| `GET /api/meta` | Sheets, table metadata, version, today |
| `GET /api/version` | Change counter (client polls every 6 s) |
| `GET /api/sheet/:name` | Cells (value, formula, style id), styles, widths, merges, validation lists |
| `GET /api/table/:key` | Table metadata + rows (`v` values, `f` formula flags, sheet row) |
| `GET /api/security/:ticker` | Cross-registry view for one ticker + certified allocation |
| `POST /api/action/:name` | Workflow actions (below) |
| `GET /api/audit?limit=` | Latest audit rows |
| `GET /api/download` | Live workbook |
| `GET/POST /api/snapshots`, `POST /api/restore` | Snapshot management |

**Actions:** `record.add`, `registry.add`, `candidate.create`, `candidate.advance`, `candidate.disposition`, `candidate.refer`, `candidate.close`, `candidate.reopen`, `cells.save`. Body `{user, params}`. Errors: `400` with `{error}` for validation/business failures (formula cell, off-list value, duplicate, no free slot), `500` otherwise. Blocked gate returns `200 {ok:false, blocked:true, projected, current}`.

## A5. Frontend
Hash router (`#/home`, `#/pipeline/<id>`, `#/security/<ticker>`, `#/sheet/<name>?cell=`); module per concern; no framework or build. Table columns are generated from `/api/table` metadata (input vs `fx`, dropdowns, date/number/percent types). Grid renders sheet styles faithfully and supports in-place edit of input cells. Theming via CSS variables with `prefers-color-scheme` dark mode.

## A6. Configuration, build, test, operations
| Item | Detail |
|---|---|
| Run | `npm install && npm start` (port 3000) |
| Env | `PORT`, `DATA_DIR` |
| Test | `npm test` — boots server on scratch copy; covers protection, validation, full lifecycle through PEW-004 referral |
| Logging | stdout/stderr |
| Backup | `data/snapshots/*.xlsx`; copy `data/` volume |
| Reset | copy `data/original.xlsx` over `data/workbook.xlsx` |

## A7. Security posture
No authentication or TLS built in; user name is self-declared. Formula cells protected; all inputs validated against workbook lists; snapshot names sanitised; JSON body capped at 4 MB. **Before shared use:** reverse proxy with TLS + SSO, role checks in `actions.js`, rate limiting, file-system permissions on `data/`.

# Part B — Data architecture

## B1. Data principles
Single authoritative store (the workbook); identifiers are business keys; calculated data is never persisted by the app (only mirrored as Excel cached values); history is append-only.

## B2. Data domains and sheets (34 sheets)
| Domain | Sheets |
|---|---|
| Executive / dashboard | 00 CISC Dashboard, 01 Dashboard Controls, 02 Decision Center, 03 Research Intelligence, 04 Committee Operations, 05 Workbench Guide, 99 Dashboard Data |
| Certified portfolio (MFPDF) | Executive Summary, Certified Allocation, Sleeve Summary, Rebalancing, Sources & Certification |
| Portfolio Engineering (PEW) | 06 Control Center, 07 Mandate & Constraints, 08 Sleeve Architecture, 09 Role Assignment, 10 Candidate Comparison, 11 Conviction, 12 Allocation Lab, 13 Validation & Cert, 14 Guide, 15 MOPS-002 Freeze Record, 98 PEW Lists |
| Research controls (RCC) | 16 RCC-001 CC, 17/18 RCC-002 CC & Evidence Ledger, 19/20/21 RCC-003 CC, MIAR Registry, Review Log, 22/23/24 RCC-004 CC, MASR Registry, Candidate Pipeline, 97 RCC Lists |
| Application | 25 App Audit Log |

## B3. Core entities
| Entity | Sheet | Rows | Business key | Key attributes (input) | Key derived (formula) |
|---|---|---|---|---|---|
| Certified holding | Certified Allocation | 47 | Ticker | sleeve, role, target weight, bands, actual weight | variance, band status |
| MASR record | 23 MASR Registry | 150 | Ticker (+ canonical MASR ID) | class, status, admission basis, sleeve, role, type, market cap, Zacks, Merrill, empirical rank, disposition | MIAR link/status, freshness, scores, evidence counts, **eligibility gate**, exception requirement, **control status**, required action |
| MIAR dossier | 20 MIAR Registry | 47 | Ticker (+ canonical MIAR ID) | integrity, MICS, record status, owner, cadence, last review dates | freshness, completeness, control status, counts |
| Evidence | 18 Evidence Ledger | 200 | `EVD-YYYYMMDD-###` | ticker, type, category, materiality, direction, reliability, source, summary, reviewer, status, verification, routing | days open, completeness, control status, referral eligibility |
| MIAR review | 21 Review Log | 200 | `MIR-YYYYMMDD-###` | ticker, type, reviewer, status/score proposals, findings, certification | prior values, control status |
| Candidate | 24 Candidate Pipeline | 200 | `MCP-YYYYMMDD-###` | ticker, type, group, target, source, evidence IDs, stage, owner, due, disposition, PEW flag/ID, closure | registry & research facts, **stage-gate result**, days open, **control status**, next action, PEW results |
| PEW-004 comparison | 10 Candidate Comparison | 20 | `CAND-###` | symbol, inputs, scores, decision | base/final score, eligibility, recommended action, status |
| Committee action | 04 Committee Operations | ~15 | `OP-###` | category, action, owner, due, priority, status, decision flag | — |
| Audit entry | 25 App Audit Log | unbounded | row | — | — |
| Controlled lists | 97 RCC Lists, 98 PEW Lists | — | — | dropdown values and required-action text | — |

## B4. Relationships
```
Certified Allocation 1──1 MASR Registry (certified rows 14–60, by position/ticker)
MASR Registry  1──0..1 MIAR Dossier      (ticker match, rows 14–60)
MASR Registry  1──*    Candidate Pipeline (ticker)
MASR Registry  1──*    Evidence Ledger   (ticker)
MIAR Dossier   1──*    MIAR Review Log   (ticker)
Candidate      *──*    Evidence          (Evidence IDs text list, ticker count)
Candidate      0..1──1 PEW-004 Comparison (PEW-004 Candidate ID)
```
Joins are `INDEX/MATCH` on ticker inside the workbook; the app mirrors none of them.

## B5. Candidate state model
```
Intake → Evidence Gathering → MIAR Review → Eligibility Review → Candidate Comparison
      → Committee Review → Approved for MASR → Referred to PEW-004
   any → On Watch | Rejected | Closed | Removed (closure needs reason, by, date)
```
Gate result per row: PASS — STAGE GATE | FAIL — {DUPLICATE ID, INCOMPLETE, MASR RECORD REQUIRED, ELIGIBILITY, EVIDENCE, MIAR GATE, COMMITTEE DISPOSITION, PEW REFERRAL}.
Control status: OPEN — ON TRACK | OVERDUE | CLOSED | CLOSURE REQUIRED | (gate-derived exceptions). Eligibility: CERTIFIED HOLDING | NOT ASSESSED | NOT ELIGIBLE | ELIGIBLE | ELIGIBLE WITH EXCEPTION.

## B6. Identifier rules
| Entity | Format | Generated by |
|---|---|---|
| Candidate | `MCP-YYYYMMDD-###` (date = intake date, sequence per date) | app |
| Evidence | `EVD-YYYYMMDD-###` (date received) | app |
| MIAR review | `MIR-YYYYMMDD-###` | app |
| Committee action | `OP-###` | app |
| PEW-004 slot | `CAND-###` (pre-seeded) | workbook |
| Canonical MASR / MIAR ID | institutional | entered by user |

## B7. Data quality and integrity controls
- Dropdown lists from `97/98 Lists` enforced server-side.
- Duplicate ID/ticker detection by workbook formulas; app blocks duplicate registry tickers.
- Required-field gates (INCOMPLETE) per stage.
- Dates stored as Excel serials, typed via cell number formats.
- Formula cells immutable through the app.

## B8. Audit data model — `25 App Audit Log`
`Timestamp (UTC) | User | Action | Sheet | Cell | Field | Previous Value | New Value | Record | Note`. Append-only; one row per changed input cell; forced gate exceptions carry action "Advance stage (forced — gate exception)" and the failing gate in Note.

## B9. Lifecycle, volume, retention
Capacity: 150 registry, 200 candidates/evidence/reviews, 20 PEW-004 slots (fixed by workbook ranges — extending requires changing formulas and `tables.js` ranges). File ≈ 0.5 MB. Retain snapshots per policy; archive audit rows periodically (export then trim outside the app).

## B10. Data security and privacy
Workbook contains firm-confidential research; protect `data/` with OS permissions and encrypted storage; downloaded copies are unmanaged — restrict the download endpoint with authentication when deployed.

# Solution Architecture

| | |
|---|---|
| **Document** | SA-RCC004-001 |
| **Pattern** | Workbook-as-database ("spreadsheet-native application") |

## 1. Context
Users need guided workflow, consolidated views and audit over a governed Excel workbook without moving the data out of it.

```
                ┌──────────────────────────────────────────────┐
  Browser  ───► │  Manifest Workbench app (Node.js, 1 process) │
  (SPA)    ◄─── │   REST/JSON API  +  static SPA               │
                │   ┌──────────────┐    ┌───────────────────┐  │
                │   │ Calc engine  │◄──►│ XLSX patch writer │  │
                │   │ HyperFormula │    │ (in-place OOXML)  │  │
                │   └──────┬───────┘    └─────────┬─────────┘  │
                └──────────┼──────────────────────┼────────────┘
                           │ load                 │ save (debounced)
                           ▼                      ▼
                   ┌─────────────────────────────────────┐
  Excel users ───► │  data/workbook.xlsx  (SOURCE OF TRUTH) │ ◄── snapshots/
                   └─────────────────────────────────────┘
```

## 2. Architecture principles
1. **One source of truth** — the `.xlsx`; no shadow database, no cached business state.
2. **Logic lives in the workbook** — gates, eligibility, statuses and roll-ups are formulas; the app supplies UX and orchestration only.
3. **Write inputs only** — actions set input cells; formulas produce outcomes.
4. **Dry-run before commit** — gated actions apply, read the workbook's verdict, then roll back or commit.
5. **Everything auditable** — each write is logged inside the workbook.
6. **Excel-compatible always** — the file stays a valid workbook users can open and keep working in.
7. **No build chain** — plain Node + vanilla JS.

## 3. Logical components
| Layer | Component | Responsibility |
|---|---|---|
| Presentation | SPA (`public/js`) | Router, views (Overview, tables, board, drawer, Security 360, grid, audit, admin), forms, toasts |
| API | `server.js` (Express) | Endpoints, error mapping, snapshots, static files |
| Application | `lib/actions.js` | Workflow actions: create, advance, disposition, refer, close, reopen, generic add/save |
| Domain metadata | `lib/tables.js` | Declares record tables; derives input/auto columns, dropdowns, formats from the workbook |
| Calculation | `lib/engine.js` | Loads sheets, recalculates, diffs, validates, audits |
| Persistence | `lib/xlsxpatch.js` | Surgical OOXML writer; adds audit sheet |
| Storage | `data/` | Live workbook, pristine `original.xlsx`, `snapshots/` |

## 4. Key runtime flows

### 4.1 Edit / action
1. SPA → `POST /api/action/{name}` `{user, params}`.
2. Action runs inside the serialised mutation queue.
3. Engine validates (not a formula cell; value in validation list) and applies to the in-memory model.
4. Model recalculates; engine diffs all cells → list of changed cells.
5. Writer patches input cells and refreshed cached values into the package; audit rows appended; version++.
6. Response returns new state and diff; SPA refreshes; other clients see the version bump within ~6 s.

### 4.2 Gated advance (dry run)
Apply proposed stage → read gate (`Z`), status (`AK`), action (`AL`) → always restore → if gate ≠ PASS and not forced, return blocker without writing; else commit with audit label (forced moves flagged).

### 4.3 PEW-004 referral
Find free row in `10 Candidate Comparison` → copy registry facts (only values permitted by that sheet's validation lists) → set referral flag, PEW ID, stage → gate-check → commit as one audited batch.

## 5. Integration points
| Integration | Mode |
|---|---|
| Excel / desktop users | Shared file (`workbook.xlsx`, download endpoint) |
| Portfolio Engineering (PEW) | Same workbook — PEW-004 sheet populated by referral |
| External data (Zacks/Merrill) | Not integrated (RCC-005 roadmap); values entered as inputs |
| Identity | None in v1 (roadmap: SSO) |

## 6. Deployment view
- Single Node ≥ 18 process; `npm start`; env `PORT`, `DATA_DIR`.
- Runs on a workstation, VM, or container with a persistent volume for `data/`.
- Put behind a TLS reverse proxy with authentication before any shared deployment.
- Back up `data/` (snapshots are plain `.xlsx`).

## 7. Quality attributes and tactics
| Attribute | Tactic |
|---|---|
| Integrity | Formula protection, list validation, serialised writes, dry-run gates, audit sheet |
| Fidelity | Patch-in-place writer keeps charts/styles/validations; fullCalcOnLoad flag for Excel |
| Recoverability | Snapshots, pre-restore snapshot, pristine baseline in repo |
| Performance | In-memory calc (~2 s load, ~150 ms edit); debounced persistence |
| Usability | Board/drawer workflow, blockers explained, cross-links, responsive, dark mode |
| Testability | Engine parity check against stored values; E2E workflow test |

## 8. Architecture decisions
| ADR | Decision | Rationale | Trade-off |
|---|---|---|---|
| 1 | Workbook as database | Mandated single source of truth | Single-writer; no row-level concurrency |
| 2 | HyperFormula in-process calc | Reproduces ~14k formulas without Excel/LibreOffice | Possible edge-case drift; licence terms |
| 3 | Surgical XML patching, not library round-trip | Generic libraries drop charts/conditional-format extensions | Custom code to maintain |
| 4 | Audit log as a workbook sheet | Keeps history inside the source of truth | Grows with use; needs archival policy |
| 5 | Derive table metadata from workbook | New columns/lists appear without code change | Table ranges declared in `tables.js` |
| 6 | Vanilla JS SPA | No build step, easy to host | Less structure than a framework |

## 9. Risks and evolution
Multi-user concurrency (add file lock/optimistic versioning), authentication/roles, external data ingestion (RCC-005), notifications, migration path to a relational store if volume outgrows the workbook — the `actions.js` interface and workbook-derived metadata isolate this change.

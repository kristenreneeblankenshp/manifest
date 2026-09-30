# Business Requirements Document (BRD)

| | |
|---|---|
| **Document** | BRD-RCC004-001 |
| **Initiative** | Manifest Workbench — workbook-native application for MOPS-003 / RCC-004 |
| **Status** | v1.0 delivered (PR #3); requirements traced to implementation |

## 1. Background
The Manifest institutional workbook (34 sheets, ~14,000 formulas) governs security identity, evidence, dossiers, candidate stage gates and PEW-004 referral. Users work directly in Excel, which offers no guided workflow, no action buttons, no consolidated security view and no change history. The workbook is, and must remain, the authoritative record.

## 2. Business objectives
| # | Objective | Success measure |
|---|---|---|
| O1 | Keep one source of truth | No data exists outside the `.xlsx`; app and Excel always agree |
| O2 | Enforce governance | No candidate advances past a failed gate without a recorded exception |
| O3 | Reduce effort and error | Records created via guided forms with auto IDs and validated inputs |
| O4 | Provide decision visibility | Exceptions, queue and funnel visible on one screen |
| O5 | Full auditability | 100% of app changes attributable (who/when/old/new) |

## 3. Scope
**In scope:** RCC-001…RCC-004 operations (MASR registry, MIAR dossiers, evidence ledger, review log, candidate pipeline), PEW-004 referral hand-off, committee action register, read/edit access to all 34 sheets, audit, snapshots.
**Out of scope:** trading or allocation changes, MFPDF issuance, market-data feeds (RCC-005 Zacks/Merrill crosswalk), authentication/SSO (future), MOPS-004.

## 4. Stakeholders
Research Operations, Research Committee, Stewardship Committee, Portfolio Engineering, Assigned Reviewers, Chief Investment Steward, Workbook Administrator.

## 5. Functional requirements
Priority: **M**ust / **S**hould / **C**ould. Status: ✅ delivered.

### 5.1 Source of truth and calculation
| ID | Requirement | Pri | Status |
|---|---|---|---|
| FR-01 | The `.xlsx` is the only data store; every edit persists into it | M | ✅ |
| FR-02 | All workbook formulas are evaluated; results shown in app are workbook results | M | ✅ |
| FR-03 | Formula cells cannot be overwritten; dropdown-governed inputs reject off-list values | M | ✅ |
| FR-04 | Charts, styles, validations and formulas in the file are preserved on save | M | ✅ |
| FR-05 | File opens and recalculates in Excel | M | ✅ (full-calc-on-load flag) |

### 5.2 Candidate pipeline
| ID | Requirement | Pri | Status |
|---|---|---|---|
| FR-10 | Create candidate with auto ID `MCP-YYYYMMDD-###` in first free slot (200) | M | ✅ |
| FR-11 | Advance/move stage with gate pre-check; failed gate writes nothing and explains blocker | M | ✅ |
| FR-12 | Forced advance allowed only explicitly and logged as exception | M | ✅ |
| FR-13 | Record committee disposition; mirror to registry | M | ✅ |
| FR-14 | Refer to PEW-004: open comparison slot pre-filled from registry and link IDs | M | ✅ |
| FR-15 | Close/reject/remove with reason, closer, date; reopen | M | ✅ |
| FR-16 | Board (drag to advance) and list views; search, status filter, sort, CSV export | S | ✅ |

### 5.3 Registry, research and evidence
| ID | Requirement | Pri | Status |
|---|---|---|---|
| FR-20 | Add securities to the 150-slot MASR registry; block duplicate tickers | M | ✅ |
| FR-21 | Maintain MIAR dossier fields for certified holdings | M | ✅ |
| FR-22 | Log evidence `EVD-…` and MIAR reviews `MIR-…` with auto IDs | M | ✅ |
| FR-23 | Committee action register and companies-requiring-review tables editable | S | ✅ |
| FR-24 | Security 360: all records for a ticker across registry, MIAR, pipeline, evidence, reviews, PEW-004 with cross-links | S | ✅ |

### 5.4 Visibility
| ID | Requirement | Pri | Status |
|---|---|---|---|
| FR-30 | Overview: KPIs, readiness, exception table, funnel, registry composition, work queue (all from workbook cells) | M | ✅ |
| FR-31 | Faithful grid of every sheet with formula bar, show-formulas, clickable references | S | ✅ |
| FR-32 | Global jump-to ticker or record ID | C | ✅ |
| FR-33 | Live refresh when the workbook changes | C | ✅ (6 s polling) |

### 5.5 Governance and administration
| ID | Requirement | Pri | Status |
|---|---|---|---|
| FR-40 | Every change appended to audit sheet with user, time, old/new | M | ✅ |
| FR-41 | Snapshot, restore and download of the workbook | M | ✅ |
| FR-42 | Serialised writes; no lost updates within one server | M | ✅ |

## 6. Non-functional requirements
| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-01 | Edit-to-recalculated-result latency | < 1 s typical (measured ≈150 ms) | ✅ |
| NFR-02 | Start-up (load and calculate) | < 10 s (measured ≈2 s) | ✅ |
| NFR-03 | Accessibility | Keyboard-operable rows/cards, focus states, labelled controls, light/dark themes | ✅ (baseline) |
| NFR-04 | Responsive | Usable at phone width | ✅ |
| NFR-05 | Portability | Runs on Node ≥ 18, no database or build step | ✅ |
| NFR-06 | Tested | Automated end-to-end workflow test | ✅ (`npm test`) |
| NFR-07 | Security | Authentication, TLS, per-role permissions | ❌ Planned (see §8) |

## 7. Business rules (from workbook)
Stage-gate rules, eligibility rules (Zacks ≥ 4, sub-$50B election, Merrill No Rating/Restricted → exception), control statuses and required actions are defined **in the workbook formulas** and its `97 RCC Lists` sheet. The app must never re-implement them; changing a rule means editing the workbook.

## 8. Assumptions, constraints, risks
| Item | Detail | Mitigation |
|---|---|---|
| A1 | Single trusted team, single server instance | Add auth/locking before multi-site use |
| A2 | Canonical MASR/MIAR IDs come from the institutional registry | Fields editable; flagged as exceptions until entered |
| C1 | MIAR lookups cover only 47 certified holdings (`B14:B60`) | Non-holdings cannot clear MIAR gate until workbook extended — a workbook change, flagged for decision |
| R1 | Concurrent Excel and app edits can overwrite each other | SOP: close Excel while app in use; snapshots |
| R2 | Calculation engine (HyperFormula) may differ from Excel in edge cases | Verified against stored values; Excel recalculates on open |
| R3 | HyperFormula GPLv3 licence | Obtain commercial licence before distribution |

## 9. Acceptance criteria (met)
1. A candidate can be taken Intake → Referred to PEW-004 with failed gates blocking and explained (automated test).
2. Edits to formula cells and off-list values are rejected (automated test).
3. All changes appear in the audit sheet.
4. Saved file re-loads with identical values; XML valid.

## 10. Roadmap
Authentication and roles; optimistic concurrency/locking; RCC-005 Zacks/Merrill data integration; notifications for overdue items; MIAR support for non-holdings; scheduled snapshots.

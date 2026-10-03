# Standard Operating Procedure — RCC-004 MASR Registry & Candidate Pipeline

| | |
|---|---|
| **Document** | SOP-RCC004-001 |
| **System** | Manifest Workbench app (`app/`) over `Manifest_Workbench … RCC-004 … v0_4.xlsx` |
| **Governing principle** | *Research identifies and evaluates change. Portfolio Engineering designs the response. Committee governance authorizes the response. The certified MFPDF remains the sole portfolio system of record.* (workbook MOPS-003 control principle) |
| **Audience** | Research Operations, Research Committee, Stewardship Committee, Portfolio Engineering, Assigned Reviewers |

## 1. Purpose and scope
Defines how security identity, evidence, candidate review and committee disposition are recorded and progressed so that every decision is evidence-controlled and auditable. Covers the seven RCC-004 operating steps (Register → Classify → Evidence → Test → Advance → Decide → Refer).

**Out of scope:** trading, changing certified allocation weights, issuing a new MFPDF version. The app and workbook record research judgment only. RCC-005 (Zacks / Merrill crosswalk) and MOPS-004 are not yet built.

## 2. Roles
| Role | Responsibility in this SOP |
|---|---|
| Research Operations | Canonical MASR/MIAR IDs, registry upkeep, advancing candidates, evidence logging |
| Assigned Reviewer | Verifies evidence, completes MIAR dossier and reviews |
| Research Committee | Classification, eligibility exceptions, recommends dispositions |
| Stewardship Committee | Records formal committee disposition and decision date |
| Portfolio Engineering | Receives PEW-004 referrals and designs the response |
| Workbook Administrator | Snapshots, restores, deployment, access |

## 3. Hard controls (enforced by workbook formulas)
1. One unique canonical MASR ID and one active registry row per security.
2. Certified holdings remain certified unless governance changes them.
3. No candidate reaches PEW-004 without an RCC-004 registry record.
4. MIAR, Integrity, MICS and empirical evidence precede advancement.
5. Zacks election < $50B, Zacks Rank #4/#5, Merrill "No Rating" or restricted research require documented exception treatment — never silent.
6. Automatic selection is prohibited; committee decision is always required.
7. Formula cells are never overwritten. Edits go to input cells only.

## 4. Procedures

### 4.1 Start of session
1. Open the app; set **Acting as** (top bar) to your name — it is stamped on every audit entry.
2. Review **Overview**: readiness banner, control exceptions, work queue, registry exceptions.

### 4.2 Register a security (MASR Registry)
1. **Registry → Add security** (or **Security 360 → Add to MASR registry**).
2. Complete ticker, name, record class, status, admission basis, sleeve, role, security type. Enter the **existing canonical MASR ID** from the institutional registry — do not invent one.
3. Enter market cap ($B), Zacks rank, Merrill status, empirical rank when known.
4. Save. Check the resulting *Registry Control Status*; follow the *Required Action* shown. Certified holdings (47) are pre-loaded and read-only for identity fields.

### 4.3 Maintain the MIAR dossier (certified holdings)
1. **MIAR Dossiers →** open the ticker. Enter Canonical MIAR ID, Record Status (*Active* to be gate-eligible), Integrity and MICS scores, Research Owner, Review Cadence, Last Full Review date.
2. Log each review under **MIAR Review Log → Log review** (`MIR-YYYYMMDD-###`), citing Evidence IDs.
3. *Research Freshness* must read **CURRENT** for advancement; **OVERDUE** or **MATERIAL EVENT REVIEW** blocks eligibility.

### 4.4 Log evidence (RCC-002)
1. **Evidence Ledger → Log evidence** (`EVD-YYYYMMDD-###`). One row per distinct signal; never combine unrelated events.
2. Mandatory: dates, record type, ticker, activity, category, materiality, source type, source/publisher, summary, reviewer, due date, status. Record the URL or memo reference.
3. High/critical unverified evidence escalates; PEW referrals require verified evidence.

### 4.5 Create a candidate
1. **Pipeline → New candidate** (or **Start candidate review** from a registry/Security 360/evidence record).
2. Enter ticker, candidate type, source, owner, due date; add comparison group, replacement target, evidence IDs, thesis summary and source memo.
3. The app assigns `MCP-YYYYMMDD-###` and stage **Intake**. A warning appears if the ticker has no registry record — create it (4.2) before MIAR Review.

### 4.6 Advance through stage gates
Stages: Intake → Evidence Gathering → MIAR Review → Eligibility Review → Candidate Comparison → Committee Review → Approved for MASR → Referred to PEW-004; exits: On Watch, Rejected, Closed, Removed.
1. Use **Advance →**, **Move to stage…**, or drag the card on the board.
2. The app dry-runs the workbook gate. If it fails, a dialog shows the gate result, status and required action, and **nothing is written**.

| Gate result | Meaning | Resolution |
|---|---|---|
| FAIL — INCOMPLETE | Missing intake date, ticker, type, source, stage, owner or due date | Complete fields in the record |
| FAIL — MASR RECORD REQUIRED | No registry record | Add to registry (4.2) |
| FAIL — ELIGIBILITY | Eligibility ≠ ELIGIBLE / ELIGIBLE WITH EXCEPTION / CERTIFIED HOLDING | Fix MIAR, scores, empirical rank, or document exception |
| FAIL — EVIDENCE | No evidence logged for ticker | Log evidence (4.4) |
| FAIL — MIAR GATE | MIAR not *Active* or freshness ≠ CURRENT | Update dossier (4.3) |
| FAIL — COMMITTEE DISPOSITION | Disposition blank/Pending | Record disposition (4.7) |
| FAIL — PEW REFERRAL | Referral flag, PEW ID or linkage missing | Refer to PEW-004 (4.8) |

3. **Advance anyway** is permitted only with documented justification; the forced move and gate result are written to the audit log and must be reviewed by the Research Committee.

### 4.7 Record committee disposition
Stewardship Committee (or delegate) selects **Record committee disposition**: choose disposition and decision date. The app mirrors it to the registry record (*Committee Disposition*, *Last Committee Review*) for non-certified securities.

### 4.8 Refer to PEW-004
1. Candidate must be at *Approved for MASR* with a disposition.
2. **Refer to PEW-004**. The app opens the next free slot in *10 Candidate Comparison* (`CAND-###`), pre-fills symbol, name, type, sleeve, role, market cap, Merrill, Zacks, MICS, Integrity and empirical rank, sets the referral flag and stage.
3. Portfolio Engineering completes scoring in PEW-004. Research does not design the portfolio response.

### 4.9 Close, reject, remove
**Close / reject…** → outcome (Rejected / Closed / Removed), reason from the controlled list, closed by, date. Closed records stay on the ledger. **Reopen on watch** reverses a closure (audited).

### 4.10 Exceptions and overdue items
Daily: clear **OVERDUE** and **COMMITTEE DECISION REQUIRED** queue items on Overview. Extend a due date only with a stated reason in *Source / Internal Memo / Exception Rationale*.

### 4.11 Direct sheet edits
Any of the 34 sheets can be opened (**All sheets**). Edit only input cells; allowed values come from the workbook's validation lists. Formula cells are protected.

## 5. Weekly and periodic cadence
| Frequency | Activity | Owner |
|---|---|---|
| Daily | Work queue, overdue candidates, new evidence | Research Operations |
| Weekly | Committee Actions register; committee dispositions; PEW-004 referrals | Stewardship / Research Committee |
| Per cadence (90/180/365 days) | MIAR reviews per dossier cadence | Assigned Reviewer |
| Weekly / before committee | **Snapshot** the workbook (Snapshots & download) | Administrator |
| Quarterly | Audit-log review; access review | Administrator |

## 6. Audit and record keeping
Every change is appended to workbook sheet **25 App Audit Log**: UTC time, user, action, sheet, cell, field, previous value, new value, record ID, note. Do not edit or delete rows. Retain workbook snapshots per firm retention policy.

## 7. Backup and recovery
1. **Snapshots & download → Create snapshot** before committee cycles and bulk changes.
2. **Restore** replaces the live workbook with a snapshot; the prior state is saved first as `pre-restore-*`.
3. The workbook can be downloaded and opened in Excel at any time. Close it before making further edits in the app.

## 8. Controls checklist (per committee cycle)
- [ ] Control exceptions on Overview reviewed; each has owner and date
- [ ] No candidate at Approved/Referred with disposition Pending
- [ ] Every forced gate exception in the audit log has a rationale
- [ ] Canonical MASR/MIAR IDs present for all active records
- [ ] Snapshot taken and downloaded copy archived

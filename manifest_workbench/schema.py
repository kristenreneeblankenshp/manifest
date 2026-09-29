"""Field schema for every workbench table.

Each table mirrors one worksheet of the Manifest Workbench v0.4. Fields keep the
worksheet column letter so users can refer to a field either by its key
(``market_cap``) or by its spreadsheet column (``T``).

Field kinds follow the workbook colour convention:

* ``input``  -- blue text / yellow fill: operator-maintained input.
* ``auto``   -- black text: formula / calculated output. Never stored.
* ``link``   -- green text: linked from another worksheet. Never stored.
* ``locked`` -- certified MFPDF data. Stored, but may not be edited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from . import lists as L

INPUT, AUTO, LINK, LOCKED = 'input', 'auto', 'link', 'locked'
TEXT, DATE, NUMBER, INT, PERCENT = 'text', 'date', 'number', 'int', 'percent'


@dataclass(frozen=True)
class Field:
    key: str
    col: str
    header: str
    kind: str = INPUT
    vtype: str = TEXT
    choices: Optional[Sequence] = None

    @property
    def stored(self) -> bool:
        return self.kind in (INPUT, LOCKED)


@dataclass(frozen=True)
class Table:
    name: str
    sheet: str
    first_row: int
    capacity: int
    fields: tuple

    def field(self, name: str) -> Field:
        """Resolve a field by key, column letter or header (case-insensitive)."""
        wanted = name.strip().lower().replace('-', '_')
        for f in self.fields:
            if wanted in (f.key, f.col.lower(), f.header.lower()):
                return f
        prefix = [f for f in self.fields if f.key.startswith(wanted)]
        if len(prefix) == 1:
            return prefix[0]
        hint = f" (did you mean: {', '.join(f.key for f in prefix)}?)" if prefix else ''
        raise KeyError(f"{self.name}: unknown field '{name}'{hint}. "
                       f"Run '{self.name} fields' to list fields")

    def keys(self, kind: Optional[str] = None) -> list:
        return [f.key for f in self.fields if kind is None or f.kind == kind]


def _t(name, sheet, first_row, capacity, *fields):
    return Table(name, sheet, first_row, capacity, tuple(fields))


F = Field

ALLOCATION = _t(
    'portfolio', 'Certified Allocation', 5, 47,
    F('sleeve', 'A', 'Production Sleeve', LOCKED, TEXT, L.SLEEVES),
    F('symbol', 'B', 'Symbol', LOCKED),
    F('security', 'C', 'Security', LOCKED),
    F('security_type', 'D', 'Security Type', LOCKED, TEXT, L.SECURITY_TYPE),
    F('role', 'E', 'Portfolio Role', LOCKED),
    F('target_weight', 'F', 'Target Weight', LOCKED, PERCENT),
    F('lower_band', 'G', 'Lower Band', AUTO, PERCENT),
    F('upper_band', 'H', 'Upper Band', AUTO, PERCENT),
    F('actual_weight', 'I', 'Actual Weight', INPUT, PERCENT),
    F('variance', 'J', 'Variance to Target', AUTO, PERCENT),
    F('band_status', 'K', 'Band Status', AUTO),
    F('rebalancing_action', 'L', 'Rebalancing Action', AUTO),
    F('conviction_tier', 'M', 'Conviction Tier', INPUT, TEXT, L.MFPDF_CONVICTION_TIER),
    F('research_status', 'N', 'Research Status', INPUT, TEXT, L.MFPDF_RESEARCH_STATUS),
)

CONVICTION = _t(
    'conviction', '11 Conviction', 5, 47,
    F('sleeve', 'A', 'Production Sleeve', LINK),
    F('symbol', 'B', 'Symbol', LINK),
    F('security', 'C', 'Security', LINK),
    F('security_type', 'D', 'Type', LINK),
    F('certified_weight', 'E', 'Certified Weight', LINK, PERCENT),
    F('current_conviction', 'F', 'Current Conviction', LINK),
    F('proposed_conviction', 'G', 'Proposed Conviction', INPUT, TEXT, L.CONVICTION_TIER),
    F('effective_conviction', 'H', 'Effective Conviction', AUTO),
    F('conviction_score', 'I', 'Conviction Score', AUTO, INT),
    F('thesis_status', 'J', 'Thesis Status', INPUT, TEXT, L.THESIS_STATUS),
    F('research_status', 'K', 'Research Status', LINK),
    F('risk_class', 'L', 'Risk Classification', INPUT, TEXT, L.RISK_CLASS),
    F('holding_period', 'M', 'Expected Holding Period', INPUT, TEXT, L.HOLDING_PERIOD),
    F('next_review_date', 'N', 'Next Review Date', INPUT, DATE),
    F('decision_state', 'O', 'Decision State', AUTO),
    F('committee_rationale', 'P', 'Committee Rationale', INPUT),
)

PEW004 = _t(
    'pew004', '10 Candidate Comparison', 14, 20,
    F('candidate_id', 'A', 'Candidate ID', LOCKED),
    F('comparison_group', 'B', 'Comparison Group'),
    F('candidate_type', 'C', 'Candidate Type', INPUT, TEXT, L.PEW_CANDIDATE_TYPE),
    F('symbol', 'D', 'Symbol'),
    F('security', 'E', 'Security'),
    F('proposed_sleeve', 'F', 'Proposed Sleeve', INPUT, TEXT, L.SLEEVES),
    F('proposed_role', 'G', 'Proposed Role', INPUT, TEXT, L.FUNCTIONAL_ROLE),
    F('market_cap', 'H', 'Market Cap ($B)', INPUT, NUMBER),
    F('merrill_status', 'I', 'Merrill Status', INPUT, TEXT, L.PEW_MERRILL_STATUS),
    F('zacks_rank', 'J', 'Zacks Rank', INPUT, INT, L.ZACKS_RANK),
    F('mics', 'K', 'MICS', INPUT, NUMBER),
    F('miar_integrity', 'L', 'MIAR / Integrity', INPUT, NUMBER),
    F('empirical_rank', 'M', 'Empirical Rank', INPUT, NUMBER),
    F('role_fit', 'N', 'Role Fit', INPUT, NUMBER),
    F('valuation', 'O', 'Valuation', INPUT, NUMBER),
    F('diversification', 'P', 'Diversification', INPUT, NUMBER),
    F('base_score', 'Q', 'Base Score', AUTO, NUMBER),
    F('close_decision', 'R', 'Close Decision?', INPUT, TEXT, L.YES_NO),
    F('zacks_overlay', 'S', 'Zacks Overlay', AUTO, NUMBER),
    F('final_score', 'T', 'Final Score', AUTO, NUMBER),
    F('eligibility_gate', 'U', 'Eligibility Gate', AUTO),
    F('recommended_action', 'V', 'Recommended Action', AUTO),
    F('committee_decision', 'W', 'Committee Decision', INPUT, TEXT, L.PEW_COMMITTEE_DECISION),
    F('notes', 'X', 'Evidence / Notes'),
    F('status', 'Y', 'Status', AUTO),
)

EVIDENCE = _t(
    'evidence', '18 RCC-002 Evidence Ledger', 14, 200,
    F('evidence_id', 'A', 'Evidence ID'),
    F('date_received', 'B', 'Date Received', INPUT, DATE),
    F('evidence_date', 'C', 'Evidence Date', INPUT, DATE),
    F('record_type', 'D', 'Record Type', INPUT, TEXT, L.RECORD_TYPE),
    F('ticker', 'E', 'Ticker'),
    F('subject', 'F', 'Security / Subject'),
    F('sleeve', 'G', 'Certified Sleeve', AUTO),
    F('activity_type', 'H', 'Activity Type', INPUT, TEXT, L.ACTIVITY_TYPE),
    F('category', 'I', 'Evidence Category', INPUT, TEXT, L.EVIDENCE_CATEGORY),
    F('materiality', 'J', 'Materiality', INPUT, TEXT, L.MATERIALITY),
    F('direction', 'K', 'Direction', INPUT, TEXT, L.DIRECTION),
    F('reliability', 'L', 'Reliability', INPUT, TEXT, L.RELIABILITY),
    F('source_type', 'M', 'Source Type', INPUT, TEXT, L.SOURCE_TYPE),
    F('publisher', 'N', 'Source / Publisher'),
    F('source_ref', 'O', 'Source Reference / URL'),
    F('summary', 'P', 'Evidence Summary'),
    F('thesis_sensitivity', 'Q', 'Thesis Sensitivity', INPUT, TEXT, L.THESIS_SENSITIVITY),
    F('reviewer', 'R', 'Assigned Reviewer'),
    F('due_date', 'S', 'Due Date', INPUT, DATE),
    F('status', 'T', 'Status', INPUT, TEXT, L.EVIDENCE_STATUS),
    F('verified', 'U', 'Verified?', INPUT, TEXT, L.VERIFICATION),
    F('miar_action', 'V', 'MIAR Action', INPUT, TEXT, L.MIAR_ACTION),
    F('thesis_impact', 'W', 'Thesis Impact', INPUT, TEXT, L.THESIS_IMPACT),
    F('conviction_rec', 'X', 'Conviction Recommendation', INPUT, TEXT, L.CONVICTION_RECOMMENDATION),
    F('candidate_replacement', 'Y', 'Candidate / Replacement', INPUT, TEXT, L.CANDIDATE_REPLACEMENT),
    F('pew_referral', 'Z', 'PEW Referral', INPUT, TEXT, L.PEW_REFERRAL),
    F('disposition', 'AA', 'Disposition', INPUT, TEXT, L.DISPOSITION),
    F('closed_date', 'AB', 'Closed Date', INPUT, DATE),
    F('days_open', 'AC', 'Days Open', AUTO, INT),
    F('completeness', 'AD', 'Record Completeness', AUTO),
    F('control_status', 'AE', 'Control Status', AUTO),
    F('referral_eligibility', 'AF', 'Referral Eligibility', AUTO),
    F('notes', 'AG', 'Notes / Exception Rationale'),
)

MIAR = _t(
    'miar', '20 RCC-003 MIAR Registry', 14, 47,
    F('miar_id', 'A', 'Canonical MIAR ID'),
    F('ticker', 'B', 'Ticker', LINK),
    F('security', 'C', 'Security', LINK),
    F('sleeve', 'D', 'Production Sleeve', LINK),
    F('security_type', 'E', 'Security Type', LINK),
    F('role', 'F', 'Portfolio Role', LINK),
    F('certified_weight', 'G', 'Certified Weight', LINK, PERCENT),
    F('mfpdf_research_status', 'H', 'MFPDF Research Status', LINK),
    F('effective_conviction', 'I', 'Effective Conviction', AUTO),
    F('thesis_status', 'J', 'Thesis Status', AUTO),
    F('integrity_score', 'K', 'Integrity Score', INPUT, NUMBER),
    F('mics_score', 'L', 'MICS Score', INPUT, NUMBER),
    F('record_status', 'M', 'Record Status', INPUT, TEXT, L.MIAR_RECORD_STATUS),
    F('research_owner', 'N', 'Research Owner'),
    F('review_cadence', 'O', 'Review Cadence', INPUT, TEXT, L.REVIEW_CADENCE),
    F('cadence_days', 'P', 'Cadence Days', AUTO, INT),
    F('last_full_review', 'Q', 'Last Full Review', INPUT, DATE),
    F('last_incremental', 'R', 'Last Incremental Update', INPUT, DATE),
    F('latest_dossier_date', 'S', 'Latest Dossier Date', AUTO, DATE),
    F('next_review', 'T', 'Next Scheduled Review', AUTO, DATE),
    F('review_log_entries', 'U', 'Review Log Entries', AUTO, INT),
    F('evidence_records', 'V', 'Evidence Records', AUTO, INT),
    F('open_evidence', 'W', 'Open Evidence Records', AUTO, INT),
    F('miar_actions_pending', 'X', 'MIAR Actions Pending', AUTO, INT),
    F('material_event_reviews', 'Y', 'Material-Event Reviews', AUTO, INT),
    F('research_freshness', 'Z', 'Research Freshness', AUTO),
    F('dossier_completeness', 'AA', 'Dossier Completeness', AUTO),
    F('control_status', 'AB', 'Control Status', AUTO),
    F('required_action', 'AC', 'Required Action', AUTO),
    F('rcc007_referral', 'AD', 'RCC-007 Referral', AUTO),
    F('certified_by', 'AE', 'Last Certified / Reviewed By'),
    F('certification_date', 'AF', 'Certification Date', INPUT, DATE),
    F('notes', 'AG', 'Notes / Exception Rationale'),
)

REVIEWS = _t(
    'review', '21 RCC-003 MIAR Review Log', 14, 200,
    F('review_id', 'A', 'Review ID'),
    F('review_date', 'B', 'Review Date', INPUT, DATE),
    F('ticker', 'C', 'Ticker'),
    F('security', 'D', 'Security', AUTO),
    F('review_type', 'E', 'Review Type', INPUT, TEXT, L.MIAR_REVIEW_TYPE),
    F('reviewer', 'F', 'Reviewer'),
    F('evidence_ids', 'G', 'Evidence IDs Referenced'),
    F('prior_status', 'H', 'Prior Record Status', AUTO),
    F('proposed_status', 'I', 'Proposed Record Status', INPUT, TEXT, L.MIAR_RECORD_STATUS),
    F('prior_integrity', 'J', 'Prior Integrity Score', AUTO, NUMBER),
    F('proposed_integrity', 'K', 'Proposed Integrity Score', INPUT, NUMBER),
    F('prior_mics', 'L', 'Prior MICS Score', AUTO, NUMBER),
    F('proposed_mics', 'M', 'Proposed MICS Score', INPUT, NUMBER),
    F('thesis_assessment', 'N', 'Thesis Assessment', INPUT, TEXT, L.THESIS_ASSESSMENT),
    F('conviction_rec', 'O', 'Conviction Recommendation', INPUT, TEXT, L.CONVICTION_RECOMMENDATION),
    F('findings', 'P', 'Review Findings Summary'),
    F('required_miar_action', 'Q', 'Required MIAR Action', INPUT, TEXT, L.MIAR_ACTION),
    F('certification_rec', 'R', 'Certification Recommendation', INPUT, TEXT,
      L.CERTIFICATION_RECOMMENDATION),
    F('certified_by', 'S', 'Certified By'),
    F('certification_date', 'T', 'Certification Date', INPUT, DATE),
    F('control_status', 'U', 'Control Status', AUTO),
    F('notes', 'V', 'Notes / Exception Rationale'),
    F('source_ref', 'W', 'Source / Internal Memo Reference'),
)

MASR = _t(
    'masr', '23 RCC-004 MASR Registry', 14, 150,
    F('masr_id', 'A', 'Canonical MASR ID'),
    F('ticker', 'B', 'Ticker'),
    F('security', 'C', 'Security'),
    F('record_class', 'D', 'Record Class', INPUT, TEXT, L.MASR_RECORD_CLASS),
    F('registry_status', 'E', 'Registry Status', INPUT, TEXT, L.MASR_REGISTRY_STATUS),
    F('admission_basis', 'F', 'Admission Basis', INPUT, TEXT, L.ADMISSION_BASIS),
    F('sleeve', 'G', 'Production Sleeve', INPUT, TEXT, L.SLEEVES),
    F('role', 'H', 'Approved / Proposed Role'),
    F('security_type', 'I', 'Security Type', INPUT, TEXT, L.SECURITY_TYPE),
    F('certified_weight', 'J', 'Certified Weight', AUTO, PERCENT),
    F('miar_id', 'K', 'Canonical MIAR ID', AUTO),
    F('miar_status', 'L', 'MIAR Record Status', AUTO),
    F('research_freshness', 'M', 'Research Freshness', AUTO),
    F('integrity_score', 'N', 'Integrity Score', AUTO, NUMBER),
    F('mics_score', 'O', 'MICS Score', AUTO, NUMBER),
    F('effective_conviction', 'P', 'Effective Conviction', AUTO),
    F('thesis_status', 'Q', 'Thesis Status', AUTO),
    F('evidence_records', 'R', 'Evidence Records', AUTO, INT),
    F('open_evidence', 'S', 'Open Evidence Records', AUTO, INT),
    F('market_cap', 'T', 'Market Cap ($B)', INPUT, NUMBER),
    F('zacks_rank', 'U', 'Zacks Rank', INPUT, INT, L.ZACKS_RANK),
    F('merrill_status', 'V', 'Merrill Status', INPUT, TEXT, L.MERRILL_STATUS),
    F('empirical_rank', 'W', 'Empirical Rank', INPUT, NUMBER),
    F('eligibility_gate', 'X', 'Eligibility Gate', AUTO),
    F('exception_requirement', 'Y', 'Exception Requirement', AUTO),
    F('pipeline_records', 'Z', 'Candidate Pipeline Records', AUTO, INT),
    F('current_stage', 'AA', 'Current Candidate Stage', AUTO),
    F('committee_disposition', 'AB', 'Committee Disposition', INPUT, TEXT, L.COMMITTEE_DISPOSITION),
    F('pew_referral_state', 'AC', 'PEW Referral State', AUTO),
    F('control_status', 'AD', 'Registry Control Status', AUTO),
    F('required_action', 'AE', 'Required Action', AUTO),
    F('last_committee_review', 'AF', 'Last Committee Review', INPUT, DATE),
    F('approved_by', 'AG', 'Approved / Reviewed By'),
    F('approval_date', 'AH', 'Approval / Review Date', INPUT, DATE),
    F('notes', 'AI', 'Notes / Source / Exception Rationale'),
)

# Registry fields that are linked to the certified MFPDF for Certified Portfolio
# Holdings (rows 14-60 of the registry) and so cannot be edited there.
MASR_CERTIFIED_LINKED = ('ticker', 'security', 'sleeve', 'role', 'security_type')
MASR_CERTIFIED_LOCKED = ('record_class', 'registry_status', 'admission_basis')

PIPELINE = _t(
    'pipeline', '24 RCC-004 Candidate Pipeline', 14, 200,
    F('candidate_id', 'A', 'Candidate ID'),
    F('intake_date', 'B', 'Intake Date', INPUT, DATE),
    F('ticker', 'C', 'Ticker'),
    F('security', 'D', 'Security', AUTO),
    F('candidate_type', 'E', 'Candidate Type', INPUT, TEXT, L.CANDIDATE_TYPE),
    F('comparison_group', 'F', 'Comparison Group'),
    F('incumbent_target', 'G', 'Incumbent / Replacement Target'),
    F('source', 'H', 'Source / Referral', INPUT, TEXT, L.CANDIDATE_SOURCE),
    F('proposed_sleeve', 'I', 'Proposed Sleeve', AUTO),
    F('proposed_role', 'J', 'Proposed Role', AUTO),
    F('masr_class', 'K', 'MASR Record Class', AUTO),
    F('masr_status', 'L', 'MASR Status', AUTO),
    F('eligibility_gate', 'M', 'Eligibility Gate', AUTO),
    F('exception_requirement', 'N', 'Exception Requirement', AUTO),
    F('miar_status', 'O', 'MIAR Record Status', AUTO),
    F('research_freshness', 'P', 'Research Freshness', AUTO),
    F('integrity_score', 'Q', 'Integrity Score', AUTO, NUMBER),
    F('mics_score', 'R', 'MICS Score', AUTO, NUMBER),
    F('empirical_rank', 'S', 'Empirical Rank', AUTO, NUMBER),
    F('market_cap', 'T', 'Market Cap ($B)', AUTO, NUMBER),
    F('zacks_rank', 'U', 'Zacks Rank', AUTO, INT),
    F('merrill_status', 'V', 'Merrill Status', AUTO),
    F('evidence_ids', 'W', 'Evidence IDs Referenced'),
    F('evidence_records', 'X', 'Evidence Records', AUTO, INT),
    F('stage', 'Y', 'Candidate Stage', INPUT, TEXT, L.CANDIDATE_STAGE),
    F('gate_result', 'Z', 'Stage Gate Result', AUTO),
    F('owner', 'AA', 'Assigned Owner'),
    F('due_date', 'AB', 'Due Date', INPUT, DATE),
    F('days_open', 'AC', 'Days Open', AUTO, INT),
    F('committee_disposition', 'AD', 'Committee Disposition', INPUT, TEXT, L.COMMITTEE_DISPOSITION),
    F('disposition_date', 'AE', 'Disposition Date', INPUT, DATE),
    F('pew_referral', 'AF', 'PEW Referral', INPUT, TEXT, L.PEW_REFERRAL_STATE),
    F('pew_candidate_id', 'AG', 'PEW-004 Candidate ID'),
    F('pew_final_score', 'AH', 'PEW-004 Final Score', AUTO, NUMBER),
    F('pew_eligibility', 'AI', 'PEW-004 Eligibility', AUTO),
    F('pew_status', 'AJ', 'PEW-004 Status', AUTO),
    F('control_status', 'AK', 'Control Status', AUTO),
    F('next_action', 'AL', 'Next Required Action', AUTO),
    F('thesis_summary', 'AM', 'Decision / Thesis Summary'),
    F('source_memo', 'AN', 'Source / Internal Memo / Exception Rationale'),
    F('closure_reason', 'AO', 'Closure / Removal Reason', INPUT, TEXT, L.CLOSURE_REASON),
    F('closed_by', 'AP', 'Closed By'),
    F('closed_date', 'AQ', 'Closed Date', INPUT, DATE),
)

TABLES = {t.name: t for t in (ALLOCATION, CONVICTION, PEW004, EVIDENCE, MIAR, REVIEWS, MASR, PIPELINE)}

# Primary key used to address a record from the command line.
KEYS = {
    'portfolio': 'symbol',
    'conviction': 'symbol',
    'pew004': 'candidate_id',
    'evidence': 'evidence_id',
    'miar': 'ticker',
    'review': 'review_id',
    'masr': 'ticker',
    'pipeline': 'candidate_id',
}

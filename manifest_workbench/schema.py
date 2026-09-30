"""Field schema for every workbench table.

Each table mirrors one worksheet of the Manifest Workbench v0.4. Fields keep the
worksheet column letter so users can refer to a field either by its key
(``market_cap``) or by its spreadsheet column (``T``).

Field kinds follow the workbook colour convention:

* ``input``  -- blue text / yellow fill: operator-maintained input.
* ``auto``   -- black text: formula / calculated output. Never stored.
* ``link``   -- green text: linked from another worksheet. Never stored.
* ``locked`` -- certified MFPDF data. Stored, but may not be edited.

Table modes describe how records are addressed:

* ``positional`` -- one row per certified holding, addressed by symbol.
* ``register``   -- append-only controlled register (RCC), addressed by record ID.
* ``slots``      -- fixed-capacity operating list; rows can be added and cleared.
* ``fixed``      -- fixed rows with locked identities (mandate controls, sleeves ...).
* ``single``     -- one record of named cells (dashboard controls, scenario header).
  For single tables ``Field.col`` holds the cell reference (``B6``).
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
    mode: str = 'register'
    key: str = ''
    title: str = ''

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


def _t(name, sheet, first_row, capacity, *fields, mode='register', key='', title=''):
    return Table(name, sheet, first_row, capacity, tuple(fields), mode, key, title)


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
    mode='positional', key='symbol', title='Certified MFPDF allocation',
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
    mode='positional', key='symbol', title='PEW-005 conviction & thesis control',
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
    mode='fixed', key='candidate_id', title='PEW-004 candidate comparison',
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
    mode='register', key='evidence_id', title='RCC-002 evidence ledger',
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
    mode='positional', key='ticker', title='RCC-003 MIAR dossier registry',
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
    mode='register', key='review_id', title='RCC-003 MIAR review log',
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
    mode='register', key='ticker', title='RCC-004 MASR registry',
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
    mode='register', key='candidate_id', title='RCC-004 candidate pipeline',
)

# =========================================================================== CISC-001

CONTROLS = _t(
    'controls', '01 Dashboard Controls', 6, 1,
    F('report_date', 'B6', 'Report Date', INPUT, DATE),
    F('console_id', 'B7', 'Console ID', LOCKED),
    F('edition', 'B8', 'Edition', LOCKED),
    F('data_status', 'B9', 'Data Status'),
    F('previous_week_score', 'B10', 'Previous Week Score', INPUT, NUMBER),
    F('confidence', 'B11', 'Confidence', INPUT, PERCENT),
    F('next_review', 'B12', 'Next Review', INPUT, DATE),
    F('mwir_status', 'B13', 'MWIR Status'),
    F('weight_total', 'C24', 'Composite Weight Total', AUTO, PERCENT),
    F('composite_score', 'B27', 'Composite Alignment Score', AUTO, NUMBER),
    F('weekly_change', 'B28', 'Weekly Change', AUTO, NUMBER),
    F('posture', 'B29', 'Current Posture', AUTO),
    F('compass_bias', 'B30', 'Compass Bias', AUTO),
    F('classification', 'B31', 'Score Classification', AUTO),
    F('prototype_note', 'B32', 'Prototype Note'),
    mode='single', title='CISC-001 dashboard controls (weekly operating inputs)',
)

COMPOSITE = _t(
    'composite', '01 Dashboard Controls', 16, 8,
    F('component', 'A', 'Composite Component', LOCKED),
    F('score', 'B', 'Score (-1 to +1)', INPUT, NUMBER),
    F('weight', 'C', 'Weight', INPUT, PERCENT),
    F('contribution', 'D', 'Contribution', AUTO, NUMBER),
    mode='fixed', key='component', title='Composite alignment components',
)

INTEL_REVIEW = _t(
    'intel-review', '03 Research Intelligence', 7, 8,
    F('symbol', 'A', 'Symbol'),
    F('company', 'B', 'Company'),
    F('reason', 'C', 'Reason'),
    F('trigger', 'D', 'Trigger'),
    F('priority', 'E', 'Priority', INPUT, TEXT, L.PRIORITY),
    F('due_date', 'F', 'Due Date', INPUT, DATE),
    F('status', 'G', 'Status', INPUT, TEXT, L.REVIEW_QUEUE_STATUS),
    mode='slots', key='symbol', title='Research intelligence: companies requiring review',
)
INTEL_EVENTS = _t(
    'intel-events', '03 Research Intelligence', 19, 8,
    F('date', 'A', 'Date', INPUT, DATE),
    F('symbol', 'B', 'Symbol'),
    F('company', 'C', 'Company'),
    F('event', 'D', 'Event'),
    F('status', 'E', 'Status', INPUT, TEXT, L.EVENT_STATUS),
    mode='slots', key='symbol', title='Research intelligence: earnings / event calendar',
)
INTEL_ZACKS = _t(
    'intel-zacks', '03 Research Intelligence', 31, 8,
    F('date', 'A', 'Date', INPUT, DATE),
    F('symbol', 'B', 'Symbol'),
    F('prior_rank', 'C', 'Prior Rank', INPUT, INT, L.ZACKS_RANK),
    F('current_rank', 'D', 'Current Rank', INPUT, INT, L.ZACKS_RANK),
    F('direction', 'E', 'Direction', INPUT, TEXT, L.ZACKS_DIRECTION),
    F('notes', 'F', 'Notes'),
    mode='slots', key='symbol', title='Research intelligence: Zacks Rank changes',
)
INTEL_MERRILL = _t(
    'intel-merrill', '03 Research Intelligence', 43, 8,
    F('date', 'A', 'Date', INPUT, DATE),
    F('symbol', 'B', 'Symbol'),
    F('rating_action', 'C', 'Rating / Action'),
    F('price_target_change', 'D', 'Price Target Change'),
    F('thesis_impact', 'E', 'Thesis Impact'),
    F('source_ref', 'F', 'Source Reference'),
    F('status', 'G', 'Status', INPUT, TEXT, L.MERRILL_UPDATE_STATUS),
    mode='slots', key='symbol', title='Research intelligence: Merrill research updates',
)
INTEL_MIAR = _t(
    'intel-miar', '03 Research Intelligence', 55, 8,
    F('symbol', 'A', 'Symbol'),
    F('review_type', 'B', 'Review Type'),
    F('last_updated', 'C', 'Last Updated', INPUT, DATE),
    F('due_date', 'D', 'Due Date', INPUT, DATE),
    F('owner', 'E', 'Owner'),
    F('status', 'F', 'Status', INPUT, TEXT, L.MIAR_UPDATE_STATUS),
    mode='slots', key='symbol', title='Research intelligence: MIAR updates',
)
INTEL_THESIS = _t(
    'intel-thesis', '03 Research Intelligence', 67, 8,
    F('symbol', 'A', 'Symbol'),
    F('current_conviction', 'B', 'Current Conviction'),
    F('proposed_conviction', 'C', 'Proposed Conviction'),
    F('reason', 'D', 'Reason'),
    F('due_date', 'E', 'Due Date', INPUT, DATE),
    F('authority', 'F', 'Authority'),
    F('status', 'G', 'Status', INPUT, TEXT, L.REVIEW_QUEUE_STATUS),
    mode='slots', key='symbol', title='Research intelligence: thesis / conviction reviews',
)

ACTIONS = _t(
    'actions', '04 Committee Operations', 7, 14,
    F('id', 'A', 'ID'),
    F('category', 'B', 'Category'),
    F('action', 'C', 'Action'),
    F('owner', 'D', 'Owner'),
    F('due_date', 'E', 'Due Date', INPUT, DATE),
    F('priority', 'F', 'Priority', INPUT, TEXT, L.PRIORITY),
    F('status', 'G', 'Status', INPUT, TEXT, L.ACTION_STATUS),
    F('committee_decision', 'H', 'Requires Committee Decision?', INPUT, TEXT, L.YES_NO),
    F('linked_record', 'I', 'Linked Record'),
    mode='slots', key='id', title='Committee operations: action register',
)
PRIORITIES = _t(
    'priorities', '04 Committee Operations', 8, 10,
    F('number', 'J', 'No.'),
    F('priority', 'K', "This Week's Priority"),
    F('owner', 'L', 'Owner'),
    F('due_date', 'M', 'Due Date', INPUT, DATE),
    F('status', 'N', 'Status'),
    mode='slots', key='number', title="Steward's notebook: this week's priorities",
)
QUESTIONS = _t(
    'questions', '04 Committee Operations', 21, 10,
    F('id', 'J', 'ID'),
    F('question', 'K', 'Question for Committee'),
    F('evidence', 'L', 'Evidence'),
    F('owner', 'M', 'Owner'),
    F('status', 'N', 'Status'),
    mode='slots', key='id', title="Steward's notebook: questions for committee",
)
PROJECTS = _t(
    'projects', '04 Committee Operations', 34, 10,
    F('id', 'J', 'ID'),
    F('project', 'K', 'Long-Term Project'),
    F('owner', 'L', 'Owner'),
    F('deliverable', 'M', 'Deliverable'),
    F('status', 'N', 'Status'),
    mode='slots', key='id', title="Steward's notebook: long-term projects",
)
PUBLICATIONS = _t(
    'publications', '04 Committee Operations', 25, 8,
    F('publication', 'A', 'Publication'),
    F('latest_issue', 'B', 'Latest Issue'),
    F('last_published', 'C', 'Last Published', INPUT, DATE),
    F('next_due', 'D', 'Next Due', INPUT, DATE),
    F('status', 'E', 'Status', INPUT, TEXT, L.PUBLICATION_STATUS),
    F('owner', 'F', 'Owner'),
    mode='slots', key='publication', title='Committee operations: publication status',
)
CALENDAR = _t(
    'calendar', '04 Committee Operations', 37, 12,
    F('date', 'A', 'Date', INPUT, DATE),
    F('event', 'B', 'Event'),
    F('cadence', 'C', 'Cadence'),
    F('authority', 'D', 'Authority'),
    F('status', 'E', 'Status'),
    mode='slots', key='event', title='Committee operations: operational calendar',
)
CERTIFICATIONS = _t(
    'certifications', '04 Committee Operations', 51, 12,
    F('record', 'A', 'Record'),
    F('version', 'B', 'Version'),
    F('certified', 'C', 'Certified / Frozen', INPUT, DATE),
    F('review_cadence', 'D', 'Review Cadence'),
    F('status', 'E', 'Status'),
    F('authority', 'F', 'Authority'),
    mode='slots', key='record', title='Committee operations: certification register',
)

DECISIONS = _t(
    'decisions', '02 Decision Center', 28, 20,
    F('id', 'A', 'ID'),
    F('date_opened', 'B', 'Date Opened', INPUT, DATE),
    F('category', 'C', 'Category'),
    F('decision', 'D', 'Decision'),
    F('evidence', 'E', 'Evidence'),
    F('recommendation', 'F', 'Recommendation'),
    F('authority', 'G', 'Authority'),
    F('owner', 'H', 'Owner'),
    F('due_date', 'I', 'Due Date', INPUT, DATE),
    F('committee_decision', 'J', 'Requires Committee Decision?', INPUT, TEXT, L.YES_NO),
    F('status', 'K', 'Status', INPUT, TEXT, L.DECISION_STATUS),
    mode='slots', key='id', title='Decision Center: manual decision register',
)

# =========================================================================== MOPS-002 PEW

MANDATE = _t(
    'mandate', '07 Mandate & Constraints', 6, 28,
    F('control_id', 'A', 'Control ID', LOCKED),
    F('domain', 'B', 'Domain', LOCKED),
    F('objective', 'C', 'Objective / Constraint', LOCKED),
    F('standard', 'D', 'Adopted Standard', LOCKED),
    F('classification', 'E', 'Classification', LOCKED, TEXT, L.CONSTRAINT_TYPE),
    F('operating_value', 'F', 'Operating Value / Current State'),
    F('test', 'G', 'Test / Trigger', LOCKED),
    F('status', 'H', 'Status'),
    F('authority', 'I', 'Authority', LOCKED),
    F('effect', 'J', 'Engineering Effect', LOCKED),
    F('notes', 'K', 'Notes / Source'),
    mode='fixed', key='control_id', title='PEW-001 mandate & constraints register',
)
# Mandate rows whose value and status are formulas (PEW-001-09..12, 25, 26).
MANDATE_FORMULA_ROWS = ('PEW-001-09', 'PEW-001-10', 'PEW-001-11', 'PEW-001-12', 'PEW-001-25',
                        'PEW-001-26')

SLEEVES = _t(
    'sleeves', '08 Sleeve Architecture', 5, 8,
    F('sleeve', 'A', 'Production Sleeve', LOCKED),
    F('purpose', 'B', 'Institutional Purpose', LOCKED),
    F('positions', 'C', 'Positions', LINK, INT),
    F('equities', 'D', 'Equities', LINK, INT),
    F('etfs', 'E', 'ETFs', LINK, INT),
    F('certified_target', 'F', 'Certified Target', LINK, PERCENT),
    F('actual', 'G', 'Actual Allocation', AUTO, PERCENT),
    F('scenario', 'H', 'Scenario Allocation', AUTO, PERCENT),
    F('delta', 'I', 'Scenario Delta', AUTO, PERCENT),
    F('range_low', 'J', 'Planning Range Low', AUTO, PERCENT),
    F('range_high', 'K', 'Planning Range High', AUTO, PERCENT),
    F('role_control', 'L', 'Role Control', AUTO),
    F('conviction_assigned', 'M', 'Conviction Assigned', AUTO, INT),
    F('conviction_completeness', 'N', 'Conviction Completeness', AUTO, PERCENT),
    F('decision_state', 'O', 'Sleeve Decision State', AUTO),
    F('committee_note', 'P', 'Committee Note'),
    mode='fixed', key='sleeve', title='PEW-002 sleeve architecture',
)

ROLES = _t(
    'roles', '09 Role Assignment', 5, 47,
    F('sleeve', 'A', 'Production Sleeve', LINK),
    F('symbol', 'B', 'Symbol', LINK),
    F('security', 'C', 'Security', LINK),
    F('security_type', 'D', 'Type', LINK),
    F('certified_role', 'E', 'Certified Portfolio Role', LINK),
    F('functional_role', 'F', 'Functional Role', INPUT, TEXT, L.FUNCTIONAL_ROLE),
    F('role_priority', 'G', 'Role Priority', INPUT, TEXT, L.ROLE_PRIORITY),
    F('core_eligibility', 'H', 'Core Eligibility', INPUT, TEXT, L.CORE_ELIGIBILITY),
    F('five_year_evidence', 'I', 'Five-Year Evidence Status', INPUT, TEXT, L.FIVE_YEAR_EVIDENCE),
    F('thesis_horizon', 'J', 'Thesis Horizon', INPUT, TEXT, L.HOLDING_PERIOD),
    F('duplication_risk', 'K', 'Duplication Risk', INPUT, TEXT, L.RISK_CLASS),
    F('complementarity', 'L', 'Complementarity Score (1–5)', INPUT, INT, (1, 2, 3, 4, 5)),
    F('role_decision', 'M', 'Role Decision', INPUT, TEXT, L.ROLE_DECISION),
    F('notes', 'N', 'Role / Replacement Notes'),
    F('control_status', 'O', 'Control Status', AUTO),
    mode='positional', key='symbol', title='PEW-003 portfolio role assignment',
)

LAB = _t(
    'lab', '12 Allocation Lab', 4, 1,
    F('scenario_id', 'B4', 'Scenario ID'),
    F('scenario_name', 'E4', 'Scenario Name'),
    F('prepared_date', 'J4', 'Prepared Date', INPUT, DATE),
    F('scenario_status', 'M4', 'Scenario Status', AUTO),
    F('certified_total', 'B6', 'Certified Total', AUTO, PERCENT),
    F('scenario_total', 'E6', 'Scenario Total', AUTO, PERCENT),
    F('funding_balance', 'H6', 'Funding Balance', AUTO, PERCENT),
    F('changed_positions', 'K6', 'Changed Positions', AUTO, INT),
    F('gross_turnover', 'N6', 'Gross Turnover', AUTO, PERCENT),
    F('band_exceptions', 'Q6', 'Band Exceptions', AUTO, INT),
    F('actual_total', 'B7', 'Current Actual Total', AUTO, PERCENT),
    F('actual_loaded', 'E7', 'Actual Weights Loaded', AUTO),
    F('readiness', 'H7', 'Implementation Readiness', AUTO),
    mode='single', title='PEW-006 allocation lab scenario',
)

SCENARIO = _t(
    'scenario', '12 Allocation Lab', 11, 47,
    F('sleeve', 'A', 'Production Sleeve', LINK),
    F('symbol', 'B', 'Symbol', LINK),
    F('security', 'C', 'Security', LINK),
    F('security_type', 'D', 'Type', LINK),
    F('role', 'E', 'Certified Portfolio Role', LINK),
    F('certified_target', 'F', 'Certified Target', LINK, PERCENT),
    F('lower_band', 'G', 'Lower Band', LINK, PERCENT),
    F('upper_band', 'H', 'Upper Band', LINK, PERCENT),
    F('actual_weight', 'I', 'Actual Weight', LINK, PERCENT),
    F('scenario_weight', 'J', 'Scenario Weight Input', INPUT, PERCENT),
    F('effective_weight', 'K', 'Effective Scenario Weight', AUTO, PERCENT),
    F('change', 'L', 'Change vs Certified', AUTO, PERCENT),
    F('funding', 'M', 'Funding / Use', AUTO),
    F('band_test', 'N', 'Certified Band Test', AUTO),
    F('trigger', 'O', 'Decision Trigger', AUTO),
    F('rationale', 'P', 'Committee Rationale'),
    F('validation_state', 'Q', 'Validation State', AUTO),
    F('abs_change', 'R', 'Absolute Change', AUTO, PERCENT),
    mode='positional', key='symbol', title='PEW-006 scenario allocation schedule',
)

CERTIFICATION = _t(
    'validation', '13 Validation & Cert', 6, 1,
    F('turnover_threshold', 'B6', 'Gross turnover materiality threshold', INPUT, PERCENT),
    F('position_threshold', 'B7', 'Single-position materiality threshold', INPUT, PERCENT),
    F('sleeve_threshold', 'B8', 'Sleeve-shift materiality threshold', INPUT, PERCENT),
    F('total_tolerance', 'B9', 'Target-total tolerance', INPUT, NUMBER),
    F('equity_min', 'B10', 'Preferred equity minimum', INPUT, INT),
    F('equity_max', 'B11', 'Preferred equity maximum', INPUT, INT),
    F('equity_ceiling', 'B12', 'Operating equity ceiling', INPUT, INT),
    F('overall_readiness', 'J12', 'Overall Readiness', AUTO),
    F('proposed_version', 'J38', 'Proposed MFPDF Version'),
    F('effective_date', 'K38', 'Effective Date', INPUT, DATE),
    F('certification_state', 'L38', 'Certification State', AUTO),
    mode='single', title='PEW-007 validation controls and certification state',
)

WORKFLOW = _t(
    'workflow', '13 Validation & Cert', 38, 7,
    F('stage', 'A', 'Review Stage', LOCKED),
    F('status', 'B', 'Status', INPUT, TEXT, L.CERTIFICATION_STATUS),
    F('reviewed_by', 'C', 'Reviewed By'),
    F('review_date', 'D', 'Review Date', INPUT, DATE),
    F('evidence_ref', 'E', 'Evidence Reference'),
    F('notes', 'F', 'Decision / Notes'),
    F('blocking', 'G', 'Blocking?', LOCKED),
    mode='fixed', key='stage', title='PEW-007 formal certification workflow',
)

CHANGES = _t(
    'changes', '13 Validation & Cert', 49, 10,
    F('change_id', 'A', 'Change ID', LOCKED),
    F('symbol_sleeve', 'B', 'Symbol / Sleeve'),
    F('change_type', 'C', 'Change Type', INPUT, TEXT, L.CHANGE_TYPE),
    F('certified_weight', 'D', 'Certified Weight', INPUT, PERCENT),
    F('proposed_weight', 'E', 'Proposed Weight', INPUT, PERCENT),
    F('delta', 'F', 'Delta', AUTO, PERCENT),
    F('rationale', 'G', 'Rationale / Evidence'),
    F('outcome', 'H', 'Certification Outcome', INPUT, TEXT, L.CHANGE_OUTCOME),
    mode='fixed', key='change_id', title='PEW-007 certification change register',
)

TABLES = {t.name: t for t in (
    ALLOCATION, CONVICTION, PEW004, EVIDENCE, MIAR, REVIEWS, MASR, PIPELINE,
    CONTROLS, COMPOSITE, INTEL_REVIEW, INTEL_EVENTS, INTEL_ZACKS, INTEL_MERRILL, INTEL_MIAR,
    INTEL_THESIS, ACTIONS, PRIORITIES, QUESTIONS, PROJECTS, PUBLICATIONS, CALENDAR,
    CERTIFICATIONS, DECISIONS, MANDATE, SLEEVES, ROLES, LAB, SCENARIO, CERTIFICATION, WORKFLOW,
    CHANGES)}
INTEL_TABLES = ('intel-review', 'intel-events', 'intel-zacks', 'intel-merrill', 'intel-miar',
                'intel-thesis')
COMMITTEE_TABLES = ('actions', 'priorities', 'questions', 'projects', 'publications', 'calendar',
                    'certifications')

# Primary key used to address a record from the command line.
KEYS = {t.name: t.key for t in TABLES.values() if t.key}

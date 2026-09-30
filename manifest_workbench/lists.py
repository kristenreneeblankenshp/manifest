"""Controlled validation lists.

Transcribed from the "97 RCC Lists" and "98 PEW Lists" sheets and the data-validation
rules of the Manifest Workbench v0.4. Do not modify without a documented MOPS-003
amendment.
"""
from __future__ import annotations

# 97 RCC Lists, column A: Record Type
RECORD_TYPE = (
    'Certified Holding',
    'MASR Non-Holding',
    'Research Candidate',
    'Portfolio-Level',
    'Market / Macro',
    'Other',
)

# 97 RCC Lists, column B: Activity Type
ACTIVITY_TYPE = (
    'Company Review',
    'Earnings / Guidance',
    'Material Corporate Event',
    'Zacks Rank Change',
    'Merrill Research Update',
    'MIAR Update',
    'Thesis / Conviction Review',
    'MASR Candidate',
    'Replacement Candidate',
    'Regulatory / Legal',
    'Capital Allocation / Dividend',
    'Other Research Signal',
)

# 97 RCC Lists, column C: Evidence Category
EVIDENCE_CATEGORY = (
    'Earnings and Guidance',
    'Revenue and Margin',
    'Balance Sheet / Credit',
    'Capital Allocation',
    'Management / Governance',
    'Competitive Position',
    'Product / Technology',
    'Regulatory / Legal',
    'Valuation',
    'Dividend / Income',
    'M&A / Divestiture',
    'Market / Industry',
    'Portfolio Concentration',
    'Correlation / Diversification',
    'External Rating / Ranking',
    'Other',
)

# 97 RCC Lists, column D: Materiality
MATERIALITY = (
    'Critical',
    'High',
    'Moderate',
    'Low',
)

# 97 RCC Lists, column E: Direction
DIRECTION = (
    'Positive',
    'Neutral',
    'Negative',
    'Mixed',
    'Unclear',
)

# 97 RCC Lists, column F: Reliability
RELIABILITY = (
    'Primary — Verified',
    'Secondary — Verified',
    'Internal Analysis',
    'Unverified — Pending',
    'Exception Approved',
)

# 97 RCC Lists, column G: Source Type
SOURCE_TYPE = (
    'Company Filing',
    'Earnings Release',
    'Company Presentation',
    'Earnings / Investor Call',
    'Merrill Research',
    'Zacks Rank',
    'Rating Agency',
    'Government / Regulator',
    'Industry Data',
    'News / Media',
    'Internal Analysis',
    'Other',
)

# 97 RCC Lists, column H: Thesis Sensitivity
THESIS_SENSITIVITY = (
    'High',
    'Medium',
    'Low',
    'Not Assessed',
)

# 97 RCC Lists, column I: Status
EVIDENCE_STATUS = (
    'New',
    'Under Review',
    'Awaiting Verification',
    'Escalated',
    'Referred to MIAR',
    'Referred to Thesis / Conviction',
    'Referred to Candidate Review',
    'Referred to Portfolio Engineering',
    'Closed — No Action',
    'Closed — Incorporated',
)

# 97 RCC Lists, column J: Verification
VERIFICATION = (
    'Yes',
    'No',
    'Exception Approved',
)

# 97 RCC Lists, column K: MIAR Action
MIAR_ACTION = (
    'None',
    'Incremental Update',
    'Full Review',
    'Material Event Review',
)

# 97 RCC Lists, column L: Thesis Impact
THESIS_IMPACT = (
    'None',
    'Strengthening',
    'Intact',
    'Under Review',
    'Weakening',
    'Impaired',
    'Broken',
)

# 97 RCC Lists, column M: Conviction Recommendation
CONVICTION_RECOMMENDATION = (
    'No Change',
    'Increase',
    'Reduce',
    'Watch',
    'Initiate Replacement Review',
    'Unassigned',
    'Not Applicable',
)

# 97 RCC Lists, column N: Candidate / Replacement
CANDIDATE_REPLACEMENT = (
    'None',
    'Candidate Review',
    'Replacement Review',
    'MASR Addition Review',
    'MASR Removal Review',
)

# 97 RCC Lists, column O: PEW Referral
PEW_REFERRAL = (
    'No',
    'Yes — PEW-003 Role',
    'Yes — PEW-004 Candidate',
    'Yes — PEW-005 Conviction',
    'Yes — PEW-006 Allocation',
    'Yes — PEW-007 Certification',
)

# 97 RCC Lists, column P: Disposition
DISPOSITION = (
    'Pending',
    'No Action',
    'MIAR Updated',
    'Thesis Updated',
    'Conviction Updated',
    'Candidate Advanced',
    'Candidate Rejected',
    'Referred to PEW',
    'Committee Review Required',
    'Closed',
)

# 97 RCC Lists, column Q: MIAR Record Status
MIAR_RECORD_STATUS = (
    'Not Initiated',
    'Draft',
    'Active',
    'Update Due',
    'Review Due',
    'Material Event Review',
    'Suspended',
    'Archived',
)

# 97 RCC Lists, column R: Review Cadence
REVIEW_CADENCE = (
    'Quarterly — 90 Days',
    'Semiannual — 180 Days',
    'Annual — 365 Days',
    'Event-Driven',
)

# 97 RCC Lists, column S: MIAR Review Type
MIAR_REVIEW_TYPE = (
    'Full Review',
    'Incremental Update',
    'Material Event Review',
    'Certification Review',
)

# 97 RCC Lists, column T: Thesis Assessment
THESIS_ASSESSMENT = (
    'Strengthening',
    'Intact',
    'Under Review',
    'Weakening',
    'Impaired',
    'Broken',
    'Not Assessed',
)

# 97 RCC Lists, column U: Certification Recommendation
CERTIFICATION_RECOMMENDATION = (
    'Certify Current',
    'Certify with Exception',
    'Return for Revision',
    'Escalate to RCC-007',
    'No Certification',
)

# 97 RCC Lists, column V: RCC-007 Referral State
RCC007_REFERRAL_STATE = (
    'No Referral',
    'Refer to RCC-007',
    'Hold Pending MIAR Update',
)

# 97 RCC Lists, column W: MIAR Control Status
MIAR_CONTROL_STATUS = (
    'CONTROL CLEAR',
    'INCOMPLETE',
    'DUPLICATE MIAR ID',
    'CERTIFICATION REQUIRED',
    'DRAFT — NOT CERTIFIED',
    'THESIS / CONVICTION SETUP',
    'MIAR ACTION PENDING',
    'MATERIAL EVENT REVIEW',
    'REVIEW DUE',
    'OVERDUE',
)

# 97 RCC Lists, column X: Research Freshness
RESEARCH_FRESHNESS = (
    'CURRENT',
    'UPDATE DUE',
    'REVIEW DUE',
    'OVERDUE',
    'MATERIAL EVENT REVIEW',
    'NOT INITIALIZED',
    'INACTIVE',
)

# 97 RCC Lists, column Y: Required MIAR Action
REQUIRED_MIAR_ACTION = (
    'Maintain scheduled cadence',
    'Complete MIAR setup',
    'Assign unique canonical MIAR ID',
    'Enter certifier and certification date',
    'Complete certification review',
    'Complete thesis and conviction prerequisites',
    'Resolve RCC-002 MIAR referrals',
    'Complete material-event dossier review',
    'Schedule and complete dossier review',
    'Complete overdue full review',
)

# 97 RCC Lists, column Z: MASR Record Class
MASR_RECORD_CLASS = (
    'Certified Portfolio Holding',
    'MASR Approved Non-Holding',
    'Conditional Candidate',
    'Research Candidate',
    'Replacement Candidate',
    'Rejected Candidate',
    'Removed Security',
    'Archived Record',
)

# 97 RCC Lists, column AA: MASR Registry Status
MASR_REGISTRY_STATUS = (
    'Active — Certified Holding',
    'Active — Approved Non-Holding',
    'Conditional',
    'Candidate — Under Research',
    'Candidate — Committee Review',
    'Suspended',
    'Rejected',
    'Removed',
    'Archived',
)

# 97 RCC Lists, column AB: Admission Basis
ADMISSION_BASIS = (
    'Certified MFPDF / Founders Edition',
    'Manifest Research',
    'Empirical Screen',
    'Zacks Election',
    'Merrill Commonality',
    'Replacement Review',
    'Committee Referral',
    'Advisor Observation',
    'Other',
)

# 97 RCC Lists, column AC: Candidate Type
CANDIDATE_TYPE = (
    'New Candidate',
    'Replacement Candidate',
    'Retention Review',
    'MASR Addition Review',
    'MASR Removal Review',
    'Conditional Candidate',
    'Reinstatement Review',
    'Research Candidate',
)

# 97 RCC Lists, column AD: Candidate Stage
CANDIDATE_STAGE = (
    'Intake',
    'Evidence Gathering',
    'MIAR Review',
    'Eligibility Review',
    'Candidate Comparison',
    'Committee Review',
    'Approved for MASR',
    'Referred to PEW-004',
    'On Watch',
    'Rejected',
    'Closed',
    'Removed',
)

# 97 RCC Lists, column AE: Eligibility Gate
ELIGIBILITY_GATE = (
    'CERTIFIED HOLDING',
    'ELIGIBLE',
    'ELIGIBLE WITH EXCEPTION',
    'NOT ELIGIBLE',
    'NOT ASSESSED',
)

# 97 RCC Lists, column AF: Merrill Status
MERRILL_STATUS = (
    'Buy',
    'Neutral',
    'Underperform',
    'No Rating',
    'Restricted / Unavailable',
    'Not Reviewed',
)

# 97 RCC Lists, column AG: Candidate Source / Referral
CANDIDATE_SOURCE = (
    'RCC-002 Evidence Referral',
    'RCC-003 MIAR Referral',
    'RCC-007 Thesis / Conviction Referral',
    'Committee Referral',
    'PEW Replacement Need',
    'Empirical Screen',
    'Zacks Screen',
    'Merrill Research',
    'Advisor Observation',
    'Other',
)

# 97 RCC Lists, column AH: Committee Disposition
COMMITTEE_DISPOSITION = (
    'Pending',
    'Approve MASR Admission',
    'Approve Conditional Admission',
    'Advance to PEW-004',
    'Retain on Watch',
    'Reject Candidate',
    'Remove from MASR',
    'Defer',
    'No Action',
    'Grandfathered — Certified Holding',
    'Exception Approved',
)

# 97 RCC Lists, column AI: PEW Referral State
PEW_REFERRAL_STATE = (
    'No',
    'Yes — Refer to PEW-004',
    'Referred — Pending PEW Record',
    'Referred — PEW Record Linked',
)

# 97 RCC Lists, column AJ: MASR Control Status
MASR_CONTROL_STATUS = (
    'SETUP REQUIRED',
    'DUPLICATE MASR ID',
    'DUPLICATE TICKER',
    'INCOMPLETE',
    'MIAR SETUP REQUIRED',
    'NOT ELIGIBLE',
    'EXCEPTION REVIEW',
    'COMMITTEE DISPOSITION REQUIRED',
    'CERTIFICATION REQUIRED',
    'CONTROL CLEAR',
    'INACTIVE / CLOSED',
)

# 97 RCC Lists, column AK: Required MASR Action
REQUIRED_MASR_ACTION = (
    'Assign canonical MASR ID and complete registry setup',
    'Resolve duplicate canonical MASR identifier',
    'Resolve duplicate active ticker record',
    'Complete required registry classification and role fields',
    'Complete RCC-003 MIAR identity and dossier controls',
    'Resolve eligibility failure or reject / archive record',
    'Document and approve all eligibility exceptions',
    'Record committee disposition and review date',
    'Record approval authority and review date',
    'Maintain current registry record',
    'Retain auditable archive; no active admission authority',
)

# 97 RCC Lists, column AL: Candidate Control Status
CANDIDATE_CONTROL_STATUS = (
    'INCOMPLETE',
    'DUPLICATE CANDIDATE ID',
    'MASR RECORD REQUIRED',
    'ELIGIBILITY BLOCK',
    'EVIDENCE REQUIRED',
    'MIAR GATE BLOCK',
    'COMMITTEE DECISION REQUIRED',
    'PEW REFERRAL INCOMPLETE',
    'CLOSURE REQUIRED',
    'OVERDUE',
    'OPEN — ON TRACK',
    'CLOSED',
)

# 97 RCC Lists, column AM: Required Candidate Action
REQUIRED_CANDIDATE_ACTION = (
    'Complete required candidate intake fields',
    'Resolve duplicate candidate identifier',
    'Create or reconcile the RCC-004 MASR registry record',
    'Resolve eligibility gate or close candidate',
    'Add verified RCC-002 evidence before advancement',
    'Complete RCC-003 dossier and research-freshness controls',
    'Record formal committee disposition',
    'Complete PEW-004 referral and candidate linkage',
    'Record closure authority, date and rationale',
    'Complete or formally extend the overdue review',
    'Continue current stage and meet due date',
    'Retain final evidence and disposition record',
)

# 97 RCC Lists, column AN: Closure / Removal Reason
CLOSURE_REASON = (
    'Approved / Advanced',
    'Rejected — Evidence',
    'Rejected — Eligibility',
    'Rejected — Role Fit',
    'Rejected — Valuation',
    'Removed — Thesis Impaired',
    'Removed — Better Replacement',
    'Closed — No Action',
    'Deferred / Watch',
)

# 97 RCC Lists, column AO: Security Type
SECURITY_TYPE = (
    'Equity',
    'ETF',
    'Other',
)

# 98 PEW Lists / Certified Allocation / PEW-004 / PEW-005 data validations
SLEEVES = (
    'Strategic Anchors',
    'Growth Compounders',
    'Digital Infrastructure & AI',
    'Industrials & Infrastructure',
    'Financial Infrastructure',
    'Healthcare Leadership',
    'Energy & Natural Resources',
    'Income & Risk Management',
)

ZACKS_RANK = (1, 2, 3, 4, 5)

# Certified Allocation M / N
MFPDF_CONVICTION_TIER = ('Tier 1', 'Tier 2', 'Tier 3', 'Unassigned')
MFPDF_RESEARCH_STATUS = ('Current', 'Review Due', 'Decision Required', 'Suspended')

# 11 Conviction G / J / L / M
CONVICTION_TIER = ('Tier 1 — Anchor', 'Tier 2 — Core', 'Tier 3 — Opportunistic', 'Unassigned')
THESIS_STATUS = ('Current', 'Watch', 'Review Due', 'Impaired')
RISK_CLASS = ('Low', 'Moderate', 'High', 'Not Assessed')
HOLDING_PERIOD = ('1–3 years', '3–5 years', '5+ years', 'Tactical / event driven')

# 10 Candidate Comparison C / G / I / R / W
PEW_CANDIDATE_TYPE = ('Incumbent', 'Candidate')
FUNCTIONAL_ROLE = (
    'Constitutional Anchor',
    'Core Compounder',
    'Growth Engine',
    'Infrastructure Enabler',
    'Quality Financial',
    'Defensive Healthcare',
    'Resource Exposure',
    'Income Generator',
    'Volatility Moderator',
    'Diversifier',
)
PEW_MERRILL_STATUS = ('Buy', 'Neutral', 'Underperform', 'No Rating', 'Not Checked')
YES_NO = ('Yes', 'No')
PEW_COMMITTEE_DECISION = ('Approve', 'Reject', 'Defer', 'Exception Approved', 'No Decision')

# 98 PEW Lists (remaining columns) and data validation on the PEW / CISC sheets
CONSTRAINT_TYPE = ('Hard Constraint', 'Soft Objective', 'Governance Rule', 'Preference',
                   'Monitoring Control')
ROLE_PRIORITY = ('Primary', 'Secondary', 'Implementation')
CORE_ELIGIBILITY = ('Core', 'Satellite / Implementation', 'Exception', 'Review')
FIVE_YEAR_EVIDENCE = ('Certified Baseline', 'Met', 'Not Met', 'Exception', 'Review')
ROLE_DECISION = ('Retain — Certified Baseline', 'Retain', 'Review', 'Replacement Candidate')
PEW_RESEARCH_STATUS = ('Current', 'Update Due', 'Review Due', 'Decision Required')
CERTIFICATION_STATUS = ('Pending', 'Approved', 'Rejected', 'Not Required')
SCENARIO_STATUS = ('Open', 'Ready for Validation', 'Committee Review', 'Certified', 'Rejected')
CHANGE_TYPE = ('Add', 'Remove', 'Increase', 'Decrease', 'Sleeve Reassignment', 'Role Change',
               'Conviction Change')
CHANGE_OUTCOME = ('Approved', 'Rejected', 'Deferred', 'Exception Approved', 'Pending')
PRIORITY = ('High', 'Medium', 'Low')
REVIEW_QUEUE_STATUS = ('Open', 'In Review', 'Decision Required', 'Closed')
EVENT_STATUS = ('Scheduled', 'Complete', 'Canceled')
ZACKS_DIRECTION = ('Upgrade', 'Downgrade', 'No Change')
MERRILL_UPDATE_STATUS = ('New', 'Reviewed', 'Decision Required', 'Archived')
MIAR_UPDATE_STATUS = ('Current', 'Due', 'Overdue', 'Complete')
ACTION_STATUS = ('Open', 'In Progress', 'Planned', 'Completed', 'Deferred')
PUBLICATION_STATUS = ('Not Started', 'Planned', 'Draft', 'In Review', 'Published', 'Scheduled')
DECISION_STATUS = ('Open', 'In Review', 'Closed', 'Deferred')


# Name -> values, for the `lists` command.
REGISTRY = {
    'record-type': RECORD_TYPE,
    'activity-type': ACTIVITY_TYPE,
    'evidence-category': EVIDENCE_CATEGORY,
    'materiality': MATERIALITY,
    'direction': DIRECTION,
    'reliability': RELIABILITY,
    'source-type': SOURCE_TYPE,
    'thesis-sensitivity': THESIS_SENSITIVITY,
    'evidence-status': EVIDENCE_STATUS,
    'verification': VERIFICATION,
    'miar-action': MIAR_ACTION,
    'thesis-impact': THESIS_IMPACT,
    'conviction-recommendation': CONVICTION_RECOMMENDATION,
    'candidate-replacement': CANDIDATE_REPLACEMENT,
    'pew-referral': PEW_REFERRAL,
    'disposition': DISPOSITION,
    'miar-record-status': MIAR_RECORD_STATUS,
    'review-cadence': REVIEW_CADENCE,
    'miar-review-type': MIAR_REVIEW_TYPE,
    'thesis-assessment': THESIS_ASSESSMENT,
    'certification-recommendation': CERTIFICATION_RECOMMENDATION,
    'rcc007-referral-state': RCC007_REFERRAL_STATE,
    'miar-control-status': MIAR_CONTROL_STATUS,
    'research-freshness': RESEARCH_FRESHNESS,
    'required-miar-action': REQUIRED_MIAR_ACTION,
    'masr-record-class': MASR_RECORD_CLASS,
    'masr-registry-status': MASR_REGISTRY_STATUS,
    'admission-basis': ADMISSION_BASIS,
    'candidate-type': CANDIDATE_TYPE,
    'candidate-stage': CANDIDATE_STAGE,
    'eligibility-gate': ELIGIBILITY_GATE,
    'merrill-status': MERRILL_STATUS,
    'candidate-source': CANDIDATE_SOURCE,
    'committee-disposition': COMMITTEE_DISPOSITION,
    'pew-referral-state': PEW_REFERRAL_STATE,
    'masr-control-status': MASR_CONTROL_STATUS,
    'required-masr-action': REQUIRED_MASR_ACTION,
    'candidate-control-status': CANDIDATE_CONTROL_STATUS,
    'required-candidate-action': REQUIRED_CANDIDATE_ACTION,
    'closure-reason': CLOSURE_REASON,
    'security-type': SECURITY_TYPE,
    'sleeve': SLEEVES,
    'zacks-rank': ZACKS_RANK,
    'mfpdf-conviction-tier': MFPDF_CONVICTION_TIER,
    'mfpdf-research-status': MFPDF_RESEARCH_STATUS,
    'conviction-tier': CONVICTION_TIER,
    'thesis-status': THESIS_STATUS,
    'risk-class': RISK_CLASS,
    'holding-period': HOLDING_PERIOD,
    'pew-candidate-type': PEW_CANDIDATE_TYPE,
    'functional-role': FUNCTIONAL_ROLE,
    'pew-merrill-status': PEW_MERRILL_STATUS,
    'yes-no': YES_NO,
    'pew-committee-decision': PEW_COMMITTEE_DECISION,
    'constraint-type': CONSTRAINT_TYPE,
    'role-priority': ROLE_PRIORITY,
    'core-eligibility': CORE_ELIGIBILITY,
    'five-year-evidence': FIVE_YEAR_EVIDENCE,
    'role-decision': ROLE_DECISION,
    'pew-research-status': PEW_RESEARCH_STATUS,
    'certification-status': CERTIFICATION_STATUS,
    'scenario-status': SCENARIO_STATUS,
    'change-type': CHANGE_TYPE,
    'change-outcome': CHANGE_OUTCOME,
    'priority': PRIORITY,
    'review-queue-status': REVIEW_QUEUE_STATUS,
    'event-status': EVENT_STATUS,
    'zacks-direction': ZACKS_DIRECTION,
    'merrill-update-status': MERRILL_UPDATE_STATUS,
    'miar-update-status': MIAR_UPDATE_STATUS,
    'action-status': ACTION_STATUS,
    'publication-status': PUBLICATION_STATUS,
    'decision-status': DECISION_STATUS,
}

# Status -> required action lookups (97 RCC Lists W/Y, AJ/AK, AL/AM).
MIAR_REQUIRED_ACTION = dict(zip(MIAR_CONTROL_STATUS, REQUIRED_MIAR_ACTION))
MASR_REQUIRED_ACTION = dict(zip(MASR_CONTROL_STATUS, REQUIRED_MASR_ACTION))
CANDIDATE_REQUIRED_ACTION = dict(zip(CANDIDATE_CONTROL_STATUS, REQUIRED_CANDIDATE_ACTION))

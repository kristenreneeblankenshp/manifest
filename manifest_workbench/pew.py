"""MOPS-002 Portfolio Engineering Workspace (PEW-001 through PEW-007).

Formula port of sheets 06 PEW Control Center, 07 Mandate & Constraints,
08 Sleeve Architecture, 09 Role Assignment, 12 Allocation Lab and
13 Validation & Cert. The scenario layer never writes to the certified MFPDF.
"""

from __future__ import annotations

from . import lists as L
from .engine import blank, num, same

WITHIN = 'Within Certified Band'
DEFAULT_THRESHOLDS = {'turnover_threshold': 0.1, 'position_threshold': 0.0075,
                      'sleeve_threshold': 0.02, 'total_tolerance': 1e-06, 'equity_min': 32,
                      'equity_max': 38, 'equity_ceiling': 41}


def thresholds(store) -> dict:
    t = dict(DEFAULT_THRESHOLDS)
    for k, v in store.get('certification', {}).items():
        if k in t and num(v) is not None:
            t[k] = num(v)
    return t


class PEW:
    """PEW views computed from a :class:`manifest_workbench.engine.Workbench`."""

    def __init__(self, wb):
        self.wb = wb
        self.store = wb.store
        self.t = thresholds(self.store)
        self.roles = self._roles()
        self.scenario = self._scenario()
        self.lab = self._lab()
        self.sleeves = self._sleeves()
        self.mandate = self._mandate()
        self.tests = self._tests()
        self.workflow, self.certification = self._certification()
        self.changes = self._changes()
        self.control = self._control_center()

    # ------------------------------------------------------------------ PEW-003

    def _roles(self):
        rows = []
        stored = self.store.get('roles', [])
        for pos, alloc in enumerate(self.wb.portfolio):
            r = dict(stored[pos]) if pos < len(stored) else {}
            r.update({'sleeve': alloc.get('sleeve'), 'symbol': alloc.get('symbol'),
                      'security': alloc.get('security'), 'security_type': alloc.get('security_type'),
                      'certified_role': alloc.get('role')})
            if blank(r.get('functional_role')):                                            # O
                r['control_status'] = 'ROLE REQUIRED'
            elif same(r.get('five_year_evidence'), 'Review'):
                r['control_status'] = 'EVIDENCE REVIEW'
            elif same(r.get('role_decision'), 'Replacement Candidate'):
                r['control_status'] = 'COMMITTEE REVIEW'
            else:
                r['control_status'] = 'PASS'
            rows.append(r)
        return rows

    def role_summary(self):
        return {'passed': sum(1 for r in self.roles if r['control_status'] == 'PASS'),        # F52
                'review_items': sum(1 for r in self.roles if r['control_status'] != 'PASS'),  # I52
                'replacement_candidates': sum(1 for r in self.roles                           # M52
                                              if same(r.get('role_decision'), 'Replacement Candidate'))}

    # ------------------------------------------------------------------ PEW-006

    def _scenario(self):
        tol, pos_threshold = self.t['total_tolerance'], self.t['position_threshold']
        stored = self.store.get('scenario', [])
        rows = []
        for pos, alloc in enumerate(self.wb.portfolio):
            r = dict(stored[pos]) if pos < len(stored) else {}
            f = num(alloc.get('target_weight')) or 0.0
            actual = num(alloc.get('actual_weight'))
            r.update({'sleeve': alloc.get('sleeve'), 'symbol': alloc.get('symbol'),
                      'security': alloc.get('security'), 'security_type': alloc.get('security_type'),
                      'role': alloc.get('role'), 'certified_target': f,
                      'lower_band': alloc['lower_band'], 'upper_band': alloc['upper_band'],
                      # A link to a blank actual weight displays 0 but stays blank for tests.
                      'actual_weight': 0 if actual is None else actual,
                      '_actual_blank': actual is None})
            j = num(r.get('scenario_weight'))
            k = f if j is None else j
            change = k - f
            r['effective_weight'], r['change'], r['abs_change'] = k, change, abs(change)      # K L R
            unchanged = abs(change) < tol
            r['funding'] = 'No Change' if unchanged else (                                  # M
                'Funding Required' if change > 0 else 'Source of Funds')
            if k < r['lower_band']:                                                         # N
                r['band_test'] = 'Below Certified Band'
            elif k > r['upper_band']:
                r['band_test'] = 'Above Certified Band'
            else:
                r['band_test'] = WITHIN
            if unchanged:                                                                   # O
                r['trigger'] = 'No scenario change'
            elif r['band_test'] != WITHIN:
                r['trigger'] = 'BAND EXCEPTION — COMMITTEE DECISION'
            elif abs(change) >= pos_threshold:
                r['trigger'] = 'MATERIAL POSITION CHANGE'
            else:
                r['trigger'] = 'REVIEW PROPOSED CHANGE'
            if unchanged:                                                                   # Q
                r['validation_state'] = 'Baseline'
            elif blank(r.get('rationale')):
                r['validation_state'] = 'Rationale Required'
            else:
                r['validation_state'] = 'Ready for Validation'
            rows.append(r)
        return rows

    def _lab(self):
        rows, tol = self.scenario, self.t['total_tolerance']
        header = dict(self.store.get('lab', {}))
        loaded = sum(1 for r in self.wb.portfolio if not blank(r.get('actual_weight')))
        total_k = sum(r['effective_weight'] for r in rows)
        certified = sum(r['certified_target'] for r in rows)
        changed = sum(1 for r in rows if r['change'] != 0)
        header.update({
            'certified_total': certified,                                                   # B6
            'scenario_total': total_k,                                                      # E6
            'funding_balance': total_k - certified,                                         # H6
            'changed_positions': changed,                                                   # K6
            'gross_turnover': sum(r['abs_change'] for r in rows) / 2,                       # N6
            'band_exceptions': sum(1 for r in rows if r['band_test'] != WITHIN),            # Q6
            'actual_total': sum(r['actual_weight'] for r in rows),                          # B7
            'actual_loaded': f'{loaded} / 47',                                              # E7
            'scenario_weight_total': sum(num(r.get('scenario_weight')) or 0 for r in rows),  # J58
            'change_total': sum(r['change'] for r in rows),                                 # L58
        })
        if loaded < 47:                                                                     # H7
            header['readiness'] = 'INPUT REQUIRED — LOAD ACTUAL WEIGHTS'
        elif abs(total_k - 1) > tol:
            header['readiness'] = 'REVISION REQUIRED — SCENARIO MUST TOTAL 100%'
        elif any(r['validation_state'] == 'Rationale Required' for r in rows):
            header['readiness'] = 'INPUT REQUIRED — COMPLETE RATIONALES'
        else:
            header['readiness'] = 'READY FOR VALIDATION'
        if loaded < 47:                                                                     # M4
            header['scenario_status'] = 'DATA SETUP REQUIRED'
        elif abs(total_k - 1) > tol:
            header['scenario_status'] = 'REVISION REQUIRED'
        elif changed == 0:
            header['scenario_status'] = 'BASELINE / NO CHANGE'
        else:
            header['scenario_status'] = 'COMMITTEE REVIEW REQUIRED'
        return header

    # ------------------------------------------------------------------ PEW-002

    def _sleeves(self):
        stored = {s.get('sleeve'): s for s in self.store.get('sleeves', [])}
        summary = {s['sleeve']: s for s in self.wb.sleeve_summary()}
        tol = self.t['total_tolerance']
        rows = []
        for sleeve in L.SLEEVES:
            r = dict(stored.get(sleeve, {'sleeve': sleeve}))
            ss = summary[sleeve]
            members = [x for x in self.scenario if same(x['sleeve'], sleeve)]
            r.update({'positions': ss['positions'], 'equities': ss['equities'], 'etfs': ss['etfs'],
                      'certified_target': ss['target'],
                      'actual': sum(x['actual_weight'] for x in members),                   # G
                      'scenario': sum(x['effective_weight'] for x in members)})             # H
            r['delta'] = r['scenario'] - r['certified_target']                              # I
            r['range_low'] = r['certified_target'] * 0.8                                    # J
            r['range_high'] = r['certified_target'] * 1.2                                   # K
            r['role_control'] = 'PASS' if not any(                                          # L
                x['control_status'] != 'PASS' for x in self.roles if same(x['sleeve'], sleeve)) else 'REVIEW'
            r['conviction_assigned'] = sum(                                                 # M
                1 for x in self.wb.conviction if same(x['sleeve'], sleeve)
                and not same(x['effective_conviction'], 'Unassigned'))
            r['conviction_completeness'] = (r['conviction_assigned'] / r['positions']       # N
                                            if r['positions'] else 0)
            if r['scenario'] < r['range_low'] or r['scenario'] > r['range_high']:           # O
                r['decision_state'] = 'SLEEVE REVIEW'
            elif r['conviction_completeness'] < 1:
                r['decision_state'] = 'CONVICTION INPUT REQUIRED'
            elif abs(r['delta']) < tol:
                r['decision_state'] = 'BASELINE'
            else:
                r['decision_state'] = 'REVIEW PROPOSED SHIFT'
            rows.append(r)
        return rows

    def sleeve_totals(self):
        rows = self.sleeves
        positions = sum(r['positions'] for r in rows)
        assigned = sum(r['conviction_assigned'] for r in rows)
        scenario = sum(r['scenario'] for r in rows)
        return {
            'positions': positions, 'equities': sum(r['equities'] for r in rows),
            'etfs': sum(r['etfs'] for r in rows),
            'certified_target': sum(r['certified_target'] for r in rows),
            'actual': sum(r['actual'] for r in rows), 'scenario': scenario,
            'delta': sum(r['delta'] for r in rows), 'conviction_assigned': assigned,
            'conviction_completeness': assigned / positions if positions else 0,
            'decision_state': 'SCENARIO TOTAL PASS' if abs(scenario - 1) < self.t['total_tolerance']
            else 'SCENARIO TOTAL FAIL',
        }

    # ------------------------------------------------------------------ PEW-001

    def _mandate(self):
        equities = sum(1 for r in self.wb.portfolio if same(r.get('security_type'), 'Equity'))
        positions = sum(1 for r in self.wb.portfolio if not blank(r.get('symbol')))
        target = sum(num(r.get('target_weight')) or 0 for r in self.wb.portfolio)
        loaded = sum(1 for r in self.wb.portfolio if not blank(r.get('actual_weight')))
        assigned = self.conviction_assigned()
        computed = {
            'PEW-001-09': (equities, 'PASS' if equities <= 38 else (
                'MONITOR — ABOVE PREFERRED RANGE' if equities <= 41 else 'FAIL — ABOVE OPERATING CEILING')),
            'PEW-001-10': (equities, 'PASS' if equities <= 41 else 'FAIL — ABOVE OPERATING CEILING'),
            'PEW-001-11': (positions, 'PASS' if positions == 47 else 'FAIL — DOES NOT RECONCILE'),
            'PEW-001-12': (target, 'PASS' if abs(target - 1) < 0.000001 else 'FAIL — TARGET TOTAL'),
            'PEW-001-25': (f'{loaded} / 47 loaded', 'PASS' if loaded == 47 else 'INPUT REQUIRED'),
            'PEW-001-26': (f'{assigned} / 47 assigned', 'PASS' if assigned == 47 else 'INPUT REQUIRED'),
        }
        rows = []
        for src in self.store.get('mandate', []):
            r = dict(src)
            if r.get('control_id') in computed:
                r['operating_value'], r['status'] = computed[r['control_id']]
                r['_computed'] = True
            rows.append(r)
        return rows

    def conviction_assigned(self):
        return sum(1 for r in self.wb.conviction if not same(r['effective_conviction'], 'Unassigned'))

    # ------------------------------------------------------------------ PEW-007

    def _tests(self):
        t, lab, sc = self.t, self.lab, self.scenario
        deltas = [r['delta'] for r in self.sleeves]
        pew = self.wb.pew004
        committee = sum(1 for r in pew if r['status'] == 'COMMITTEE DECISION REQUIRED')
        role_pass = sum(1 for r in self.roles if r['control_status'] == 'PASS')
        positive = [r for r in sc if r['effective_weight'] > 0]
        equities = sum(1 for r in positive if same(r['security_type'], 'Equity'))
        loaded = sum(1 for r in self.wb.portfolio if not blank(r.get('actual_weight')))
        c = {
            'VAL-001': lab['scenario_total'], 'VAL-002': lab['funding_balance'],
            'VAL-003': min(r['effective_weight'] for r in sc),
            'VAL-004': sum(1 for r in sc if r['validation_state'] == 'Rationale Required'),
            'VAL-005': lab['band_exceptions'], 'VAL-006': lab['gross_turnover'],
            'VAL-007': max(r['abs_change'] for r in sc),
            'VAL-008': max(max(deltas), -min(deltas)),
            'VAL-009': len(positive), 'VAL-010': equities,
            'VAL-011': sum(1 for r in positive if same(r['security_type'], 'ETF')),
            'VAL-012': loaded, 'VAL-013': self.conviction_assigned(), 'VAL-014': role_pass,
            'VAL-015': committee,
            'VAL-016': sum(1 for r in self.wb.conviction if r['decision_state'] != 'NO CHANGE'),
            'VAL-017': lab['readiness'],
        }
        advance = sum(1 for r in pew if r['recommended_action'] == 'ADVANCE')
        c['VAL-018'] = 'REQUIRED' if (c['VAL-006'] > t['turnover_threshold']
                                      or c['VAL-007'] >= t['position_threshold']
                                      or c['VAL-008'] >= t['sleeve_threshold']
                                      or c['VAL-009'] != 47 or advance > 0) else 'NOT REQUIRED'

        def pass_if(ok, fail):
            return 'PASS' if ok else fail

        if c['VAL-010'] > t['equity_ceiling']:
            equity_status = 'FAIL'
        elif t['equity_min'] <= c['VAL-010'] <= t['equity_max']:
            equity_status = 'PASS'
        else:
            equity_status = 'MONITOR — OUTSIDE PREFERRED RANGE'
        status = {
            'VAL-001': pass_if(abs(c['VAL-001'] - 1) <= t['total_tolerance'], 'FAIL'),
            'VAL-002': pass_if(abs(c['VAL-002']) <= t['total_tolerance'], 'FAIL'),
            'VAL-003': pass_if(c['VAL-003'] >= 0, 'FAIL'),
            'VAL-004': pass_if(c['VAL-004'] == 0, 'INPUT REQUIRED'),
            'VAL-005': pass_if(c['VAL-005'] == 0, 'COMMITTEE REVIEW'),
            'VAL-006': pass_if(c['VAL-006'] <= t['turnover_threshold'], 'COMMITTEE REVIEW'),
            'VAL-007': pass_if(c['VAL-007'] < t['position_threshold'], 'COMMITTEE REVIEW'),
            'VAL-008': pass_if(c['VAL-008'] < t['sleeve_threshold'], 'COMMITTEE REVIEW'),
            'VAL-009': pass_if(c['VAL-009'] == 47, 'COMMITTEE REVIEW'),
            'VAL-010': equity_status,
            'VAL-011': pass_if(c['VAL-011'] == 7, 'COMMITTEE REVIEW'),
            'VAL-012': pass_if(c['VAL-012'] == 47, 'INPUT REQUIRED'),
            'VAL-013': pass_if(c['VAL-013'] == 47, 'INPUT REQUIRED'),
            'VAL-014': pass_if(c['VAL-014'] == 47, 'REVIEW'),
            'VAL-015': pass_if(c['VAL-015'] == 0, 'COMMITTEE REVIEW'),
            'VAL-016': pass_if(c['VAL-016'] == 0, 'REVIEW'),
            'VAL-017': pass_if(c['VAL-017'] == 'READY FOR VALIDATION', 'INPUT REQUIRED'),
            'VAL-018': pass_if(c['VAL-018'] == 'NOT REQUIRED', 'REQUIRED'),
        }
        return [dict(zip(('id', 'test', 'standard', 'action', 'authority'), meta),
                     result=c[meta[0]], status=status[meta[0]]) for meta in VALIDATION_TESTS]

    def readiness(self):
        states = [x['status'] for x in self.tests]                                          # J12
        if 'FAIL' in states or 'INPUT REQUIRED' in states:
            return 'NOT READY'
        if any(s in ('COMMITTEE REVIEW', 'REVIEW', 'REQUIRED') for s in states):
            return 'COMMITTEE REVIEW'
        return 'READY'

    def _certification(self):
        header = dict(self.store.get('validation', {}))
        rows = []
        for src in self.store.get('workflow', []):
            r = dict(src)
            r['scenario_id'] = nz_link(self.lab.get('scenario_id'))                         # H
            r['scenario_name'] = nz_link(self.lab.get('scenario_name'))                     # I
            rows.append(r)
        states = [r.get('status') for r in rows]
        tests = {x['id']: x['status'] for x in self.tests}
        empirical = next((r.get('status') for r in rows
                          if same(r.get('stage'), 'Empirical / Monte Carlo Review')), None)
        if any(same(s, 'Rejected') for s in states):                                        # L38
            state = 'REJECTED'
        elif (any(same(s, 'Pending') for s in states) or 'FAIL' in tests.values()
              or 'INPUT REQUIRED' in tests.values()
              or (tests['VAL-018'] == 'REQUIRED' and not same(empirical, 'Approved'))):
            state = 'NOT READY'
        else:
            state = 'READY TO ISSUE NEW MFPDF'
        header['overall_readiness'] = self.readiness()
        header['certification_state'] = state
        return rows, header

    def _changes(self):
        rows = []
        for src in self.store.get('changes', []):
            r = dict(src)
            d, e = num(r.get('certified_weight')), num(r.get('proposed_weight'))
            r['delta'] = '' if d is None or e is None else e - d                            # F
            rows.append(r)
        return rows

    # ------------------------------------------------------------------ 06 PEW Control Center

    def _control_center(self):
        lab = self.lab
        loaded = sum(1 for r in self.wb.portfolio if not blank(r.get('actual_weight')))
        assigned = self.conviction_assigned()
        pew = self.wb.pew004
        committee = sum(1 for r in pew if r['status'] == 'COMMITTEE DECISION REQUIRED')
        mandate_status = [r.get('status') for r in self.mandate]
        sleeve_states = [r['decision_state'] for r in self.sleeves]
        role_open = sum(1 for r in self.roles if r['control_status'] != 'PASS')
        readiness = self.readiness()
        if loaded < 47:                                                                     # G6
            action = 'Load all 47 current actual portfolio weights'
        elif assigned < 47:
            action = 'Assign effective conviction tiers to all active holdings'
        elif lab['changed_positions'] == 0:
            action = 'No allocation redesign is currently proposed'
        else:
            action = 'Resolve scenario evidence and committee decisions'
        if lab['changed_positions'] == 0:
            lab_state = 'BASELINE'
        elif abs(lab['scenario_total'] - 1) > self.t['total_tolerance']:
            lab_state = 'FAIL'
        else:
            lab_state = 'COMMITTEE REVIEW'
        modules = [
            ('PEW-001', 'Mandate & Constraints', 'Defines objective, guardrails and governance',
             'FAIL' if any(same(s, 'FAIL') for s in mandate_status) else 'ACTIVE',
             sum(1 for s in mandate_status if same(s, 'INPUT REQUIRED')),
             'Maintain adopted controls; load objective-test analytics', 'Chief Investment Steward'),
            ('PEW-002', 'Sleeve Architecture', 'Tests purpose, capacity and sleeve allocation',
             'REVIEW' if 'SLEEVE REVIEW' in sleeve_states else (
                 'INPUT REQUIRED' if 'CONVICTION INPUT REQUIRED' in sleeve_states else 'BASELINE'),
             sum(1 for s in sleeve_states if s != 'BASELINE'),
             'Complete conviction inputs; review material sleeve shifts', 'Stewardship Committee'),
            ('PEW-003', 'Role Assignment', 'Confirms each holding has institutional function',
             'PASS' if role_open == 0 else 'REVIEW', role_open,
             'Resolve role, evidence or replacement exceptions', 'Research Committee'),
            ('PEW-004', 'Candidate Comparison', 'Compares incumbents and replacements',
             'READY — NO CANDIDATES' if not any(not blank(r.get('symbol')) for r in pew) else (
                 'COMMITTEE REVIEW' if committee else 'UNDER REVIEW'), committee,
             'Load candidates only when a defined role or replacement need exists',
             'Stewardship Committee'),
            ('PEW-005', 'Conviction', 'Assigns conviction, thesis, risk and horizon',
             'PASS' if assigned == 47 else 'INPUT REQUIRED',
             sum(1 for r in self.wb.conviction if same(r['effective_conviction'], 'Unassigned')),
             'Assign effective conviction to every active holding', 'Stewardship Committee'),
            ('PEW-006', 'Allocation Lab', 'Builds funded, band-aware scenario weights', lab_state,
             lab['changed_positions'], 'Use yellow scenario cells; document rationale for every change',
             'Portfolio Engineering'),
            ('PEW-007', 'Validation & Certification', 'Tests and governs new portfolio version',
             readiness, sum(1 for x in self.tests if x['status'] != 'PASS'),
             'Complete evidence and approvals before issuing new MFPDF', 'Chief Investment Steward'),
        ]
        queue = [
            (1, 'Data Integrity', f'{47 - loaded} actual weights missing', 'Data update required',
             'Load Certified Allocation column I', 'Portfolio Operations',
             'CLOSED' if loaded == 47 else 'ACTION REQUIRED'),
            (2, 'Conviction', f'{self._unassigned()} conviction tiers unassigned',
             'Conviction assignment required', 'Complete PEW-005 effective conviction',
             'Stewardship Committee', 'CLOSED' if self._unassigned() == 0 else 'ACTION REQUIRED'),
            (3, 'Allocation', f"{lab['changed_positions']} scenario positions changed",
             'No allocation decision unless change exists', 'Review funded scenario and bands',
             'Stewardship Committee', 'NO DECISION' if lab['changed_positions'] == 0 else 'COMMITTEE REVIEW'),
            (4, 'Candidate Selection', f'{committee} candidate decisions',
             'Candidate decision only when evidence is complete', 'Approve, reject, defer or exception',
             'Stewardship Committee', 'NO DECISION' if committee == 0 else 'COMMITTEE REVIEW'),
            (5, 'Validation', readiness, 'Certification readiness decision',
             'Complete failed / missing validation controls', 'Chief Investment Steward', readiness),
        ]
        return {
            'implementation_state': readiness, 'primary_action': action,
            'certified_positions': sum(1 for r in self.wb.portfolio if not blank(r.get('symbol'))),
            'actual_loaded': f'{loaded} / 47', 'conviction_assigned': f'{assigned} / 47',
            'scenario_changes': lab['changed_positions'],
            'certification_state': self.certification['certification_state'],
            'modules': modules, 'queue': queue,
        }

    def _unassigned(self):
        return sum(1 for r in self.wb.conviction if same(r['effective_conviction'], 'Unassigned'))


def nz_link(v):
    """A direct link to an empty cell displays as 0."""
    return 0 if blank(v) else v


VALIDATION_TESTS = (
    ('VAL-001', 'Scenario effective weights total', '100.00% ± tolerance',
     'Reconcile scenario weights before review', 'Portfolio Engineering'),
    ('VAL-002', 'Funding balance', '0.00% ± tolerance',
     'Adds must be fully funded by trims / cash source', 'Portfolio Engineering'),
    ('VAL-003', 'No negative scenario weights', 'Minimum weight ≥ 0.00%',
     'Correct any negative allocation', 'Portfolio Engineering'),
    ('VAL-004', 'Changed-position rationales complete', '0 missing rationales',
     'Complete evidence for every changed position', 'Chief Investment Steward'),
    ('VAL-005', 'Certified holding-band exceptions', 'Review each exception; no automatic trade',
     'Document add / trim decision or accepted exception', 'Stewardship Committee'),
    ('VAL-006', 'Gross turnover materiality', '≤ materiality threshold',
     'Run empirical / Monte Carlo review if exceeded', 'Validation Committee'),
    ('VAL-007', 'Maximum single-position change', '< single-position threshold unless validated',
     'Document material position changes', 'Validation Committee'),
    ('VAL-008', 'Maximum sleeve allocation shift', '< sleeve-shift threshold unless validated',
     'Document sleeve-level risk / purpose change', 'Validation Committee'),
    ('VAL-009', 'Positive-weight position count', 'Baseline 47 unless add / remove is approved',
     'Document any removal or candidate addition', 'Stewardship Committee'),
    ('VAL-010', 'Equity-core position count', 'Preferred 32–38; hard ceiling 41',
     'Review complexity above preferred range', 'Stewardship Committee'),
    ('VAL-011', 'ETF position count', 'Approved implementation exposures only',
     'Confirm eligible ETF architecture', 'Stewardship Committee'),
    ('VAL-012', 'Actual portfolio weights loaded', '47 of 47',
     'Load actual weights before implementation review', 'Portfolio Operations'),
    ('VAL-013', 'Effective conviction tiers assigned', '47 of 47',
     'Assign conviction before certification', 'Stewardship Committee'),
    ('VAL-014', 'Portfolio-role controls passed', '47 of 47',
     'Resolve role / evidence exceptions', 'Research Committee'),
    ('VAL-015', 'Candidate committee decisions outstanding', '0 unresolved committee decisions',
     'Resolve candidate / replacement decisions', 'Stewardship Committee'),
    ('VAL-016', 'Research / conviction decisions outstanding',
     '0 unresolved research / conviction decisions', 'Complete thesis and conviction review',
     'Research Committee'),
    ('VAL-017', 'Implementation data readiness', 'READY FOR VALIDATION',
     'Complete required workbook inputs', 'Portfolio Operations'),
    ('VAL-018', 'Empirical / Monte Carlo requirement', 'Required when any materiality trigger is breached',
     'Attach validation package when required', 'Validation Committee'),
)


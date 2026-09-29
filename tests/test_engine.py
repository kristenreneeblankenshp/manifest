"""Branch-level tests of the formula port, using the bundled v0.4 inputs as a base."""

import datetime as dt
import unittest

from manifest_workbench import store as ST
from manifest_workbench.engine import Workbench

TODAY = dt.date(2026, 9, 29)


def base_store():
    return ST.seed_store()


def masr_row(wb, ticker):
    return next(r for r in wb.masr if r.get('ticker') == ticker)


def pipe_row(wb, cid):
    return next(r for r in wb.pipeline if r.get('candidate_id') == cid)


def complete_miar(store, pos, **extra):
    store['miar'][pos] = {
        'miar_id': f'MIAR-{pos:04d}', 'integrity_score': 80, 'mics_score': 75,
        'record_status': 'Active', 'research_owner': 'Research Ops',
        'review_cadence': 'Quarterly — 90 Days', 'last_full_review': '2026-09-01',
        'certified_by': 'CIS', 'certification_date': '2026-09-02', **extra}
    store['conviction'][pos] = {'proposed_conviction': 'Tier 2 — Core', 'thesis_status': 'Current'}


def evidence(eid, ticker, **extra):
    rec = {
        'evidence_id': eid, 'date_received': '2026-09-20', 'evidence_date': '2026-09-19',
        'record_type': 'Certified Holding', 'ticker': ticker, 'subject': ticker,
        'activity_type': 'Company Review', 'category': 'Valuation', 'materiality': 'Moderate',
        'direction': 'Positive', 'reliability': 'Primary — Verified', 'source_type': 'Company Filing',
        'publisher': 'Issuer', 'source_ref': '10-Q', 'summary': 'Quarterly filing reviewed',
        'thesis_sensitivity': 'Medium', 'reviewer': 'RC', 'due_date': '2026-10-15',
        'status': 'Under Review', 'verified': 'Yes', 'miar_action': 'None', 'thesis_impact': 'Intact',
        'conviction_rec': 'No Change', 'candidate_replacement': 'None', 'pew_referral': 'No',
        'disposition': 'Pending'}
    rec.update(extra)
    return rec


class PortfolioTest(unittest.TestCase):
    def test_bands_and_actions(self):
        store = base_store()
        store['portfolio'][0]['actual_weight'] = 0.05   # BRK.B target 3.02% -> upper band 3.775%
        store['portfolio'][6]['actual_weight'] = 0.005  # MA target 1.60% -> lower band 1.20%
        store['portfolio'][1]['actual_weight'] = 0.0302
        wb = Workbench(store, TODAY)
        brk, cost, ma = wb.portfolio[0], wb.portfolio[1], wb.portfolio[6]
        self.assertAlmostEqual(brk['lower_band'], 0.02265)
        self.assertAlmostEqual(brk['upper_band'], 0.03775)
        self.assertEqual((brk['band_status'], brk['rebalancing_action']), ('Above band', 'Review / Trim'))
        self.assertEqual((ma['band_status'], ma['rebalancing_action']), ('Below band', 'Review / Add'))
        self.assertEqual(cost['band_status'], 'Within band')
        self.assertAlmostEqual(ma['lower_band'], 0.012)
        self.assertEqual(wb.portfolio[2]['band_status'], 'Not entered')
        self.assertEqual(wb.portfolio_totals()['certification'], 'Certified 100.00%')
        self.assertEqual(sum(s['positions'] for s in wb.sleeve_summary()), 47)

    def test_band_floor_and_cap(self):
        store = base_store()
        wb = Workbench(store, TODAY)
        self.assertTrue(all(r['lower_band'] >= 0.01 for r in wb.portfolio))
        self.assertTrue(all(r['upper_band'] <= 0.04 for r in wb.portfolio))


class ConvictionTest(unittest.TestCase):
    def test_decision_states(self):
        store = base_store()
        store['conviction'][0] = {'proposed_conviction': 'Tier 1 — Anchor', 'thesis_status': 'Current'}
        store['conviction'][1] = {'proposed_conviction': 'Tier 3 — Opportunistic', 'thesis_status': 'Impaired'}
        store['portfolio'][2]['conviction_tier'] = 'Tier 1'
        store['portfolio'][2]['research_status'] = 'Review Due'
        wb = Workbench(store, TODAY)
        self.assertEqual(wb.conviction[0]['decision_state'], 'COMMITTEE REVIEW')
        self.assertEqual(wb.conviction[0]['conviction_score'], 3)
        self.assertEqual(wb.conviction[1]['decision_state'], 'REDUCE / REPLACE REVIEW')
        self.assertEqual(wb.conviction[2]['decision_state'], 'RESEARCH REVIEW')
        self.assertEqual(wb.conviction[2]['conviction_score'], 0)  # MFPDF "Tier 1" is not a PEW-005 tier
        self.assertEqual(wb.conviction[3]['decision_state'], 'ASSIGN CONVICTION')


class Pew004Test(unittest.TestCase):
    def scored(self, **extra):
        rec = {'candidate_id': 'CAND-001', 'symbol': 'XYZ', 'candidate_type': 'Candidate',
               'market_cap': 120, 'merrill_status': 'Buy', 'zacks_rank': 2, 'mics': 80,
               'miar_integrity': 80, 'empirical_rank': 80, 'role_fit': 80, 'valuation': 80,
               'diversification': 80}
        rec.update(extra)
        store = base_store()
        store['pew004'][0] = rec
        return Workbench(store, TODAY).pew004[0]

    def test_scoring_and_overlay(self):
        r = self.scored()
        self.assertAlmostEqual(r['base_score'], 80)
        self.assertEqual(r['final_score'], 80)
        self.assertEqual(r['recommended_action'], 'RETAIN ON SHORT LIST')
        close = self.scored(close_decision='Yes')
        self.assertAlmostEqual(close['final_score'], 80 * 0.2 + 85 * 0.8)
        self.assertEqual(close['recommended_action'], 'RETAIN ON SHORT LIST')
        close = self.scored(close_decision='Yes', zacks_rank=1)
        self.assertAlmostEqual(close['final_score'], 80 * 0.2 + 100 * 0.8)
        self.assertEqual(close['recommended_action'], 'ADVANCE')
        self.assertEqual(close['status'], 'COMMITTEE DECISION REQUIRED')

    def test_eligibility_exceptions(self):
        self.assertEqual(self.scored(market_cap=30)['eligibility_gate'], 'MARKET CAP EXCEPTION')
        self.assertEqual(self.scored(market_cap=30, candidate_type='Incumbent')['eligibility_gate'], 'ELIGIBLE')
        self.assertEqual(self.scored(merrill_status='No Rating')['eligibility_gate'], 'MERRILL EXCEPTION')
        self.assertEqual(self.scored(zacks_rank=4)['eligibility_gate'], 'ZACKS EXCEPTION')
        missing = self.scored(valuation=None)
        self.assertEqual((missing['eligibility_gate'], missing['recommended_action']),
                         ('DATA MISSING', 'COMPLETE SCORING'))
        exc = self.scored(zacks_rank=5)
        self.assertEqual(exc['recommended_action'], 'DOCUMENT / COMMITTEE EXCEPTION')
        self.assertEqual(exc['status'], 'COMMITTEE DECISION REQUIRED')
        self.assertEqual(self.scored(committee_decision='Approve')['status'], 'Decision Recorded')

    def test_open_slot(self):
        wb = Workbench(base_store(), TODAY)
        self.assertEqual(wb.pew004[5]['status'], 'Open Slot')


class EvidenceTest(unittest.TestCase):
    def status(self, **extra):
        store = base_store()
        rec = evidence('EVD-20260920-001', 'VRT')
        rec.update(extra)
        store['evidence'] = [rec]
        return Workbench(store, TODAY).evidence[0]

    def test_complete_and_routing(self):
        r = self.status()
        self.assertEqual((r['completeness'], r['control_status'], r['referral_eligibility']),
                         ('COMPLETE', 'OPEN — ON TRACK', 'NO REFERRAL REQUIRED'))
        self.assertEqual(r['sleeve'], 'Digital Infrastructure & AI')
        self.assertEqual(r['days_open'], 9)
        self.assertEqual(self.status(miar_action='Full Review')['referral_eligibility'], 'ELIGIBLE FOR ROUTING')

    def test_control_statuses(self):
        self.assertEqual(self.status(summary=None)['control_status'], 'INCOMPLETE')
        self.assertEqual(self.status(ticker='EMR')['control_status'], 'HOLDING IDENTIFIER MISMATCH')
        self.assertEqual(self.status(materiality='High', verified='No')['control_status'], 'VERIFY / ESCALATE')
        self.assertEqual(self.status(conviction_rec='Unassigned')['control_status'],
                         'CONVICTION DECISION REQUIRED')
        self.assertEqual(self.status(due_date='2026-09-01')['control_status'], 'OVERDUE')
        self.assertEqual(self.status(status='Closed — Incorporated')['control_status'], 'CLOSE DATE REQUIRED')
        self.assertEqual(self.status(closed_date='2026-09-25')['control_status'], 'STATUS / CLOSE DATE MISMATCH')
        self.assertEqual(self.status(pew_referral='Yes — PEW-004 Candidate', verified='No')['control_status'],
                         'PEW REFERRAL BLOCKED')
        self.assertEqual(self.status(status='Awaiting Verification')['control_status'], 'STATUS MISMATCH')
        closed = self.status(status='Closed — No Action', closed_date='2026-09-25')
        self.assertEqual((closed['control_status'], closed['days_open']), ('CLOSED', 5))
        macro = self.status(record_type='Market / Macro', ticker=None)
        self.assertEqual(macro['completeness'], 'COMPLETE')

    def test_duplicate_id(self):
        store = base_store()
        store['evidence'] = [evidence('EVD-20260920-001', 'VRT'), evidence('EVD-20260920-001', 'VRT')]
        wb = Workbench(store, TODAY)
        self.assertEqual(wb.evidence[0]['control_status'], 'DUPLICATE ID')


class MiarTest(unittest.TestCase):
    def freshness(self, last_full, cadence='Quarterly — 90 Days', **extra):
        store = base_store()
        complete_miar(store, 0, last_full_review=last_full, review_cadence=cadence, **extra)
        return Workbench(store, TODAY).miar[0]

    def test_freshness_windows(self):
        self.assertEqual(self.freshness('2026-09-01')['research_freshness'], 'CURRENT')    # due 11-30
        self.assertEqual(self.freshness('2026-08-01')['research_freshness'], 'UPDATE DUE')  # due 10-30
        self.assertEqual(self.freshness('2026-07-15')['research_freshness'], 'REVIEW DUE')  # due 10-13
        overdue = self.freshness('2026-06-01')
        self.assertEqual((overdue['research_freshness'], overdue['control_status']), ('OVERDUE', 'OVERDUE'))
        self.assertEqual(overdue['required_action'], 'Complete overdue full review')
        self.assertEqual(self.freshness('2025-01-01', 'Event-Driven')['research_freshness'], 'CURRENT')
        self.assertEqual(self.freshness('2026-09-01', record_status='Suspended')['research_freshness'], 'INACTIVE')
        latest = self.freshness('2026-06-01', last_incremental='2026-09-10')
        self.assertEqual(latest['latest_dossier_date'], dt.date(2026, 9, 10))
        self.assertEqual(latest['research_freshness'], 'CURRENT')

    def test_control_status_chain(self):
        clear = self.freshness('2026-09-01')
        self.assertEqual((clear['control_status'], clear['rcc007_referral']), ('CONTROL CLEAR', 'NO REFERRAL'))
        self.assertEqual(self.freshness('2026-09-01', certified_by=None)['control_status'],
                         'CERTIFICATION REQUIRED')
        self.assertEqual(self.freshness('2026-09-01', record_status='Draft')['control_status'],
                         'DRAFT — NOT CERTIFIED')
        store = base_store()
        complete_miar(store, 0, last_full_review='2026-09-01')
        store['conviction'][0] = {}
        wb = Workbench(store, TODAY)
        self.assertEqual(wb.miar[0]['control_status'], 'THESIS / CONVICTION SETUP')
        self.assertEqual(wb.miar[0]['rcc007_referral'], 'REFER TO RCC-007')

    def test_material_event_overrides(self):
        store = base_store()
        complete_miar(store, 0, last_full_review='2026-09-01')
        store['evidence'] = [evidence('EVD-20260920-001', 'BRK.B', miar_action='Material Event Review')]
        wb = Workbench(store, TODAY)
        r = wb.miar[0]
        self.assertEqual((r['research_freshness'], r['control_status'], r['rcc007_referral']),
                         ('MATERIAL EVENT REVIEW', 'MATERIAL EVENT REVIEW', 'REFER TO RCC-007'))
        self.assertEqual((r['miar_actions_pending'], r['material_event_reviews']), (1, 1))

    def test_duplicate_miar_id(self):
        store = base_store()
        complete_miar(store, 0)
        complete_miar(store, 1)
        store['miar'][1]['miar_id'] = store['miar'][0]['miar_id']
        wb = Workbench(store, TODAY)
        self.assertEqual(wb.miar[1]['dossier_completeness'], 'DUPLICATE MIAR ID')


class ReviewLogTest(unittest.TestCase):
    def test_certification_rules(self):
        store = base_store()
        base = {'review_id': 'MIR-20260920-001', 'review_date': '2026-09-20', 'ticker': 'VRT',
                'review_type': 'Full Review', 'reviewer': 'RC', 'evidence_ids': 'EVD-1',
                'proposed_status': 'Active', 'proposed_integrity': 80, 'proposed_mics': 75,
                'thesis_assessment': 'Intact', 'conviction_rec': 'No Change', 'findings': 'ok',
                'required_miar_action': 'None', 'certification_rec': 'Certify Current',
                'source_ref': 'memo'}
        store['review'] = [dict(base), dict(base, review_id='MIR-20260920-002', certified_by='CIS',
                                            certification_date='2026-09-21'),
                           dict(base, review_id='MIR-20260920-003', certification_rec='No Certification',
                                certified_by='CIS'),
                           dict(base, review_id='MIR-20260920-004', ticker='ZZZ', findings=None)]
        wb = Workbench(store, TODAY)
        self.assertEqual([r['control_status'] for r in wb.review],
                         ['CERTIFICATION REQUIRED', 'COMPLETE', 'CERTIFICATION MISMATCH', 'INCOMPLETE'])
        self.assertEqual(wb.review[3]['security'], 'TICKER NOT FOUND')
        self.assertEqual(wb.miar[22]['review_log_entries'], 3)  # VRT


class MasrTest(unittest.TestCase):
    def candidate(self, **extra):
        store = base_store()
        emr = next(r for r in store['masr'] if r.get('ticker') == 'EMR')
        emr.update({'masr_id': 'MASR-0101', 'market_cap': 70, 'zacks_rank': 2,
                    'merrill_status': 'Buy', 'empirical_rank': 20})
        emr.update(extra)
        return store

    def test_candidate_without_miar_is_not_eligible(self):
        # v0.4 limits the MIAR registry to certified holdings, so non-holdings cannot
        # satisfy the MIAR gate until RCC-003 covers them.
        r = masr_row(Workbench(self.candidate(), TODAY), 'EMR')
        self.assertEqual((r['eligibility_gate'], r['control_status']), ('NOT ELIGIBLE', 'MIAR SETUP REQUIRED'))
        self.assertEqual(r['exception_requirement'], 'Complete MIAR / scoring / empirical eligibility')

    def test_certified_holding_exceptions(self):
        store = base_store()
        complete_miar(store, 22)  # VRT
        vrt = next(r for r in store['masr'] if r.get('_linked') == 22)
        vrt['masr_id'] = 'MASR-0023'
        wb = Workbench(store, TODAY)
        r = masr_row(wb, 'VRT')
        self.assertEqual((r['eligibility_gate'], r['exception_requirement'], r['control_status']),
                         ('CERTIFIED HOLDING', 'None', 'CONTROL CLEAR'))
        self.assertAlmostEqual(r['certified_weight'], 0.0155)
        for extra, expected in (({'zacks_rank': 4}, 'Zacks #4/#5 exception review'),
                                ({'merrill_status': 'No Rating'}, 'Merrill No Rating exception'),
                                ({'merrill_status': 'Restricted / Unavailable'},
                                 'Merrill restricted / unavailable exception')):
            vrt.update(extra)
            r = masr_row(Workbench(store, TODAY), 'VRT')
            self.assertEqual((r['exception_requirement'], r['control_status']), (expected, 'EXCEPTION REVIEW'))
            for k in extra:
                vrt.pop(k)

    def test_duplicates_and_setup(self):
        store = self.candidate()
        store['masr'].append({'ticker': 'EMR', 'masr_id': 'MASR-0101'})
        wb = Workbench(store, TODAY)
        emr = [r for r in wb.masr if r.get('ticker') == 'EMR']
        self.assertEqual({r['control_status'] for r in emr}, {'DUPLICATE MASR ID'})
        base = Workbench(base_store(), TODAY)
        self.assertEqual(masr_row(base, 'BRK.B')['control_status'], 'SETUP REQUIRED')
        self.assertEqual(masr_row(base, 'EMR')['pipeline_records'], 1)
        self.assertEqual(masr_row(base, 'EMR')['current_stage'], 'Intake')
        self.assertEqual(masr_row(base, 'EMR')['pew_referral_state'], 'CANDIDATE RECORD ACTIVE')
        self.assertEqual(masr_row(base, 'MSFT')['pew_referral_state'], 'NO ACTIVE CANDIDATE')

    def _eligible_non_holding(self, **extra):
        """A non-holding that borrows a complete MIAR record via a shared ticker lookup."""
        store = base_store()
        complete_miar(store, 22)
        store['masr'] = [r for r in store['masr'] if r.get('_linked') != 22]
        store['masr'].append({'masr_id': 'MASR-0900', 'ticker': 'VRT', 'security': 'Vertiv',
                              'record_class': 'MASR Approved Non-Holding',
                              'registry_status': 'Active — Approved Non-Holding',
                              'admission_basis': 'Manifest Research',
                              'sleeve': 'Digital Infrastructure & AI', 'role': 'Enabler',
                              'security_type': 'Equity', 'market_cap': 70, 'zacks_rank': 2,
                              'merrill_status': 'Buy', 'empirical_rank': 20, **extra})
        return masr_row(Workbench(store, TODAY), 'VRT')

    def test_non_holding_governance_chain(self):
        r = self._eligible_non_holding()
        self.assertEqual((r['eligibility_gate'], r['control_status']),
                         ('ELIGIBLE', 'COMMITTEE DISPOSITION REQUIRED'))
        r = self._eligible_non_holding(committee_disposition='Approve MASR Admission')
        self.assertEqual(r['control_status'], 'CERTIFICATION REQUIRED')
        r = self._eligible_non_holding(committee_disposition='Approve MASR Admission',
                                       approved_by='CIS', approval_date='2026-09-20')
        self.assertEqual(r['control_status'], 'CONTROL CLEAR')
        r = self._eligible_non_holding(admission_basis='Zacks Election', market_cap=40)
        self.assertEqual((r['eligibility_gate'], r['exception_requirement']),
                         ('ELIGIBLE WITH EXCEPTION', 'Sub-$50B Zacks election exception'))
        r = self._eligible_non_holding(empirical_rank=None)
        self.assertEqual(r['control_status'], 'NOT ELIGIBLE')
        r = self._eligible_non_holding(registry_status='Rejected', record_class='Rejected Candidate')
        self.assertEqual(r['control_status'], 'INACTIVE / CLOSED')


class PipelineTest(unittest.TestCase):
    CID = 'MCP-20260824-001'  # VRT retention review

    def ready_store(self):
        store = base_store()
        complete_miar(store, 22)
        next(r for r in store['masr'] if r.get('_linked') == 22)['masr_id'] = 'MASR-0023'
        store['evidence'] = [evidence('EVD-20260920-001', 'VRT')]
        store['pipeline'][0]['due_date'] = '2026-10-31'
        return store

    def gate(self, store, **extra):
        store['pipeline'][0].update(extra)
        return pipe_row(Workbench(store, TODAY), self.CID)

    def test_overdue_as_of_today(self):
        wb = Workbench(base_store(), TODAY)
        r = pipe_row(wb, self.CID)
        self.assertEqual((r['gate_result'], r['control_status'], r['days_open']),
                         ('PASS — STAGE GATE', 'OVERDUE', 36))
        self.assertEqual(r['next_action'], 'Complete or formally extend the overdue review')

    def test_gates_in_order(self):
        base = base_store()
        self.assertEqual(self.gate(base, owner=None)['gate_result'], 'FAIL — INCOMPLETE')
        store = base_store()
        store['pipeline'][0]['candidate_id'] = 'MCP-20260824-002'
        dupes = [r for r in Workbench(store, TODAY).pipeline if r['candidate_id'] == 'MCP-20260824-002']
        self.assertEqual({r['gate_result'] for r in dupes}, {'FAIL — DUPLICATE ID'})
        self.assertEqual({r['control_status'] for r in dupes}, {'DUPLICATE CANDIDATE ID'})
        store = base_store()
        store['pipeline'][1]['stage'] = 'MIAR Review'
        store['pipeline'][1]['ticker'] = 'NOPE'
        r = pipe_row(Workbench(store, TODAY), 'MCP-20260824-002')
        self.assertEqual((r['gate_result'], r['control_status']),
                         ('FAIL — MASR RECORD REQUIRED', 'MASR RECORD REQUIRED'))
        store = base_store()
        store['pipeline'][1]['stage'] = 'Eligibility Review'
        r = pipe_row(Workbench(store, TODAY), 'MCP-20260824-002')
        self.assertEqual(r['gate_result'], 'FAIL — ELIGIBILITY')
        store = self.ready_store()
        store['evidence'] = []
        self.assertEqual(self.gate(store, stage='Candidate Comparison')['gate_result'], 'FAIL — EVIDENCE')
        store = self.ready_store()
        store['miar'][22]['last_full_review'] = '2026-06-01'
        self.assertEqual(self.gate(store, stage='Candidate Comparison')['gate_result'], 'FAIL — MIAR GATE')
        store = self.ready_store()
        self.assertEqual(self.gate(store, stage='Candidate Comparison')['gate_result'], 'PASS — STAGE GATE')
        self.assertEqual(self.gate(store, stage='Approved for MASR')['gate_result'],
                         'FAIL — COMMITTEE DISPOSITION')
        r = self.gate(store, stage='Referred to PEW-004', committee_disposition='Advance to PEW-004')
        self.assertEqual((r['gate_result'], r['control_status']),
                         ('FAIL — PEW REFERRAL', 'PEW REFERRAL INCOMPLETE'))
        store['pew004'][0].update({'symbol': 'VRT'})
        r = self.gate(store, pew_referral='Yes — Refer to PEW-004', pew_candidate_id='CAND-001')
        self.assertEqual(r['gate_result'], 'PASS — STAGE GATE')
        self.assertEqual(r['pew_status'], 'Under Review')
        wb = Workbench(store, TODAY)
        self.assertEqual(masr_row(wb, 'VRT')['pew_referral_state'], 'REFERRED — PEW-004')
        self.assertEqual(wb.rcc004()['state']['pew_referrals'], 1)

    def test_closure(self):
        store = self.ready_store()
        r = self.gate(store, stage='Rejected', committee_disposition='Reject Candidate')
        self.assertEqual(r['control_status'], 'CLOSURE REQUIRED')
        r = self.gate(store, closure_reason='Rejected — Valuation', closed_by='RC', closed_date='2026-09-28')
        self.assertEqual((r['control_status'], r['days_open']), ('CLOSED', 35))
        self.assertEqual(Workbench(store, TODAY).rcc004()['state']['active_candidates'], 9)


class ControlCenterTest(unittest.TestCase):
    def test_rcc004_counts_today(self):
        d = Workbench(base_store(), TODAY).rcc004()
        self.assertEqual(d['state']['control_exceptions'], 66)  # 56 registry setups + 10 overdue
        self.assertEqual(d['controls'][5]['count'], 10)
        self.assertEqual(d['state']['readiness'], 'SETUP / CONTROL EXCEPTIONS OPEN')

    def test_rcc001_readiness_progression(self):
        store = base_store()
        self.assertEqual(Workbench(store, TODAY).rcc001()['state']['readiness'], 'RESEARCH SETUP INCOMPLETE')
        store['pipeline'] = []
        store['masr'] = []
        for pos in range(47):
            complete_miar(store, pos)
        self.assertEqual(Workbench(store, TODAY).rcc001()['state']['readiness'],
                         'RCC READY — NO EVIDENCE LOADED')
        store['evidence'] = [evidence('EVD-20260920-001', 'VRT')]
        self.assertEqual(Workbench(store, TODAY).rcc001()['state']['readiness'], 'ACTIVE')
        store['evidence'][0]['due_date'] = '2026-09-01'
        self.assertEqual(Workbench(store, TODAY).rcc001()['state']['readiness'], 'RCC CONTROL EXCEPTIONS')


if __name__ == '__main__':
    unittest.main()

"""Tests for the MOPS-002 PEW and CISC-001 sheets beyond the workbook's saved state."""

import datetime as dt
import unittest

from manifest_workbench import store as ST
from manifest_workbench.cisc import text_date
from manifest_workbench.engine import Workbench

TODAY = dt.date(2026, 9, 30)


def load_actuals(store, bump=None):
    """Actual weights equal to target, optionally overriding some symbols."""
    for r in store['portfolio']:
        r['actual_weight'] = r['target_weight']
    for sym, w in (bump or {}).items():
        next(r for r in store['portfolio'] if r['symbol'] == sym)['actual_weight'] = w


def assign_convictions(store):
    for r in store['conviction']:
        r['proposed_conviction'] = 'Tier 2 — Core'
        r['thesis_status'] = 'Current'


def pos(store, symbol):
    return next(i for i, r in enumerate(store['portfolio']) if r['symbol'] == symbol)


class AllocationLabTest(unittest.TestCase):
    def test_baseline(self):
        pew = Workbench(ST.seed_store(), TODAY).pew()
        self.assertEqual(pew.lab['scenario_status'], 'DATA SETUP REQUIRED')
        self.assertEqual(pew.lab['changed_positions'], 0)
        self.assertEqual(pew.readiness(), 'NOT READY')

    def test_funded_scenario(self):
        store = ST.seed_store()
        load_actuals(store)
        assign_convictions(store)
        store['scenario'][pos(store, 'NVDA')] = {'scenario_weight': 0.0318, 'rationale': 'AI capex'}
        store['scenario'][pos(store, 'JEPQ')] = {'scenario_weight': 0.0252}
        pew = Workbench(store, TODAY).pew()
        nvda = pew.scenario[pos(store, 'NVDA')]
        jepq = pew.scenario[pos(store, 'JEPQ')]
        self.assertAlmostEqual(nvda['change'], 0.005)
        self.assertEqual((nvda['funding'], nvda['band_test'], nvda['trigger'], nvda['validation_state']),
                         ('Funding Required', 'Within Certified Band', 'REVIEW PROPOSED CHANGE',
                          'Ready for Validation'))
        self.assertEqual((jepq['funding'], jepq['validation_state']), ('Source of Funds', 'Rationale Required'))
        lab = pew.lab
        self.assertEqual(lab['changed_positions'], 2)
        self.assertAlmostEqual(lab['funding_balance'], 0, places=9)
        self.assertAlmostEqual(lab['gross_turnover'], 0.005)
        self.assertEqual(lab['readiness'], 'INPUT REQUIRED — COMPLETE RATIONALES')
        self.assertEqual(lab['scenario_status'], 'COMMITTEE REVIEW REQUIRED')
        tests = {t['id']: t['status'] for t in pew.tests}
        self.assertEqual(tests['VAL-004'], 'INPUT REQUIRED')
        self.assertEqual(tests['VAL-007'], 'PASS')  # 0.50% < 0.75% single-position threshold
        sleeve = next(s for s in pew.sleeves if s['sleeve'] == 'Growth Compounders')
        self.assertAlmostEqual(sleeve['delta'], 0.005)
        self.assertEqual(sleeve['decision_state'], 'REVIEW PROPOSED SHIFT')

    def test_material_and_band_exceptions(self):
        store = ST.seed_store()
        store['scenario'][pos(store, 'NVDA')] = {'scenario_weight': 0.045, 'rationale': 'x'}
        pew = Workbench(store, TODAY).pew()
        nvda = pew.scenario[pos(store, 'NVDA')]
        self.assertEqual(nvda['trigger'], 'BAND EXCEPTION — COMMITTEE DECISION')
        tests = {t['id']: (t['result'], t['status']) for t in pew.tests}
        self.assertEqual(tests['VAL-001'][1], 'FAIL')        # unfunded: total > 100%
        self.assertEqual(tests['VAL-002'][1], 'FAIL')
        self.assertEqual(tests['VAL-018'], ('REQUIRED', 'REQUIRED'))
        self.assertEqual(pew.lab['scenario_status'], 'DATA SETUP REQUIRED')
        self.assertEqual(pew.control['modules'][5][3], 'FAIL')  # PEW-006 unbalanced scenario

    def test_certification_workflow(self):
        store = ST.seed_store()
        load_actuals(store)
        assign_convictions(store)
        pew = Workbench(store, TODAY).pew()
        self.assertEqual(pew.readiness(), 'COMMITTEE REVIEW')  # equity count 40 -> monitor, not fail
        self.assertEqual(pew.certification['certification_state'], 'NOT READY')  # reviews pending
        for r in store['workflow']:
            if r['status'] == 'Pending':
                r['status'] = 'Approved'
        pew = Workbench(store, TODAY).pew()
        self.assertEqual(pew.certification['certification_state'], 'READY TO ISSUE NEW MFPDF')
        store['workflow'][2]['status'] = 'Rejected'
        self.assertEqual(Workbench(store, TODAY).pew().certification['certification_state'], 'REJECTED')

    def test_change_register_delta(self):
        store = ST.seed_store()
        store['changes'][0].update({'certified_weight': 0.0268, 'proposed_weight': 0.0318})
        pew = Workbench(store, TODAY).pew()
        self.assertAlmostEqual(pew.changes[0]['delta'], 0.005)
        self.assertEqual(pew.changes[1]['delta'], '')


class MandateRolesTest(unittest.TestCase):
    def test_mandate_formula_rows(self):
        store = ST.seed_store()
        load_actuals(store)
        assign_convictions(store)
        m = {r['control_id']: r for r in Workbench(store, TODAY).pew().mandate}
        self.assertEqual((m['PEW-001-25']['operating_value'], m['PEW-001-25']['status']),
                         ('47 / 47 loaded', 'PASS'))
        self.assertEqual(m['PEW-001-26']['status'], 'PASS')
        self.assertEqual(m['PEW-001-09']['status'], 'MONITOR — ABOVE PREFERRED RANGE')
        self.assertEqual(m['PEW-001-01']['status'], 'ACTIVE')  # adopted text rows are unchanged

    def test_role_statuses(self):
        store = ST.seed_store()
        store['roles'][0]['functional_role'] = None
        store['roles'][1]['five_year_evidence'] = 'Review'
        store['roles'][2]['role_decision'] = 'Replacement Candidate'
        pew = Workbench(store, TODAY).pew()
        self.assertEqual([r['control_status'] for r in pew.roles[:4]],
                         ['ROLE REQUIRED', 'EVIDENCE REVIEW', 'COMMITTEE REVIEW', 'PASS'])
        self.assertEqual(pew.sleeves[0]['role_control'], 'REVIEW')
        self.assertEqual(pew.role_summary(), {'passed': 44, 'review_items': 3, 'replacement_candidates': 1})


class CiscTest(unittest.TestCase):
    def test_posture_thresholds(self):
        for score, posture, bias in ((0.6, 'MAINTAIN STRATEGIC ALLOCATION', 'OPPORTUNISTIC'),
                                     (0.2, 'MAINTAIN STRATEGIC ALLOCATION', 'BALANCED'),
                                     (0.0, 'HOLD / MONITOR', 'DISCIPLINED'),
                                     (-0.2, 'DEFENSIVE TILT', 'DEFENSIVE'),
                                     (-0.5, 'REDUCE RISK', 'CAPITAL PRESERVATION')):
            store = ST.seed_store()
            for c in store['composite']:
                c['score'] = score
            controls = Workbench(store, TODAY).cisc().controls
            self.assertAlmostEqual(controls['composite_score'], score)
            self.assertEqual((controls['posture'], controls['compass_bias']), (posture, bias))

    def test_live_ranking_and_alerts(self):
        store = ST.seed_store()
        load_actuals(store, {'MA': 0.035, 'VFH': 0.005, 'NVDA': 0.04})
        cisc = Workbench(store, TODAY).cisc()
        d = cisc.data
        self.assertEqual(d['ranking_basis'], 'Actual Weight')
        self.assertEqual(d['top10'][0]['symbol'], 'NVDA')
        self.assertEqual(d['band_breaches'], 3)
        self.assertEqual([a['symbol'] for a in d['alerts'][:3]], ['MA', 'NVDA', 'VFH'])
        self.assertAlmostEqual(d['alerts'][0]['variance'], 0.019)
        self.assertEqual(cisc.decision['state'], 'COMMITTEE ACTION REQUIRED')
        self.assertEqual(cisc.decision['meeting'], 'CONVENE COMMITTEE')
        self.assertEqual(cisc.console['recommendation'], 'REVIEW IDENTIFIED DECISIONS')
        self.assertIn('3 allocation-band exceptions', cisc.console['alert_note'])

    def test_no_action_state(self):
        store = ST.seed_store()
        load_actuals(store)
        cisc = Workbench(store, TODAY).cisc()
        self.assertEqual(cisc.decision['state'], 'NO COMMITTEE ACTION REQUIRED')
        self.assertEqual(cisc.decision['priority'], 'Continue disciplined monitoring')
        self.assertEqual(cisc.console['alert_note'], 'All positions are within certified bands.')
        store['decisions'][5] = {'id': 'DC-006', 'committee_decision': 'Yes', 'status': 'In Review'}
        store['intel-thesis'][0] = {'symbol': 'MU', 'reason': 'Memory cycle', 'status': 'Decision Required'}
        cisc = Workbench(store, TODAY).cisc()
        self.assertEqual((cisc.decision['manual_decisions'], cisc.decision['research_decisions']), (1, 1))
        self.assertEqual(cisc.decision['state'], 'COMMITTEE ACTION REQUIRED')
        self.assertEqual(cisc.console['research']['thesis'][0], 'MU — Memory cycle')

    def test_research_panel_formats(self):
        store = ST.seed_store()
        store['intel-events'][0] = {'date': '2026-10-22', 'symbol': 'NVDA', 'event': 'Q3 earnings'}
        store['intel-zacks'][0] = {'symbol': 'MU', 'prior_rank': 2, 'current_rank': 4}
        r = Workbench(store, TODAY).cisc().console['research']
        self.assertEqual(r['events'][0], '10/22  NVDA — Q3 earnings')
        self.assertEqual(r['zacks'][0], 'MU  #2 → #4')
        self.assertEqual(r['review'][0], 'No entry loaded')

    def test_text_dates(self):
        self.assertEqual(text_date('2026-07-27', 'dddd, mmm d, yyyy'), 'Monday, Jul 27, 2026')
        self.assertEqual(text_date('2026-07-05', 'm/d'), '7/5')
        self.assertEqual(text_date(None, 'm/d/yyyy'), '')


class MigrationTest(unittest.TestCase):
    def test_older_data_file_gains_new_sheets(self):
        store = ST.seed_store()
        store['portfolio'][0]['actual_weight'] = 0.03
        for key in ('controls', 'mandate', 'actions', 'validation'):
            del store[key]
        migrated = ST._validate(store)
        self.assertEqual(migrated['portfolio'][0]['actual_weight'], 0.03)
        self.assertEqual(len(migrated['mandate']), 28)
        self.assertEqual(migrated['controls']['console_id'], 'CISC-001')


if __name__ == '__main__':
    unittest.main()

"""Tests for controlled edits: parsing, locks, uniqueness, IDs, capacity and stage gates."""

import datetime as dt
import unittest

from manifest_workbench import ops
from manifest_workbench import schema as S
from manifest_workbench import store as ST
from manifest_workbench.engine import Workbench

TODAY = dt.date(2026, 9, 29)
CID = 'MCP-20260824-001'


def fresh():
    return ST.seed_store()


class ParseTest(unittest.TestCase):
    def test_controlled_values(self):
        stage = S.PIPELINE.field('stage')
        self.assertEqual(ops.parse_value(stage, 'referred', TODAY), 'Referred to PEW-004')
        self.assertEqual(ops.parse_value(stage, 'ON WATCH', TODAY), 'On Watch')
        status = S.EVIDENCE.field('status')
        self.assertEqual(ops.parse_value(status, 'Closed - No Action', TODAY), 'Closed — No Action')
        with self.assertRaises(ops.OpError):
            ops.parse_value(status, 'closed', TODAY)  # ambiguous
        with self.assertRaises(ops.OpError):
            ops.parse_value(status, 'finished', TODAY)
        zacks = S.MASR.field('zacks_rank')
        self.assertEqual(ops.parse_value(zacks, '#2', TODAY), 2)
        with self.assertRaises(ops.OpError):
            ops.parse_value(zacks, '6', TODAY)

    def test_types(self):
        self.assertEqual(ops.parse_value(S.MASR.field('market_cap'), '$1,250.5', TODAY), 1250.5)
        self.assertEqual(ops.parse_value(S.MASR.field('approval_date'), 'today', TODAY), '2026-09-29')
        weight = S.ALLOCATION.field('actual_weight')
        self.assertAlmostEqual(ops.parse_value(weight, '3.1%', TODAY), 0.031)
        self.assertAlmostEqual(ops.parse_value(weight, '0.031', TODAY), 0.031)
        self.assertAlmostEqual(ops.parse_value(weight, '3.1', TODAY), 0.031)
        self.assertIsNone(ops.parse_value(weight, '', TODAY))
        with self.assertRaises(ops.OpError):
            ops.parse_value(S.MASR.field('approval_date'), '09/29/2026', TODAY)

    def test_field_names(self):
        self.assertEqual(S.MASR.field('T').key, 'market_cap')
        self.assertEqual(S.MASR.field('merrill').key, 'merrill_status')
        self.assertEqual(S.MASR.field('Registry Status').key, 'registry_status')
        with self.assertRaises(KeyError):
            S.MASR.field('mi')  # ambiguous prefix: miar_id / miar_status


class LockTest(unittest.TestCase):
    def test_certified_data_locked(self):
        store = fresh()
        for table, key, pair in (('portfolio', 'NVDA', 'target_weight=5%'),
                                 ('portfolio', 'NVDA', 'symbol=NVDX'),
                                 ('masr', 'NVDA', 'record_class=Removed Security'),
                                 ('masr', 'NVDA', 'ticker=XX'),
                                 ('masr', 'EMR', 'eligibility_gate=ELIGIBLE'),
                                 ('miar', 'NVDA', 'research_freshness=CURRENT'),
                                 ('pipeline', CID, 'candidate_id=MCP-20260824-099'),
                                 ('pew004', 'CAND-001', 'candidate_id=CAND-099')):
            with self.subTest(table=table, pair=pair), self.assertRaises(ops.OpError):
                ops.set_fields(store, table, key, [pair], 'tester', TODAY)
        self.assertEqual(store['audit'], [])

    def test_inputs_editable_and_audited(self):
        store = fresh()
        ops.set_fields(store, 'portfolio', 'nvda', ['actual_weight=2.5%', 'N=Review Due'], 'tester', TODAY)
        self.assertAlmostEqual(store['portfolio'][11]['actual_weight'], 0.025)
        self.assertEqual(store['portfolio'][11]['research_status'], 'Review Due')
        self.assertEqual([e['field'] for e in store['audit']], ['actual_weight', 'research_status'])
        self.assertEqual(store['audit'][0]['record'], 'NVDA')
        ops.set_fields(store, 'portfolio', 'NVDA', ['actual_weight='], 'tester', TODAY)
        self.assertNotIn('actual_weight', store['portfolio'][11])
        ops.set_fields(store, 'masr', 'NVDA', ['masr_id=MASR-0012', 'AB=Exception Approved'], 'tester', TODAY)
        self.assertEqual(store['masr'][11]['masr_id'], 'MASR-0012')


class UniquenessTest(unittest.TestCase):
    def test_masr_identity(self):
        store = fresh()
        ops.set_fields(store, 'masr', 'VRT', ['masr_id=MASR-0023'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.set_fields(store, 'masr', 'EMR', ['masr_id=masr-0023'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'masr', ['ticker=vrt'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'masr', ['ticker=emr'], 'tester', TODAY)
        rec = ops.add_record(store, 'masr', ['ticker=pwr', 'record_class=Research Candidate'], 'tester', TODAY)
        self.assertEqual(rec['ticker'], 'PWR')
        ops.set_fields(store, 'masr', 'PWR', ['masr_id=MASR-0300'], 'tester', TODAY)
        self.assertEqual(ops.find(store, 'masr', 'MASR-0300')[1]['ticker'], 'PWR')

    def test_miar_identity(self):
        store = fresh()
        ops.set_fields(store, 'miar', 'VRT', ['miar_id=MIAR-1'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.set_fields(store, 'miar', 'MSFT', ['miar_id=MIAR-1'], 'tester', TODAY)


class AddTest(unittest.TestCase):
    def test_ids_generated_and_validated(self):
        store = fresh()
        rec = ops.add_record(store, 'pipeline', ['ticker=pwr', 'candidate_type=new'], 'tester', TODAY)
        self.assertEqual(rec['candidate_id'], 'MCP-20260929-001')
        self.assertEqual((rec['stage'], rec['intake_date'], rec['ticker']), ('Intake', '2026-09-29', 'PWR'))
        rec = ops.add_record(store, 'pipeline', ['ticker=abc', 'intake_date=2026-08-24'], 'tester', TODAY)
        self.assertEqual(rec['candidate_id'], 'MCP-20260824-011')
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'pipeline', ['candidate_id=MCP-20260824-011', 'ticker=x'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'pipeline', ['candidate_id=CAND-7', 'ticker=x'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'pipeline', ['ticker=x', 'stage=Committee Review'], 'tester', TODAY)
        ev = ops.add_record(store, 'evidence', ['ticker=vrt', 'date_received=2026-09-01'], 'tester', TODAY)
        self.assertEqual(ev['evidence_id'], 'EVD-20260901-001')
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'review', ['ticker=EMR'], 'tester', TODAY)  # not a certified holding
        rv = ops.add_record(store, 'review', ['ticker=VRT'], 'tester', TODAY)
        self.assertEqual(rv['review_id'], 'MIR-20260929-001')
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'miar', ['ticker=VRT'], 'tester', TODAY)

    def test_capacity(self):
        store = fresh()
        store['masr'].extend({'ticker': f'T{i}'} for i in range(150 - len(store['masr'])))
        with self.assertRaises(ops.OpError):
            ops.add_record(store, 'masr', ['ticker=ONEMORE'], 'tester', TODAY)


class StageGateTest(unittest.TestCase):
    def test_advance_requires_passing_gate(self):
        store = fresh()
        self.assertEqual(ops.advance(store, CID, 'tester', TODAY), ('Intake', 'Evidence Gathering'))
        ops.advance(store, CID, 'tester', TODAY)
        ops.advance(store, CID, 'tester', TODAY)       # MIAR Review -> Eligibility Review
        wb = Workbench(store, TODAY)
        self.assertEqual(wb.pipeline[0]['stage'], 'Eligibility Review')
        # VRT is a certified holding (eligible), but it has no evidence and no MIAR dossier.
        ops.advance(store, CID, 'tester', TODAY)       # -> Candidate Comparison (gate now fails)
        with self.assertRaises(ops.OpError) as ctx:
            ops.advance(store, CID, 'tester', TODAY)
        self.assertIn('FAIL — EVIDENCE', str(ctx.exception))
        with self.assertRaises(ops.OpError):
            ops.set_fields(store, 'pipeline', CID, ['stage=Committee Review'], 'tester', TODAY)
        # Moving back is always allowed.
        ops.set_fields(store, 'pipeline', CID, ['stage=Evidence Gathering'], 'tester', TODAY)
        stages = [(e['old'], e['new']) for e in store['audit'] if e['field'] == 'stage']
        self.assertEqual(stages[-1], ('Candidate Comparison', 'Evidence Gathering'))

    def test_incomplete_candidate_cannot_advance(self):
        store = fresh()
        ops.set_fields(store, 'pipeline', CID, ['owner='], 'tester', TODAY)
        with self.assertRaises(ops.OpError) as ctx:
            ops.advance(store, CID, 'tester', TODAY)
        self.assertIn('FAIL — INCOMPLETE', str(ctx.exception))

    def test_explicit_target_and_closed(self):
        store = fresh()
        with self.assertRaises(ops.OpError):
            ops.advance(store, CID, 'tester', TODAY, target='Intake')
        ops.advance(store, CID, 'tester', TODAY, target='closed')  # gate at Intake passes
        with self.assertRaises(ops.OpError):
            ops.set_fields(store, 'pipeline', CID, ['stage=Intake'], 'tester', TODAY)
        with self.assertRaises(ops.OpError):
            ops.advance(store, CID, 'tester', TODAY)


if __name__ == '__main__':
    unittest.main()

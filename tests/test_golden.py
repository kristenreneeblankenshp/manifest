"""Golden test: the engine reproduces every cached formula result in the v0.4 workbook.

The workbook was last calculated with TODAY() = 2026-08-24 (its candidate intake date);
evaluating the engine as of that date must reproduce every calculated and linked cell.
"""

import datetime as dt
import unittest
import warnings
from pathlib import Path

from manifest_workbench import schema as S
from manifest_workbench import store as ST
from manifest_workbench.engine import Workbench

SPEC = (Path(__file__).resolve().parent.parent / 'spec' /
        'Manifest_Workbench_CISC-001_MOPS-003_RCC-004_MASR_Registry_Candidate_Pipeline_v0_4.xlsx')
CALC_DATE = dt.date(2026, 8, 24)

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None


def _norm(v):
    if v is None or v == '':
        return ''
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _equal(a, b):
    a, b = _norm(a), _norm(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


@unittest.skipUnless(openpyxl and SPEC.exists(), 'openpyxl and the v0.4 workbook are required')
class GoldenWorkbookTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from manifest_workbench.xlsx_import import import_workbook
        cls.store, cls.problems = import_workbook(SPEC)
        cls.wb = Workbench(cls.store, CALC_DATE)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            cls.xl = openpyxl.load_workbook(SPEC, data_only=True)

    def test_import_is_clean(self):
        self.assertEqual(self.problems, [])
        counts = {k: len(self.store[k]) for k in ST.TABLE_KEYS}
        self.assertEqual(counts, {'portfolio': 47, 'conviction': 47, 'pew004': 20, 'evidence': 0,
                                  'miar': 47, 'review': 0, 'masr': 56, 'pipeline': 10})

    def test_bundled_seed_matches_workbook(self):
        seed = ST.seed_store()
        for key in ST.TABLE_KEYS:
            self.assertEqual(seed[key], self.store[key], key)

    def test_every_calculated_cell(self):
        checked, mismatches = 0, []
        for table in S.TABLES.values():
            ws = self.xl[table.sheet]
            for offset, row in enumerate(self.wb.table(table.name)):
                excel_row = table.first_row + offset
                for f in table.fields:
                    if f.kind not in (S.AUTO, S.LINK):
                        continue
                    checked += 1
                    expected = ws[f'{f.col}{excel_row}'].value
                    if not _equal(row.get(f.key), expected):
                        mismatches.append(f'{table.sheet}!{f.col}{excel_row} ({f.key}): '
                                          f'{row.get(f.key)!r} != {expected!r}')
        self.assertGreater(checked, 3000)
        self.assertEqual(mismatches, [])

    def _cells(self, sheet, expected):
        ws = self.xl[sheet]
        for cell, value in expected.items():
            with self.subTest(sheet=sheet, cell=cell):
                self.assertTrue(_equal(value, ws[cell].value), f'{cell}: {value!r} != {ws[cell].value!r}')

    def test_rcc004_control_center(self):
        d = self.wb.rcc004()
        s = d['state']
        expected = {
            'A7': s['records_loaded'], 'E7': s['certified_holdings'], 'I7': s['approved_non_holdings'],
            'M7': s['active_candidates'], 'Q7': s['pew_referrals'], 'U7': s['control_exceptions'],
            'A13': s['readiness'], 'G13': s['capacity'], 'M13': s['stage_gates'], 'S13': s['routing'],
        }
        for i, c in enumerate(d['controls']):
            expected[f'D{18 + i}'] = c['count']
            expected[f'E{18 + i}'] = c['state']
        for i, (_, n, clear, exc) in enumerate(d['composition']):
            expected.update({f'O{18 + i}': n, f'P{18 + i}': clear, f'Q{18 + i}': exc})
        sheet_stages = ['Intake', 'Evidence Gathering', 'MIAR Review', 'Eligibility Review',
                        'Candidate Comparison', 'Committee Review', 'Referred to PEW-004', 'On Watch']
        by_stage = {st: rest for st, *rest in d['stages']}
        for i, stage in enumerate(sheet_stages):
            n, gate, exc = by_stage[stage]
            expected.update({f'S{18 + i}': n, f'T{18 + i}': gate, f'U{18 + i}': exc})
        self._cells('22 RCC-004 Control Center', expected)

    def test_rcc003_control_center(self):
        d = self.wb.rcc003()
        s = d['state']
        expected = {
            'A7': s['total_records'], 'E7': s['dossiers_complete'], 'I7': s['current'],
            'M7': s['due_overdue'], 'Q7': s['material_events'], 'U7': s['control_exceptions'],
            'A13': s['readiness'], 'G13': s['coverage'], 'M13': s['miar_actions'],
            'S13': s['rcc007_referrals'],
        }
        for i, c in enumerate(d['controls']):
            expected[f'D{18 + i}'] = c['count']
            expected[f'E{18 + i}'] = c['state']
        for i, x in enumerate(d['sleeves']):
            expected.update({f'O{18 + i}': x['records'], f'P{18 + i}': x['complete'],
                             f'Q{18 + i}': x['current'], f'T{18 + i}': x['overdue'],
                             f'V{18 + i}': x['setup_required'], f'W{18 + i}': x['coverage'],
                             f'X{18 + i}': x['primary']})
        self._cells('19 RCC-003 Control Center', expected)

    def test_rcc002_control_center(self):
        s = self.wb.rcc002()['state']
        self._cells('17 RCC-002 Control Center', {
            'A7': s['total_records'], 'E7': s['open'], 'I7': s['critical_high'], 'M7': s['overdue'],
            'Q7': s['unverified'], 'U7': s['referrals_ready'], 'A13': s['readiness'],
            'G13': s['miar_actions'], 'M13': s['thesis_conviction_actions'], 'S13': s['pew_referrals'],
        })

    def test_rcc001_control_center(self):
        d = self.wb.rcc001()
        s = d['state']
        expected = {
            'A7': s['readiness'], 'G7': s['certified_holdings'], 'K7': s['activity_records'],
            'O7': s['conviction_assigned'], 'S7': s['thesis_assigned'],
            'G12': s['mfpdf_research_status'], 'M12': s['control_exceptions'],
        }
        for i, c in enumerate(d['controls']):
            expected[f'C{18 + i}'] = c['count']
            expected[f'D{18 + i}'] = c['state']
        for i, (_, n) in enumerate(d['snapshot']):
            expected[f'K{18 + i}'] = n
        self._cells('16 RCC-001 Control Center', expected)

    def test_portfolio_totals(self):
        t = self.wb.portfolio_totals()
        self._cells('Certified Allocation', {'F53': t['target_total'], 'K53': t['certification']})


if __name__ == '__main__':
    unittest.main()

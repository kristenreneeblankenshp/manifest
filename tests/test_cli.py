"""End-to-end tests of the console commands."""

import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from manifest_workbench import cli


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = str(Path(self.tmp.name) / 'wb.json')
        os.environ['COLUMNS'] = '160'
        self.assertEqual(self.run_cli('init')[0], 0)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv, as_of='2026-09-29'):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(['--data', self.data, '--as-of', as_of, '--no-color', '--by', 'tester',
                             *argv])
        return code, out.getvalue(), err.getvalue()

    def test_init_refuses_overwrite(self):
        code, _, err = self.run_cli('init')
        self.assertEqual(code, 1)
        self.assertIn('already exists', err)
        self.assertEqual(self.run_cli('init', '--force')[0], 0)

    def test_control_centers_render(self):
        for command, expected in (('dashboard', 'DECISIONS REQUIRED THIS WEEK'),
                                  ('rcc001', 'RESEARCH SETUP INCOMPLETE'),
                                  ('rcc002', 'READY — NO RECORDS LOADED'),
                                  ('rcc003', '0 OF 47 COMPLETE'),
                                  ('rcc004', '56 OF 150 SLOTS LOADED'),
                                  ('guide', 'HARD CONTROLS')):
            code, out, _ = self.run_cli(command)
            self.assertEqual(code, 0, command)
            self.assertIn(expected, out, command)
        code, out, _ = self.run_cli('rcc004', as_of='2026-08-24')
        self.assertIn('10 PASS / 0 BLOCKED', out)

    def test_lists_and_views(self):
        code, out, _ = self.run_cli('pipeline', 'list', '--exceptions')
        self.assertEqual(out.count('OVERDUE'), 10)
        code, out, _ = self.run_cli('pipeline', 'list', '--exceptions', as_of='2026-08-24')
        self.assertIn('(no records)', out)
        code, out, _ = self.run_cli('masr', 'list', '--class', 'research')
        self.assertIn('9 record(s) shown', out)
        code, out, _ = self.run_cli('masr', 'show', 'EMR')
        self.assertIn('Emerson Electric Co.', out)
        code, out, _ = self.run_cli('portfolio')
        self.assertIn('Certified 100.00%', out)
        code, out, _ = self.run_cli('portfolio', 'sleeves')
        self.assertIn('100.00%', out)
        code, out, _ = self.run_cli('lists', 'candidate-stage')
        self.assertIn('Referred to PEW-004', out)
        code, out, _ = self.run_cli('masr', 'fields')
        self.assertIn('market_cap', out)
        code, _, err = self.run_cli('masr', 'show', 'NOPE')
        self.assertEqual(code, 1)
        self.assertIn('No MASR registry record', err)

    def test_edit_advance_history_audit(self):
        code, out, _ = self.run_cli('pipeline', 'set', 'MCP-20260824-002', 'due_date=2026-10-31')
        self.assertEqual(code, 0)
        self.assertIn('OPEN — ON TRACK', out)
        code, out, _ = self.run_cli('pipeline', 'advance', 'MCP-20260824-002')
        self.assertIn('Intake → Evidence Gathering', out)
        code, out, _ = self.run_cli('pipeline', 'history', 'MCP-20260824-002')
        self.assertIn('Evidence Gathering', out)
        code, out, _ = self.run_cli('audit', '--table', 'pipeline')
        self.assertIn('tester', out)
        code, _, err = self.run_cli('portfolio', 'set', 'NVDA', 'target_weight=5%')
        self.assertEqual(code, 1)
        self.assertIn('certified MFPDF data', err)

    def test_add_reports_missing_fields(self):
        code, out, _ = self.run_cli('pipeline', 'add', 'ticker=PWR', 'candidate_type=new')
        self.assertEqual(code, 0)
        self.assertIn('MCP-20260929-001', out)
        self.assertIn('no RCC-004 MASR registry record for PWR', out)
        self.assertIn('Missing required: source (H), owner (AA), due_date (AB)', out)

    def test_every_sheet_command_renders(self):
        from manifest_workbench.views import SHEETS
        for sheet, command, _ in SHEETS:
            with self.subTest(sheet=sheet):
                code, out, err = self.run_cli(*command.split())
                self.assertEqual(code, 0, f'{command}: {err}')
                self.assertTrue(out.strip())

    def test_sheet_views(self):
        for command, expected in (('cisc', 'NEXT REVIEW: Monday, Jul 27, 2026'),
                                  ('decision-center', 'DEFER — COMPLETE DATA'),
                                  ('pew', 'READY — NO CANDIDATES'),
                                  ('validation', 'MONITOR — OUTSIDE PREFERRED RANGE'),
                                  ('lab', 'certified baseline preserved'),
                                  ('mandate', 'PEW-001-28'),
                                  ('sleeves', 'SCENARIO TOTAL PASS'),
                                  ('roles', '47 passed'),
                                  ('controls', 'GREEN / STRONG ALIGNMENT'),
                                  ('committee', 'Monte Carlo Enhancement'),
                                  ('dashboard-data', 'Target Weight'),
                                  ('doc', 'freeze-record')):
            code, out, err = self.run_cli(command)
            self.assertEqual(code, 0, err)
            self.assertIn(expected, out, command)
        code, out, _ = self.run_cli('cell', '13 Validation', 'J12')
        self.assertIn("'NOT READY'", out)
        code, _, err = self.run_cli('cell', '07', 'A6')
        self.assertEqual(code, 1)
        self.assertIn('not a formula cell', err)

    def test_operating_edits(self):
        code, out, _ = self.run_cli('decisions', 'add', 'decision=Review MU', 'committee_decision=yes',
                                    'status=open')
        self.assertIn('DC-004', out)
        code, out, _ = self.run_cli('decision-center')
        self.assertIn('Manual Committee Decisions       1', out)
        code, out, _ = self.run_cli('scenario', 'set', 'NVDA', 'scenario_weight=4.5%', 'rationale=test')
        self.assertIn('BAND EXCEPTION — COMMITTEE DECISION', out)
        code, out, _ = self.run_cli('controls', 'set', 'previous_week_score=0.7')
        self.assertIn('-0.08', out)
        code, _, err = self.run_cli('mandate', 'set', 'PEW-001-09', 'status=PASS')
        self.assertEqual(code, 1)
        self.assertIn('calculated by formula', err)
        code, out, _ = self.run_cli('intel-review', 'add', 'symbol=MU', 'reason=Memory cycle')
        code, out, _ = self.run_cli('cisc')
        self.assertIn('MU — Memory cycle', out)
        code, out, _ = self.run_cli('intel-review', 'clear', '1')
        self.assertIn('Cleared', out)

    def test_export(self):
        path = Path(self.tmp.name) / 'pipeline.csv'
        code, out, _ = self.run_cli('pipeline', 'export', str(path))
        self.assertEqual(code, 0)
        with open(path, encoding='utf-8-sig') as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0][0], 'Candidate ID (A)')
        self.assertEqual(len(rows), 11)
        jpath = Path(self.tmp.name) / 'masr.json'
        self.run_cli('masr', 'export', str(jpath))
        data = json.loads(jpath.read_text(encoding='utf-8'))
        self.assertEqual(len(data), 56)
        self.assertEqual(data[0]['control_status'], 'SETUP REQUIRED')

    def test_interactive_shell(self):
        script = io.StringIO('help\nas-of 2026-08-24\nrcc004\nbogus\nquit\n')
        out = io.StringIO()
        old_stdin = os.sys.stdin
        try:
            os.sys.stdin = script
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(['--data', self.data, '--no-color'])
        finally:
            os.sys.stdin = old_stdin
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertIn('CHIEF INVESTMENT STEWARD CONSOLE (CISC)', text)
        self.assertIn('5 · MANIFEST DECISION CENTER', text)
        self.assertIn('Evaluating as of 2026-08-24', text)
        self.assertIn('10 PASS / 0 BLOCKED', text)


if __name__ == '__main__':
    unittest.main()

"""MWIR: the model ported from the browser builder, the PDF and the console workspace."""

import datetime as dt
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from manifest_workbench import mwir as M
from manifest_workbench import reports as RP
from manifest_workbench import store as ST

from .test_web import HAVE_WEB, WebTestCase

try:
    import reportlab  # noqa: F401
    HAVE_PDF = True
except ImportError:  # pragma: no cover
    HAVE_PDF = False


def model(doc=None, store=None):
    return M.model(doc or M.seed_doc(), M.snapshot(store or ST.seed_store()))


class BuilderParityTest(unittest.TestCase):
    """The same expectations as mwir/test.js."""

    def test_bands(self):
        self.assertEqual(M.band(3.49), '2.62–4.00%')
        self.assertEqual(M.band(1.85), '1.39–2.31%')
        self.assertEqual(M.band(1.2), '1.00–1.50%')
        self.assertEqual(M.band(3.02), '2.27–3.77%')  # JavaScript toFixed rounding

    def test_csv_import_converts_decimal_weights(self):
        store, doc = ST.seed_store(), M.seed_doc()
        msg, ok = M.import_csv(store, doc, 'Date,Symbol,Weights,,note\n9/25/2026,COST,0.6,,"a, quoted"\n'
                                           '9/25/2026,NEWCO,0.4,,\n,,,,\n')
        self.assertEqual([(h['ticker'], h['current'], h['sleeve']) for h in doc['holdings']],
                         [('COST', '60', 'Strategic'), ('NEWCO', '40', 'Unassigned')])
        self.assertEqual((doc['weekEnding'], doc['pubDate']), ('2026-09-25', '2026-09-28'))
        self.assertFalse(ok)
        self.assertIn('set sleeve + rationale): NEWCO', msg)
        self.assertRegex(msg, r'Dropped vs prior: .*JNJ')

    def test_zacks_screen(self):
        zk = model()['zk']
        self.assertEqual(zk['counts'], {'TIER 1': 6, 'PASS': 28, 'REVIEW': 5, 'ETF': 6, 'NO DATA': 0})
        self.assertIn('CME (cap $95.10B, Rank 4 Sell)', zk['review_text'])
        self.assertIn('MMC is listed by Zacks as MRSH', zk['alias_text'])

    def test_controls_fail_until_total_is_100(self):
        store, doc = ST.seed_store(), M.seed_doc()
        v = M.model(doc, M.snapshot(store))
        self.assertFalse(v['stats']['total_ok'])
        self.assertEqual(v['cert']['label'], 'HOLD · CONTROLS FAILING')
        M.import_csv(store, doc, 'Date,Symbol,Weights\n9/25/2026,COST,0.5\n9/25/2026,JNJ,0.5\n')
        self.assertTrue(M.model(doc, M.snapshot(store))['stats']['total_ok'])

    def test_gauge_and_assertions(self):
        v = model()
        self.assertEqual((v['zone']['value'], v['zone']['label']), (62, 'YELLOW · NEUTRAL / RISK CONTROL'))
        self.assertEqual([a['result'] for a in v['assertions']][:7],
                         ['45 / PASS', '96.99% / FAIL', '22.52% / PASS', '0 / PASS', '0 / PASS', '0 / PASS',
                          '5 / REVIEW'])
        self.assertEqual(len(v['matrix_pages'][0]['rows']), 23)


class ImportTest(unittest.TestCase):
    def test_import_json_normalises_untrusted_input(self):
        doc = M.import_json(json.dumps({'headline': 7, 'holdings': [{'ticker': 'cost', 'current': 3.5}, 'junk'],
                                        'components': [{'name': 'Growth', 'score': 5}], 'evil': 'x'}))
        self.assertEqual(doc['headline'], '7')
        self.assertEqual(doc['holdings'], [{'ticker': 'COST', 'sleeve': '', 'mfpdf': '', 'current': '3.5',
                                            'guidance': '', 'rationale': '', 'status': ''}])
        self.assertNotIn('evil', doc)
        M.model(doc, M.bundled_snapshot())  # renders without error
        with self.assertRaises(ValueError):
            M.import_json('{"headline": "no holdings"}')


class WorkbenchIntegrationTest(unittest.TestCase):
    def test_new_tickers_filled_from_certified_portfolio(self):
        store, doc = ST.seed_store(), M.seed_doc()
        msg, ok = M.import_csv(store, doc, 'Date,Symbol,Weights\n9/25/2026,COST,0.97\n9/25/2026,PFF,0.03\n')
        pff = doc['holdings'][1]
        self.assertEqual((pff['sleeve'], pff['mfpdf']), ('Income', '3.02'))
        self.assertTrue(pff['rationale'])
        self.assertTrue(ok)
        self.assertIn('filled from the certified portfolio: PFF', msg)

    def test_strategic_target_and_baseline(self):
        store = ST.seed_store()
        self.assertEqual(M.strategic_target(store), '22.51')
        doc = M.seed_doc()
        doc['holdings'][0]['mfpdf'] = '9.99'
        self.assertGreaterEqual(M.fill_baseline(store, doc), 1)
        self.assertEqual(doc['holdings'][0]['mfpdf'], '3.02')

    def test_upcoming_earnings_become_event_gates(self):
        store, doc = ST.seed_store(), M.seed_doc()
        doc['pubDate'] = '2026-09-28'
        events = M.upcoming_events(store, doc)
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].startswith('SEP 30 | Micron'))

    def test_weekly_drafts_carry_forward(self):
        store = ST.seed_store()
        first = RP.create_draft(store, 'mwir', 'Ada', dt.date(2026, 9, 29))
        self.assertEqual((first['doc']['weekEnding'], first['doc']['pubDate']), ('2026-09-25', '2026-09-28'))
        self.assertEqual(first['period_label'], 'Week ending Sep 25, 2026')
        first['doc']['headline'] = 'CARRIED HEADLINE'
        nxt = RP.create_draft(store, 'mwir', 'Ada', dt.date(2026, 10, 6))
        self.assertEqual(nxt['doc']['headline'], 'CARRIED HEADLINE')
        self.assertEqual(nxt['doc']['weekEnding'], '2026-10-02')
        self.assertEqual(nxt['doc']['gatesWeek'], 'WEEK OF OCT 5')

    @unittest.skipUnless(HAVE_PDF, 'reportlab not installed')
    def test_issue_requires_override_when_controls_fail(self):
        store = ST.seed_store()
        draft = RP.create_draft(store, 'mwir', 'Ada', dt.date(2026, 9, 29))
        out = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(ValueError, 'override reason'):
            RP.issue(store, draft['id'], 'Ada', dt.date(2026, 9, 29), out)
        issued = RP.issue(store, draft['id'], 'Ada', dt.date(2026, 9, 29), out, override='Committee accepted')
        self.assertEqual(issued['certification'], 'HOLD · CONTROLS FAILING')
        self.assertEqual(issued['zacks']['as_of'], '2026-09-25')
        self.assertTrue((out / issued['files'][-1]['file']).read_bytes().startswith(b'%PDF'))
        pub = next(p for p in store['publications'] if p and p.get('publication') == 'MWIR')
        self.assertEqual(pub['latest_issue'], 'Week ending Sep 25, 2026 (v1)')


@unittest.skipUnless(HAVE_PDF, 'reportlab not installed')
class PdfTest(unittest.TestCase):
    def test_eight_landscape_pages(self):
        from manifest_workbench.mwir_pdf import render
        path = Path(tempfile.mkdtemp()) / 'mwir.pdf'
        doc = M.seed_doc()
        doc['clientBrief'] = 'Long text ≤ with unicode → ' * 60  # shrinks to fit, no crash
        render({'doc': doc}, path, final=False, snap=M.bundled_snapshot())
        data = path.read_bytes()
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertEqual(len(re.findall(rb'/Type /Page\b', data)), 8)
        self.assertIn(b'/MediaBox [ 0 0 792 612 ]', data)


@unittest.skipUnless(HAVE_WEB, 'web extras not installed')
class WorkspaceTest(WebTestCase):
    def start(self):
        r = self.post('/mwir/start')
        self.assertEqual(r.status_code, 302)
        return r.headers['Location'].rsplit('/', 1)[-1]

    def test_index_then_start(self):
        html = self.c.get('/mwir').get_data(as_text=True)
        self.assertIn("Start this week", html)
        rid = self.start()
        self.assertEqual(rid, 'mwir-2026-W40')
        self.assertEqual(self.c.get('/mwir').headers['Location'], f'/mwir/{rid}')
        page = self.c.get(f'/mwir/{rid}').get_data(as_text=True)
        self.assertIn('HOLD · CONTROLS FAILING', page)
        pages = self.c.get(f'/mwir/{rid}/pages').get_data(as_text=True)
        self.assertEqual(pages.count('class="sheet'), 8)

    def test_autosave_returns_status(self):
        rid = self.start()
        doc = self.store()['reports'][rid]['doc']
        form = {'headline': 'NEW HEADLINE', 'composite': '74', 'h_count': str(len(doc['holdings']))}
        for i, h in enumerate(doc['holdings']):
            form.update({f'h_{i}_{k}': h[k] for k in M.HOLDING_FIELDS})
        form['h_0_remove'] = '1'
        r = self.post(f'/mwir/{rid}/save', form, headers={'X-Requested-With': 'fetch'})
        j = r.get_json()
        self.assertTrue(j['ok'])
        self.assertIn('GREEN · CONSTRUCTIVE', j['status_html'])
        saved = self.store()['reports'][rid]['doc']
        self.assertEqual(saved['headline'], 'NEW HEADLINE')
        self.assertEqual(len(saved['holdings']), len(doc['holdings']) - 1)

    def test_holdings_upload_and_issue(self):
        rid = self.start()
        doc = self.store()['reports'][rid]['doc']
        total = sum(float(h['current']) for h in doc['holdings'])
        csv_text = 'Date,Symbol,Weights\n' + ''.join(
            f"9/25/2026,{h['ticker']},{float(h['current']) / total:.6f}\n" for h in doc['holdings'])
        r = self.c.post(f'/mwir/{rid}/holdings', data={'_csrf': self.token(),
                                                        'file': (io.BytesIO(csv_text.encode()), 'holdings.csv')},
                        content_type='multipart/form-data', follow_redirects=True)
        self.assertIn('Loaded 45 holdings', r.get_data(as_text=True))
        # strategic anchors now differs from the frozen total, so issuing needs an override
        r = self.post(f'/mwir/{rid}/issue', follow_redirects=True)
        self.assertIn('override reason', r.get_data(as_text=True))
        self.assertEqual(self.store()['reports'][rid]['status'], 'Draft')
        self.post(f'/mwir/{rid}/issue', {'override': 'Normalized file accepted by committee'})
        issued = self.store()['reports'][rid]
        self.assertEqual((issued['status'], issued['version']), ('Issued', 1))
        f = self.c.get(f"/reports/{rid}/file/{issued['files'][-1]['file']}")
        self.assertTrue(f.data.startswith(b'%PDF'))
        f.close()
        # the weekly review's MWIR item now passes
        review = self.post('/reviews/start/weekly').headers['Location']
        self.assertIn('Issued', self.c.get(review).get_data(as_text=True))
        # issued documents are frozen
        r = self.post(f'/mwir/{rid}/save', {'headline': 'x'}, follow_redirects=True)
        self.assertIn('Reopen it to revise', r.get_data(as_text=True))

    def test_export_import_and_events(self):
        rid = self.start()
        exported = self.c.get(f'/mwir/{rid}/export.json').get_json()
        exported['doc']['headline'] = 'FROM THE BROWSER BUILDER'
        builder_state = json.dumps(exported['doc'])  # the builder's localStorage value is the bare doc
        self.c.post(f'/mwir/{rid}/import-json', data={'_csrf': self.token(),
                                                       'file': (io.BytesIO(builder_state.encode()), 'mwir.json')},
                    content_type='multipart/form-data')
        self.assertEqual(self.store()['reports'][rid]['doc']['headline'], 'FROM THE BROWSER BUILDER')
        self.post(f'/mwir/{rid}/events')
        self.assertIn('Micron', self.store()['reports'][rid]['doc']['events'])
        pdf = self.c.get(f'/mwir/{rid}/draft.pdf')
        self.assertTrue(pdf.data.startswith(b'%PDF'))
        pdf.close()

    def test_viewer_cannot_edit(self):
        rid = self.start()
        self.post('/settings/users', {'username': 'val', 'name': 'Val', 'password': 'correct-horse-battery',
                                      'role': 'viewer'})
        viewer = self.app.test_client()
        self.login(viewer, 'val')
        self.assertIn('disabled', viewer.get(f'/mwir/{rid}').get_data(as_text=True))
        self.assertEqual(self.post(f'/mwir/{rid}/save', {'headline': 'x'}, client=viewer).status_code, 403)


@unittest.skipUnless(HAVE_WEB, 'web extras not installed')
class NavigationTest(WebTestCase):
    def test_sidebar_hubs_and_jump(self):
        html = self.c.get('/t/miar').get_data(as_text=True)
        side = html.split('class="nav"')[1].split('</nav>')[0]
        self.assertLessEqual(side.count('<a '), 14)  # was 27 before the hubs
        self.assertIn('aria-current="page">Research', side)
        sub = html.split('class="subnav"')[1].split('</nav>')[0]
        self.assertIn('class="on">MIAR registry', sub)
        self.assertIn('data-url="/t/masr"', html)  # quick jump reaches every table
        self.assertIn('Step 5', self.c.get('/').get_data(as_text=True))

    def test_every_jump_target_opens(self):
        from manifest_workbench.web.nav import jump_targets
        with self.app.test_request_context():
            targets = jump_targets()
        for label, url in targets:
            self.assertEqual(self.c.get(url, follow_redirects=True).status_code, 200, url)


if __name__ == '__main__':
    unittest.main()

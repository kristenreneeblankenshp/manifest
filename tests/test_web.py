"""End-to-end tests for the hosted web app (Flask test client, temporary data directory).

Skipped when the optional web dependencies (flask, reportlab) are not installed.
"""

import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import flask  # noqa: F401
    import reportlab  # noqa: F401
    HAVE_WEB = True
except ImportError:  # pragma: no cover
    HAVE_WEB = False

if HAVE_WEB:
    from manifest_workbench import schema as S
    from manifest_workbench.connectors import research
    from manifest_workbench import reviews as RV
    from manifest_workbench.engine import Workbench
    from manifest_workbench.web import create_app

PASSWORD = 'correct-horse-battery'
AS_OF = '2026-09-29'
CID = 'MCP-20260824-001'


def csrf(html):
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    return m.group(1) if m else ''


@unittest.skipUnless(HAVE_WEB, 'web extras not installed')
class WebTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.app = create_app(self.dir, testing=True)
        self.c = self.app.test_client()
        page = self.c.get('/setup').get_data(as_text=True)
        r = self.c.post('/setup', data={'_csrf': csrf(page), 'name': 'Ada Admin', 'username': 'ada',
                                        'password': PASSWORD, 'confirm': PASSWORD})
        self.assertEqual(r.status_code, 302)
        self.login(self.c, 'ada')
        self.post('/as-of', {'as_of': AS_OF})

    def login(self, client, user, password=PASSWORD):
        page = client.get('/login').get_data(as_text=True)
        r = client.post('/login', data={'_csrf': csrf(page), 'username': user, 'password': password})
        self.assertEqual(r.status_code, 302, 'login failed')

    def token(self, client=None):
        return csrf((client or self.c).get('/').get_data(as_text=True))

    def post(self, url, data=None, client=None, **kw):
        client = client or self.c
        data = dict(data or {}, _csrf=self.token(client))
        return client.post(url, data=data, **kw)

    def store(self):
        return self.app.extensions['repo'].read()

    def assertFlash(self, text, contains):
        self.assertIn(contains, text)


class AuthTest(WebTestCase):
    def test_anonymous_redirected_to_login(self):
        anon = self.app.test_client()
        r = anon.get('/decisions')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login', r.headers['Location'])

    def test_login_and_setup_need_form_token(self):
        anon = self.app.test_client()
        r = anon.post('/login', data={'username': 'ada', 'password': PASSWORD})
        self.assertEqual(r.status_code, 400)
        fresh = create_app(tempfile.mkdtemp(), testing=True).test_client()
        r = fresh.post('/setup', data={'name': 'X', 'username': 'x', 'password': PASSWORD, 'confirm': PASSWORD})
        self.assertEqual(r.status_code, 400)

    def test_health_check_is_public(self):
        r = self.app.test_client().get('/healthz')
        self.assertEqual((r.status_code, r.get_json()), (200, {'status': 'ok'}))

    def test_setup_closed_after_first_admin(self):
        r = self.app.test_client().get('/setup')
        self.assertEqual(r.status_code, 302)

    def test_bad_password_rejected(self):
        anon = self.app.test_client()
        page = anon.get('/login').get_data(as_text=True)
        r = anon.post('/login', data={'_csrf': csrf(page), 'username': 'ada', 'password': 'wrong-password'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('/login', anon.get('/').headers['Location'])

    def test_post_without_csrf_rejected(self):
        r = self.c.post('/decisions/new', data={'decision': 'x'})
        self.assertEqual(r.status_code, 400)

    def test_viewer_is_read_only(self):
        self.post('/settings/users', {'username': 'val', 'name': 'Val Viewer', 'password': PASSWORD,
                                      'role': 'viewer'})
        viewer = self.app.test_client()
        self.login(viewer, 'val')
        self.assertEqual(viewer.get('/decisions').status_code, 200)
        r = self.post('/decisions/new', {'decision': 'Should not save'}, client=viewer)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(viewer.get('/settings').status_code, 403)

    def test_redirects_stay_on_site(self):
        for target in ('//evil.example', '/\\evil.example', 'https://evil.example'):
            r = self.post('/as-of', {'as_of': AS_OF, 'next': target})
            self.assertEqual(r.headers['Location'], '/', target)
        r = self.post('/as-of', {'as_of': AS_OF, 'next': '/pipeline'})
        self.assertEqual(r.headers['Location'], '/pipeline')

    def test_admin_cannot_remove_self(self):
        self.post('/settings/users', {'username': 'ada', 'remove': '1'})
        self.assertIn('ada', self.store()['users'])


class PagesTest(WebTestCase):
    def test_every_page_renders(self):
        pages = ['/', '/decisions', '/actions', '/pipeline', '/research', '/intel', '/controls', '/pew',
                 '/lab', '/validation', '/sheets', '/lists', '/audit', '/data', '/settings', '/reviews',
                 '/reports'] + [f'/rcc/{n}' for n in (1, 2, 3, 4)]
        for name, spec in S.TABLES.items():
            pages.append(f'/t/{name}')
            if spec.mode == 'single':
                pages.append(f'/t/{name}/_')
        for url in pages:
            r = self.c.get(url, follow_redirects=True)
            self.assertEqual(r.status_code, 200, url)

    def test_sheet_links_resolve(self):
        html = self.c.get('/sheets').get_data(as_text=True)
        for url in set(re.findall(r'href="(/(?:doc|t|rcc)/[^"#?]*)"', html)):
            self.assertEqual(self.c.get(url, follow_redirects=True).status_code, 200, url)

    def test_record_pages(self):
        self.assertEqual(self.c.get(f'/t/pipeline/{CID}').status_code, 200)
        self.assertEqual(self.c.get('/t/masr/MU').status_code, 200)
        self.assertEqual(self.c.get('/t/evidence/new').status_code, 200)
        self.assertEqual(self.c.get('/t/mandate/new').status_code, 404)


class ClaudeConnectorModeTest(WebTestCase):
    def setUp(self):
        super().setUp()
        self.app.config['CONNECTORS'] = 'claude'

    def test_data_page_offers_connector_pulls(self):
        html = self.c.get('/data').get_data(as_text=True)
        self.assertIn('Zacks Data connector in Claude', html)
        self.assertNotIn('disabled>Pull from Zacks', html)

    def test_server_side_pull_explains_instead_of_failing(self):
        r = self.post('/data/zacks', follow_redirects=True)
        self.assertIn('connector is not available', r.get_data(as_text=True))
        r = self.post('/data/research', follow_redirects=True)
        self.assertIn('connector is not available', r.get_data(as_text=True))


class DecisionsAndActionsTest(WebTestCase):
    def test_add_and_resolve_decision(self):
        self.post('/decisions/new', {'decision': 'Approve MU trim', 'category': 'Portfolio Engineering',
                                     'owner': 'Ada'})
        rows = [r for r in self.store()['decisions'] if r]
        slot = next(i + 1 for i, r in enumerate(self.store()['decisions']) if r.get('decision') == 'Approve MU trim')
        self.assertTrue(rows)
        self.post(f'/decisions/{slot}/resolve', {'status': 'Closed', 'resolution': 'Approved 3-1'})
        row = self.store()['decisions'][slot - 1]
        self.assertEqual(row['status'], 'Closed')
        self.assertEqual(row['resolution'], 'Approved 3-1')
        self.assertIn('Approve MU trim', self.c.get('/decisions').get_data(as_text=True))

    def test_action_item_lifecycle(self):
        self.post('/actions/actions/new', {'action': 'Confirm Q3 weights', 'owner': 'Ada', 'status': 'Open'})
        slot = next(i + 1 for i, r in enumerate(self.store()['actions']) if r.get('action') == 'Confirm Q3 weights')
        self.post(f'/actions/actions/{slot}/status', {'status': 'Completed'})
        self.assertEqual(self.store()['actions'][slot - 1]['status'], 'Completed')
        self.post(f'/actions/actions/{slot}/clear')
        self.assertFalse(self.store()['actions'][slot - 1])


class PipelineTest(WebTestCase):
    def test_advance_and_update(self):
        before = next(r for r in self.store()['pipeline'] if r.get('candidate_id') == CID)['stage']
        r = self.post(f'/pipeline/{CID}/advance', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        after = next(r for r in self.store()['pipeline'] if r.get('candidate_id') == CID)
        self.assertNotEqual(after['stage'], before)
        self.post(f'/pipeline/{CID}/update', {'thesis_summary': 'Committee memo'})
        after = next(r for r in self.store()['pipeline'] if r.get('candidate_id') == CID)
        self.assertEqual(after['thesis_summary'], 'Committee memo')
        # calculated columns cannot be written from the board
        self.post(f'/pipeline/{CID}/update', {'next_action': 'Forged'})
        after = next(r for r in self.store()['pipeline'] if r.get('candidate_id') == CID)
        self.assertNotEqual(after.get('next_action'), 'Forged')
        events = [e for e in self.store()['audit'] if e.get('record') == CID]
        self.assertTrue(any(e['actor'] == 'Ada Admin' for e in events))

    def test_new_candidate(self):
        src = S.PIPELINE.field('source').choices[0]
        r = self.post('/pipeline/new', {'ticker': 'PLTR', 'candidate_type': 'New Candidate', 'source': src,
                                        'owner': 'Research Committee', 'due_date': '2026-10-15'},
                      follow_redirects=True)
        self.assertIn('created at Intake', r.get_data(as_text=True))
        rec = next(r for r in self.store()['pipeline'] if r.get('ticker') == 'PLTR')
        self.assertEqual(rec['stage'], 'Intake')
        self.assertTrue(rec['candidate_id'].startswith('MCP-20260929-'))


class LabTest(WebTestCase):
    def test_scenario_save_keeps_certified(self):
        store = self.store()
        syms = [r['symbol'] for r in store['portfolio']][:2]
        targets = [r['target_weight'] for r in store['portfolio']][:2]
        self.post('/lab', {f'w_{syms[0]}': f'{(targets[0] + 0.005) * 100:.2f}%', f'r_{syms[0]}': 'Add',
                           f'w_{syms[1]}': f'{(targets[1] - 0.005) * 100:.2f}%', f'r_{syms[1]}': 'Fund',
                           'scenario_id': 'PEW-SCN-002', 'scenario_name': 'Rotation', 'prepared_date': AS_OF})
        after = self.store()
        self.assertAlmostEqual(after['scenario'][0]['scenario_weight'], targets[0] + 0.005, places=6)
        self.assertEqual([r['target_weight'] for r in after['portfolio']][:2], targets)
        html = self.c.get('/lab').get_data(as_text=True)
        self.assertIn('Rotation', html)


class DataTest(WebTestCase):
    def weights_csv(self):
        syms = [r['symbol'] for r in self.store()['portfolio']]
        lines = ['Account Positions as of 09/29/2026', '', 'Symbol,Description,Quantity,Price,Value']
        lines += [f'"{s.replace(".", "/")}",Security,10,100,"$1,000.00"' for s in syms]
        lines += ['Cash & Money Market,,,,"$500.00"', 'Total,,,,"$47,500.00"']
        return '\n'.join(lines), len(syms)

    def test_weights_upload_preview_then_apply(self):
        text, n = self.weights_csv()
        r = self.c.post('/data/weights', data={'_csrf': self.token(), 'missing_as_zero': 'on',
                                               'file': (io.BytesIO(text.encode()), 'positions.csv')},
                        content_type='multipart/form-data')
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Load these weights', html)
        # nothing written until applied
        self.assertTrue(all(r.get('actual_weight') in (None, '') for r in self.store()['portfolio']))
        token = re.search(r'/data/weights/([\w-]+)"', html).group(1)
        self.post(f'/data/weights/{token}')
        weights = [r.get('actual_weight') for r in self.store()['portfolio']]
        self.assertTrue(all(isinstance(w, float) for w in weights))
        self.assertAlmostEqual(sum(weights), 1.0, places=4)
        # token is single use
        r = self.post(f'/data/weights/{token}', follow_redirects=True)
        self.assertIn('expired', r.get_data(as_text=True))

    def test_zacks_csv_upload(self):
        def upload(rank):
            csv_text = f'Ticker,Company Name,Zacks Rank,Market Cap (mil)\nMU,Micron,{rank},120000\n'
            return self.c.post('/data/zacks', data={'_csrf': self.token(),
                                                    'file': (io.BytesIO(csv_text.encode()), 'screen.csv')},
                               content_type='multipart/form-data', follow_redirects=True)
        self.assertIn('0 rank changes', upload('3-Hold').get_data(as_text=True))  # first load is a baseline
        r = upload('5-Strong Sell')
        self.assertIn('1 rank changes', r.get_data(as_text=True))
        mu = next(r for r in Workbench(self.store()).masr if r.get('ticker') == 'MU')
        self.assertEqual(mu['zacks_rank'], 5)
        self.assertTrue(any(e.get('activity_type') == 'Zacks Rank Change' and e.get('ticker') == 'MU'
                            for e in self.store()['evidence']))

    def test_zacks_api_without_config_reports_error(self):
        r = self.post('/data/zacks', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Settings', r.get_data(as_text=True))

    def test_research_pull_and_triage(self):
        feed = ('<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                '<title>8-K - Current report</title><updated>2026-09-28T16:00:00-04:00</updated>'
                '<link href="https://www.sec.gov/Archives/{t}/8k.htm"/><category term="8-K"/>'
                '<summary>Results of operations</summary></entry></feed>')
        real = research.run

        def fake_run(store, actor, today, days=7):
            return real(store, actor, today, get=lambda url, h: feed.replace('{t}', re.search(r'CIK=(\w+)', url).group(1)),
                        days=days, tickers=['MU', 'MSFT'])
        self.post('/settings', {'sec_contact': 'ops@example.com'})
        with mock.patch.object(research, 'run', fake_run):
            self.post('/data/research', {'days': '7'})
        inbox = self.store()['inbox']
        self.assertEqual(len(inbox), 2)
        first, second = inbox
        page = self.c.get(f"/data/inbox/{first['id']}/evidence").get_data(as_text=True)
        self.assertIn('8-K', page)
        self.post(f"/data/inbox/{second['id']}/dismiss")
        self.assertEqual(self.store()['inbox'][1]['status'], 'Dismissed')


class ReviewsTest(WebTestCase):
    def test_weekly_review_flow(self):
        r = self.post('/reviews/start/weekly')
        self.assertEqual(r.status_code, 302)
        rid = r.headers['Location'].rsplit('/', 1)[-1]
        self.assertEqual(self.c.get(f'/reviews/{rid}').status_code, 200)
        # a failing auto-check needs a note to confirm
        self.post(f'/reviews/{rid}/item/weights', {'done': '1'})
        self.assertFalse(self.store()['reviews'][rid]['items'].get('weights', {}).get('done'))
        self.post(f'/reviews/{rid}/item/weights', {'done': '1', 'note': 'Broker file delayed; loading Monday'})
        self.assertTrue(self.store()['reviews'][rid]['items']['weights']['done'])
        # cannot sign off with open items
        self.post(f'/reviews/{rid}/signoff')
        self.assertEqual(self.store()['reviews'][rid]['status'], 'In Progress')
        # confirm everything (with exception notes), then sign off and reopen
        for key in [i.key for i in RV.CHECKLISTS[RV.WEEKLY]]:
            self.post(f'/reviews/{rid}/item/{key}', {'done': '1', 'note': 'Reviewed in committee'})
        self.post(f'/reviews/{rid}/signoff', {'notes': 'All clear'})
        review = self.store()['reviews'][rid]
        self.assertEqual(review['status'], 'Completed')
        self.assertEqual(review['signed_by'], 'Ada Admin')
        self.post(f'/reviews/{rid}/reopen', {'reason': ''})
        self.assertEqual(self.store()['reviews'][rid]['status'], 'Completed')
        self.post(f'/reviews/{rid}/reopen', {'reason': 'Late broker file'})
        self.assertEqual(self.store()['reviews'][rid]['status'], 'In Progress')


class ReportsTest(WebTestCase):
    def test_draft_edit_issue(self):
        r = self.post('/reports/new/mor')
        self.assertEqual(r.status_code, 302)
        rid = r.headers['Location'].rsplit('/', 1)[-1]
        draft = self.store()['reports'][rid]
        key = draft['sections'][0]['key']
        form = {'title': draft['title'], 'subtitle': 'Edited subtitle', f'n_{key}': 'Hand-written summary.'}
        form.update({f"i_{s['key']}": 'on' for s in draft['sections']})
        self.post(f'/reports/{rid}/save', form)
        self.assertEqual(self.store()['reports'][rid]['sections'][0]['narrative'], 'Hand-written summary.')
        # refresh keeps the edit
        self.post(f'/reports/{rid}/refresh')
        self.assertEqual(self.store()['reports'][rid]['sections'][0]['narrative'], 'Hand-written summary.')
        self.post(f'/reports/{rid}/section', {'title': 'Committee note', 'narrative': 'Added by hand.'})
        self.assertIn('Added by hand.', self.c.get(f'/reports/{rid}/preview').get_data(as_text=True))
        pdf = self.c.get(f'/reports/{rid}/draft.pdf')
        self.assertTrue(pdf.data.startswith(b'%PDF'))
        pdf.close()
        self.post(f'/reports/{rid}/issue')
        issued = self.store()['reports'][rid]
        self.assertEqual(issued['status'], 'Issued')
        name = issued['files'][-1]['file']
        self.assertTrue((Path(self.dir) / 'reports' / name).exists())
        f = self.c.get(f'/reports/{rid}/file/{name}')
        self.assertTrue(f.data.startswith(b'%PDF'))
        f.close()
        pubs = [p for p in self.store()['publications'] if p and str(p.get('publication', '')) == 'MOR']
        self.assertTrue(any(p.get('status') == 'Published' and p.get('last_published') == AS_OF for p in pubs))

    def test_all_report_types_build(self):
        for kind in ('mwir', 'mird', 'mor', 'qer', 'mipr'):
            r = self.post(f'/reports/new/{kind}')
            self.assertEqual(r.status_code, 302, kind)
            rid = r.headers['Location'].rsplit('/', 1)[-1]
            self.assertEqual(self.c.get(f'/reports/{rid}', follow_redirects=True).status_code, 200, kind)
            pdf = self.c.get(f'/reports/{rid}/draft.pdf')
            self.assertTrue(pdf.data.startswith(b'%PDF'), kind)
            pdf.close()


if __name__ == '__main__':
    unittest.main()

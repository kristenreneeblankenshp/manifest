"""Bridge between the in-Claude page and the workbench web app running in Pyodide.

The page (``index.html``) loads Python in the browser, unpacks this app, and routes every
navigation, form post and fetch from the rendered pages through :func:`request`. Zacks and
research pulls are fetched by the page through the viewer's Claude connectors and applied here
with the same code the hosted app uses for API and CSV pulls.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import secrets
from urllib.parse import urlsplit

os.environ.setdefault('MANIFEST_DATA_DIR', '/data')
os.environ['MANIFEST_CONNECTORS'] = 'claude'

from werkzeug.datastructures import FileStorage, MultiDict  # noqa: E402

from manifest_workbench import mwir as MW  # noqa: E402
from manifest_workbench.connectors import research, zacks  # noqa: E402
from manifest_workbench.web import create_app  # noqa: E402
from manifest_workbench.web.auth import set_user  # noqa: E402

DATA = os.environ['MANIFEST_DATA_DIR']
USER = 'steward'
_app = None
_client = None


def boot(name: str = '') -> str:
    """Create the app over /data (seeding it on first use) and sign the viewer in."""
    global _app, _client
    _app = create_app(DATA)
    name = (name or '').strip() or 'Chief Investment Steward'
    with _app.extensions['repo'].transaction() as store:
        user = store['users'].get(USER)
        if user is None or user.get('name') != name or user.get('role') != 'admin':
            set_user(store, USER, None, 'admin', name)
            # signed in by the page, never by password: no usable password exists
            store['users'][USER].setdefault('password_hash', '!signed-in-by-claude')
    _client = _app.test_client()
    _sign_in()
    return name


def _sign_in():
    with _client.session_transaction() as session:
        session['user'] = USER
        session.permanent = True
        session.setdefault('_csrf', secrets.token_urlsafe(32))


def _actor() -> str:
    return _app.extensions['repo'].read()['users'][USER]['name']


def _today() -> dt.date:
    with _client.session_transaction() as session:
        raw = session.get('as_of')
    try:
        return dt.date.fromisoformat(raw) if raw else dt.date.today()
    except ValueError:
        return dt.date.today()


def request(method: str, url: str, fields=None, files=None, headers=None) -> dict:
    """Run one HTTP request through the app. Returns status, content type, final path and body."""
    data = None
    if method.upper() != 'GET':
        data = MultiDict()
        for key, value in fields or []:
            data.add(str(key), str(value))
        for key, filename, content, ctype in files or []:
            data.add(str(key), FileStorage(io.BytesIO(bytes(content)), filename=str(filename),
                                           content_type=str(ctype or 'application/octet-stream')))
    resp = _client.open(url, method=method.upper(), data=data, headers=dict(headers or {}),
                        follow_redirects=True)
    path = resp.request.path
    if path in ('/login', '/setup'):  # signed out (e.g. Sign out was pressed): sign back in
        _sign_in()
        target = url if method.upper() == 'GET' and urlsplit(url).path not in ('/login', '/setup') else '/'
        return request('GET', target)
    query = resp.request.query_string.decode()
    fragment = ''
    for hop in resp.history:
        loc = hop.headers.get('Location', '')
        fragment = urlsplit(loc).fragment if '#' in loc else ''
    return {'status': resp.status_code, 'ctype': resp.content_type or '', 'path': path + ('?' + query if query else ''),
            'fragment': fragment, 'disposition': resp.headers.get('Content-Disposition', ''),
            'body': resp.get_data()}


# --------------------------------------------------------------------------- connectors

def universe() -> str:
    """Tickers for connector pulls: equities by Zacks symbol, and the ETFs (not covered by compare_stocks)."""
    store = _app.extensions['repo'].read()
    snap = MW.snapshot(store)
    alias = snap.get('alias') or {}
    etf = {r['symbol'].upper() for r in store['portfolio'] if r.get('security_type') == 'ETF'}
    etf |= {str(r.get('ticker', '')).upper() for r in store['masr'] if r.get('security_type') == 'ETF'}
    tickers = zacks.universe(store)
    equities = [alias.get(t, t) for t in tickers if t not in etf]
    return json.dumps({'equities': equities, 'etfs': [t for t in tickers if t in etf]})


def zacks_apply(results_json: str, errors_json: str = '[]') -> str:
    """Apply {ticker: {rank, market_cap ($B), er}} fetched through the Zacks Data connector."""
    results = {str(k).upper(): {'rank': v.get('rank'), 'market_cap': v.get('market_cap'), 'er': v.get('er')}
               for k, v in json.loads(results_json).items()}
    errors = json.loads(errors_json)
    with _app.extensions['repo'].transaction() as store:
        summary = zacks.apply_and_log(store, _actor(), _today(), results, errors,
                                      f'Zacks Data connector {_today().isoformat()}')
    return json.dumps({'text': summary['text'], 'changes': len(summary['rank_changes']),
                       'errors': summary['errors']})


def research_apply(items_json: str, scope: str, errors_json: str = '[]') -> str:
    with _app.extensions['repo'].transaction() as store:
        summary = research.ingest(store, _actor(), _today(), json.loads(items_json), scope,
                                  json.loads(errors_json))
    return json.dumps({'text': summary['text'], 'added': summary['added']})

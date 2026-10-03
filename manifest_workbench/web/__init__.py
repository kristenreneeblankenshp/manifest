"""Manifest Workbench web application (hosted console).

Create the app with :func:`create_app`; production servers use
``gunicorn 'manifest_workbench.web:create_app()'``.

Configuration (environment variables):

* ``MANIFEST_DATA_DIR``   directory for the data file, issued PDFs and the secret key
* ``MANIFEST_SECRET_KEY`` session signing key (generated and stored in the data dir if unset)
* ``MANIFEST_ADMIN_USER`` / ``MANIFEST_ADMIN_PASSWORD`` bootstrap the first administrator
* ``MANIFEST_SECURE_COOKIES=1`` when served over HTTPS (recommended in production)
* ``MANIFEST_PROXY=1`` when behind a reverse proxy / platform load balancer (trust X-Forwarded-*)
* ``ZACKS_API_KEY``, ``SEC_CONTACT_EMAIL`` connector credentials (override Settings)
"""

from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

from flask import Flask

from ..repo import Repo

DATA_FILE = 'manifest_workbench.json'


def create_app(data_dir=None, testing=False) -> Flask:
    base = Path(data_dir or os.environ.get('MANIFEST_DATA_DIR', 'data')).resolve()
    base.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('MANIFEST_SECRET_KEY') or _secret(base),
        DATA_DIR=base,
        REPORTS_DIR=base / 'reports',
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('MANIFEST_SECURE_COOKIES') == '1',
        PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=12),
        TESTING=testing,
    )
    repo = Repo(base / DATA_FILE)
    repo.ensure()
    app.extensions['repo'] = repo
    _bootstrap_admin(repo)

    from . import auth, core, data, filters, mwir, reports, reviews, tables
    filters.register(app)
    for module in (auth, core, data, reviews, reports, mwir, tables):
        app.register_blueprint(module.bp)
    if os.environ.get('MANIFEST_PROXY') == '1':
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    return app


def _secret(base: Path) -> str:
    path = base / '.secret_key'
    if not path.exists():
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip()


def _bootstrap_admin(repo: Repo) -> None:
    user, password = os.environ.get('MANIFEST_ADMIN_USER'), os.environ.get('MANIFEST_ADMIN_PASSWORD')
    if not (user and password):
        return
    from .auth import set_user
    with repo.transaction() as store:
        if not store['users']:
            set_user(store, user, password, 'admin', user)

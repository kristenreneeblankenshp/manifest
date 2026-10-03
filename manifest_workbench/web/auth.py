"""Logins, roles and CSRF protection.

Roles: ``admin`` (everything, including settings and users), ``editor`` (operate the
workbench), ``viewer`` (read-only). Every change is audited under the signed-in user.
"""

from __future__ import annotations

import datetime as dt
import functools
import hmac
import secrets

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('auth', __name__)
ROLES = ('admin', 'editor', 'viewer')
PUBLIC = {'auth.login', 'auth.setup', 'auth.healthz', 'static'}


def repo():
    return current_app.extensions['repo']


def set_user(store, username, password, role, name):
    username = username.strip().lower()
    if not username or role not in ROLES:
        raise ValueError('Username and a valid role are required')
    if password is not None and len(password) < 10:
        raise ValueError('Passwords must be at least 10 characters')
    user = store['users'].get(username, {})
    user.update({'name': name.strip() or username, 'role': role})
    if password is not None:
        user['password_hash'] = generate_password_hash(password)
    user.setdefault('created', dt.datetime.now().isoformat(timespec='seconds'))
    store['users'][username] = user
    return user


def current_user():
    return getattr(g, 'user', None)


def actor():
    user = current_user()
    return user['name'] if user else 'system'


def can_edit():
    user = current_user()
    return bool(user) and user['role'] in ('admin', 'editor')


def safe_next(target: str) -> bool:
    """Only same-site paths may be used as a post-action redirect."""
    return target.startswith('/') and not target.startswith('//') and '\\' not in target \
        and not any(ord(c) < 32 for c in target)


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


@bp.before_app_request
def load_user_and_guard():
    g.user = None
    username = session.get('user')
    if username:
        user = repo().read()['users'].get(username)
        if user:
            g.user = {'username': username, **user}
    if request.method == 'POST':  # every form, signed in or not (login and setup included)
        token, expected = request.form.get('_csrf', ''), session.get('_csrf', '')
        if not expected or not hmac.compare_digest(token, expected):
            abort(400, 'Invalid or missing form token; reload the page and try again.')
    if request.endpoint in PUBLIC or request.endpoint is None:
        return None
    if g.user is None:
        if not repo().read()['users']:
            return redirect(url_for('auth.setup'))
        return redirect(url_for('auth.login', next=request.path))
    if request.method == 'POST':
        if not can_edit() and request.endpoint not in ('auth.logout', 'core.set_as_of'):
            abort(403, 'Your role is read-only.')
    return None


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*a, **kw):
        if not current_user() or current_user()['role'] != 'admin':
            abort(403, 'Administrator access required.')
        return view(*a, **kw)
    return wrapper


@bp.route('/healthz')
def healthz():
    """Liveness check for hosting platforms: the data file is readable."""
    repo().read()
    return {'status': 'ok'}


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        user = repo().read()['users'].get(username)
        if user and check_password_hash(user.get('password_hash', ''), request.form.get('password', '')):
            session.clear()
            session.permanent = True
            session['user'] = username
            csrf_token()
            target = request.args.get('next') or ''
            return redirect(target if safe_next(target) else url_for('core.console'))
        flash('Incorrect username or password.', 'error')
    return render_template('login.html')


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """First-run: create the administrator. Disabled once any user exists."""
    if repo().read()['users']:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirm'):
            flash('Passwords do not match.', 'error')
        else:
            try:
                with repo().transaction() as store:
                    if store['users']:
                        return redirect(url_for('auth.login'))
                    set_user(store, request.form.get('username', ''), request.form.get('password', ''),
                             'admin', request.form.get('name', ''))
                flash('Administrator created. Sign in to continue.', 'ok')
                return redirect(url_for('auth.login'))
            except ValueError as exc:
                flash(str(exc), 'error')
    return render_template('setup.html')

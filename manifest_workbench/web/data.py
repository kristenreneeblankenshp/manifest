"""Data connections (Zacks, weights CSV, research), research inbox triage, settings and users."""

from __future__ import annotations

import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import ops
from ..connectors import last_run, research, weights, zacks
from .auth import ROLES, actor, admin_required, current_user, repo, set_user
from .common import back, mutate
from .filters import today

bp = Blueprint('data', __name__)

SETTINGS = (
    ('zacks_url', 'Zacks endpoint URL template', 'e.g. https://api.example.com/v1/rank?symbol={ticker}'),
    ('zacks_auth', 'Key sent as', 'query or header'),
    ('zacks_key_name', 'Key parameter / header name', 'e.g. api_key or X-API-Key'),
    ('zacks_rank_field', 'Rank field in the response', 'name or dotted path, e.g. zacks_rank'),
    ('zacks_market_cap_field', 'Market cap field in the response', 'e.g. market_cap'),
    ('zacks_market_cap_unit', 'Market cap unit returned', 'B (billions), M (millions) or RAW (dollars)'),
    ('zacks_research_url', 'Zacks research endpoint (optional)', 'URL template returning research items'),
    ('zacks_research_list_field', 'Research list field', 'default: items'),
    ('sec_contact', 'Contact e-mail for SEC EDGAR', 'required by the SEC for automated access'),
    ('sec_forms', 'SEC forms to pull', 'default: 8-K,10-Q,10-K'),
    ('sec_enabled', 'Pull SEC filings', 'yes or no'),
    ('evidence_reviewer', 'Default evidence reviewer', 'default: Research Committee'),
)


@bp.route('/data')
def data():
    store = repo().read()
    cfg = zacks.config(store)
    return render_template('data.html', runs={k: last_run(store, k) for k in ('zacks', 'weights', 'research')},
                           log=list(reversed(store.get('data_log', [])))[:25], inbox=research.open_items(store),
                           zacks_ready=bool(cfg['zacks_url'] and cfg['api_key']),
                           sec_ready=bool(store['settings'].get('sec_contact')))


@bp.route('/data/zacks', methods=['POST'])
def zacks_pull():
    upload = request.files.get('file')
    if upload and upload.filename:
        text = upload.read().decode('utf-8-sig', errors='replace')
        res = mutate(lambda s: zacks.run(s, actor(), today(), csv_text=text, source=f'Zacks CSV {upload.filename}'))
    else:
        res = mutate(lambda s: zacks.run(s, actor(), today()))
    if res and res is not True:
        flash(res['text'] + (f" · {len(res['errors'])} warning(s)" if res['errors'] else ''),
              'ok' if not res['errors'] else 'warn')
        for e in res['errors'][:5]:
            flash(e, 'warn')
    return back('data.data')


@bp.route('/data/research', methods=['POST'])
def research_pull():
    days = int(request.form.get('days') or 7)
    res = mutate(lambda s: research.run(s, actor(), today(), days=days))
    if res and res is not True:
        flash(res['text'], 'ok' if not res['errors'] else 'warn')
        for e in res['errors'][:5]:
            flash(e, 'warn')
    return redirect(url_for('data.data') + '#inbox')


@bp.route('/data/weights', methods=['POST'])
def weights_upload():
    upload = request.files.get('file')
    if not upload or not upload.filename:
        flash('Choose a positions CSV to upload.', 'error')
        return back('data.data')
    text = upload.read().decode('utf-8-sig', errors='replace')
    missing_zero = request.form.get('missing_as_zero', 'on') == 'on'
    token = secrets.token_urlsafe(12)

    def stage(store):
        result = weights.preview(store, text, missing_as_zero=missing_zero)
        store['staging'] = {k: v for k, v in store.get('staging', {}).items() if k.startswith('w-')}
        store['staging'][f'w-{token}'] = {'result': result, 'file': upload.filename}
        return result
    result = mutate(stage)
    if not result or result is True:
        return back('data.data')
    return render_template('weights_preview.html', p=result, token=token, filename=upload.filename)


@bp.route('/data/weights/<token>', methods=['POST'])
def weights_apply(token):
    def apply(store):
        staged = store.get('staging', {}).pop(f'w-{token}', None)
        if not staged:
            raise ValueError('This upload preview has expired; upload the file again.')
        return weights.apply(store, staged['result'], actor(), today(), staged['file'])
    text = mutate(apply)
    if text and text is not True:
        flash(f'Actual weights loaded: {text}', 'ok')
    return redirect(url_for('data.data'))


@bp.route('/data/inbox/<item_id>/<action>', methods=['POST'])
def inbox_action(item_id, action):
    def run(store):
        item = next((i for i in store['inbox'] if i['id'] == item_id), None)
        if item is None:
            raise ValueError('Item not found')
        if action == 'dismiss':
            item['status'] = 'Dismissed'
        elif action == 'review':
            ops.add_record(store, 'intel-review', [f"symbol={item.get('ticker', '')}",
                                                   f"reason={item.get('title', '')[:120]}",
                                                   f"trigger={item.get('source')} {item.get('form', '')}",
                                                   'status=Open', 'priority=Medium'], actor(), today())
            item['status'] = 'Queued for review'
        else:
            raise ValueError('Unknown action')
        item['triaged_by'] = actor()
        ops.audit(store, actor(), action, 'inbox', item_id)
    mutate(run, 'Inbox updated.')
    return redirect(url_for('data.data') + '#inbox')


@bp.route('/data/inbox/<item_id>/evidence', methods=['GET', 'POST'])
def inbox_evidence(item_id):
    store = repo().read()
    item = next((i for i in store['inbox'] if i['id'] == item_id), None)
    if item is None:
        abort(404)
    if request.method == 'POST':
        pairs = [f'{k}={v}' for k, v in request.form.items() if k not in ('_csrf', 'next') and v.strip()]

        def create(s):
            rec = ops.add_record(s, 'evidence', pairs, actor(), today())
            it = next(i for i in s['inbox'] if i['id'] == item_id)
            it.update({'status': 'Logged as evidence', 'evidence_id': rec['evidence_id'], 'triaged_by': actor()})
            return rec
        rec = mutate(create)
        if rec and rec is not True:
            flash(f"Evidence {rec['evidence_id']} logged.", 'ok')
            return redirect(url_for('tables.record', table='evidence', key=rec['evidence_id']))
    from .. import schema as S
    return render_template('evidence_form.html', item=item, values=research.evidence_defaults(store, item, today()),
                           table=S.EVIDENCE)


# --------------------------------------------------------------------------- settings & users

@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        def save(store):
            for key, _, _ in SETTINGS:
                store['settings'][key] = request.form.get(key, '').strip()
            key = request.form.get('zacks_api_key', '').strip()
            if key:
                store['settings']['zacks_api_key'] = key
            if request.form.get('clear_zacks_key'):
                store['settings'].pop('zacks_api_key', None)
            ops.audit(store, actor(), 'settings', 'settings', 'connectors')
        mutate(save, 'Settings saved.')
        return redirect(url_for('data.settings'))
    store = repo().read()
    import os
    return render_template('settings.html', fields=SETTINGS, values=store['settings'],
                           key_set=bool(store['settings'].get('zacks_api_key')),
                           key_env=bool(os.environ.get('ZACKS_API_KEY')), users=store['users'], roles=ROLES)


@bp.route('/settings/users', methods=['POST'])
@admin_required
def users():
    username = request.form.get('username', '')
    password = request.form.get('password') or None
    if request.form.get('remove'):
        def remove(store):
            if username.strip().lower() == current_user()['username']:
                raise ValueError('You cannot remove yourself')
            admins = [u for u, v in store['users'].items() if v['role'] == 'admin' and u != username]
            if not admins:
                raise ValueError('At least one administrator must remain')
            store['users'].pop(username, None)
            ops.audit(store, actor(), 'remove', 'users', username)
        mutate(remove, f'User {username} removed.')
    else:
        def save(store):
            if username.strip().lower() not in store['users'] and not password:
                raise ValueError('A password is required for a new user')
            set_user(store, username, password, request.form.get('role', 'viewer'), request.form.get('name', ''))
            ops.audit(store, actor(), 'user', 'users', username)
        mutate(save, f'User {username} saved.')
    return redirect(url_for('data.settings') + '#users')

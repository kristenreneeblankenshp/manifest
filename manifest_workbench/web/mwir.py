"""MWIR workspace: the official weekly report, edited beside its live 8-page preview."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_file, url_for)

from .. import mwir as MW
from .. import reports as RP
from ..pdf import render
from .auth import actor, repo
from .common import mutate
from .filters import today

bp = Blueprint('mwir', __name__)


def _get(rid):
    draft = repo().read()['reports'].get(rid)
    if draft is None or not draft.get('doc'):
        abort(404)
    return draft


def _view(store, draft):
    snap = draft.get('zacks') if draft['status'] == 'Issued' and draft.get('zacks') else MW.snapshot(store)
    return MW.model(draft['doc'], snap), snap


@bp.route('/mwir')
def index():
    store = repo().read()
    rid, _, start, end = RP.report_id('mwir', today())
    current = store['reports'].get(rid)
    if current and current.get('doc'):
        return redirect(url_for('mwir.workspace', rid=rid))
    history = sorted((r for r in store['reports'].values() if r.get('type') == 'mwir' and r.get('doc')),
                     key=lambda r: r['period_start'], reverse=True)
    we, pub = MW.week_dates(start)
    return render_template('mwir_index.html', rid=rid, week_ending=we, pub=pub, history=history,
                           prior=history[0] if history else None, snap=MW.snapshot(store))


@bp.route('/mwir/start', methods=['POST'])
def start():
    draft = mutate(lambda s: RP.create_draft(s, 'mwir', actor(), today()))
    if draft and draft is not True:
        flash('This week\'s MWIR is ready. It starts from last week\'s report; load the holdings file to begin.', 'ok')
        return redirect(url_for('mwir.workspace', rid=draft['id']))
    return redirect(url_for('mwir.index'))


@bp.route('/mwir/<rid>')
def workspace(rid):
    store = repo().read()
    draft = _get(rid)
    v, snap = _view(store, draft)
    history = sorted((r for r in store['reports'].values() if r.get('type') == 'mwir' and r.get('doc')),
                     key=lambda r: r['period_start'], reverse=True)
    return render_template('mwir_workspace.html', r=draft, v=v, d=draft['doc'], snap=snap, history=history,
                           sleeves=MW.SLEEVES, guidance=MW.GUIDANCE, text_fields=MW.TEXT_FIELDS,
                           compass=MW.COMPASS, strategic_cert=MW.strategic_target(store),
                           upcoming=MW.upcoming_events(store, draft['doc']))


@bp.route('/mwir/<rid>/pages')
def pages(rid):
    """The 8 report pages as HTML (the workspace preview; also printable)."""
    store = repo().read()
    draft = _get(rid)
    v, _ = _view(store, draft)
    return render_template('mwir_pages.html', v=v, r=draft)


@bp.route('/mwir/<rid>/save', methods=['POST'])
def save(rid):
    xhr = request.headers.get('X-Requested-With') == 'fetch'
    res = mutate(lambda s: RP.mwir_save(s, rid, actor(), request.form), None if xhr else 'Saved.')
    if xhr:
        store = repo().read()
        draft = store['reports'].get(rid)
        if not res or not draft:
            return jsonify({'ok': False, 'error': 'Not saved. Reload the page.'}), 409
        v, _ = _view(store, draft)
        return jsonify({'ok': True, 'saved': draft.get('updated'),
                        'status_html': render_template('_mwir_status.html', v=v, r=draft)})
    anchor = '#holdings' if 'h_count' in request.form else ''
    return redirect(url_for('mwir.workspace', rid=rid) + anchor)


@bp.route('/mwir/<rid>/holdings', methods=['POST'])
def holdings(rid):
    upload = request.files.get('file')
    if not upload or not upload.filename:
        flash('Choose the holdings CSV (Date, Symbol, Weights).', 'error')
        return redirect(url_for('mwir.workspace', rid=rid))
    text = upload.read().decode('utf-8-sig', errors='replace')
    res = mutate(lambda s: RP.mwir_import(s, rid, actor(), text, upload.filename))
    if res and res is not True:
        msg, ok = res
        for i, line in enumerate(msg.split('\n')):
            flash(line, 'ok' if ok or i == 0 else 'warn')
    return redirect(url_for('mwir.workspace', rid=rid) + '#holdings')


@bp.route('/mwir/<rid>/import-json', methods=['POST'])
def import_json(rid):
    upload = request.files.get('file')
    text = upload.read().decode('utf-8-sig', errors='replace') if upload and upload.filename \
        else request.form.get('json', '')
    mutate(lambda s: RP.mwir_import_json(s, rid, actor(), text), 'Document imported.')
    return redirect(url_for('mwir.workspace', rid=rid))


@bp.route('/mwir/<rid>/baseline', methods=['POST'])
def baseline(rid):
    n = mutate(lambda s: RP.mwir_fill_baseline(s, rid, actor()))
    if n is not None:
        flash(f'MFPDF baseline set from the certified portfolio ({0 if n is True else n} change(s)).', 'ok')
    return redirect(url_for('mwir.workspace', rid=rid) + '#holdings')


@bp.route('/mwir/<rid>/events', methods=['POST'])
def events(rid):
    n = mutate(lambda s: RP.mwir_add_events(s, rid, actor()))
    if n is not None:
        n = 0 if n is True else n
        flash(f'{n} earnings date(s) added to the event gates.' if n else
              'No new earnings dates in the publication week.', 'ok')
    return redirect(url_for('mwir.workspace', rid=rid) + '#controls')


@bp.route('/mwir/<rid>/draft.pdf')
def draft_pdf(rid):
    store = repo().read()
    draft = _get(rid)
    tmp = Path(tempfile.mkdtemp()) / f'{rid}-draft.pdf'
    render(draft, tmp, final=False, snap=MW.snapshot(store))
    return send_file(tmp, mimetype='application/pdf', as_attachment=False, download_name=tmp.name)


@bp.route('/mwir/<rid>/issue', methods=['POST'])
def issue(rid):
    override = request.form.get('override', '')
    draft = mutate(lambda s: RP.issue(s, rid, actor(), today(), current_app.config['REPORTS_DIR'], override))
    if draft and draft is not True:
        flash(f"MWIR issued as version {draft['version']} ({draft.get('certification')}) and recorded in "
              'Committee Operations.', 'ok')
    return redirect(url_for('mwir.workspace', rid=rid))


@bp.route('/mwir/<rid>/reopen', methods=['POST'])
def reopen(rid):
    mutate(lambda s: RP.reopen(s, rid, actor()), 'Reopened. Issuing again creates a new version.')
    return redirect(url_for('mwir.workspace', rid=rid))


@bp.route('/mwir/<rid>/export.json')
def export(rid):
    draft = _get(rid)
    body = json.dumps({'format': 'manifest-mwir/1', 'id': rid, 'doc': draft['doc']}, indent=1)
    return Response(body, mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename={rid}.json'})

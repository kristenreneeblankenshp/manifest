"""Report studio pages: drafts, editing, preview, PDF and issue."""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_file,
                   url_for)

from .. import reports as RP
from ..pdf import render
from .auth import actor, repo
from .common import mutate
from .filters import today

bp = Blueprint('reports', __name__)


@bp.route('/reports')
def index():
    store = repo().read()
    drafts = sorted(store['reports'].values(), key=lambda r: (r['period_start'], r['type']), reverse=True)
    current = []
    for kind, t in RP.TYPES.items():
        rid, review_id, start, end = RP.report_id(kind, today())
        current.append({'kind': kind, 'code': t['code'], 'title': t['title'], 'cycle': t['cycle'], 'id': rid,
                        'label': RP.period_label(kind, start, end), 'report': store['reports'].get(rid)})
    return render_template('reports.html', current=current, drafts=drafts)


@bp.route('/reports/new/<kind>', methods=['POST'])
def new(kind):
    draft = mutate(lambda s: RP.create_draft(s, kind, actor(), today()))
    if draft and draft is not True:
        return redirect(url_for('reports.edit', rid=draft['id']))
    return redirect(url_for('reports.index'))


def _get(rid):
    draft = repo().read()['reports'].get(rid)
    if draft is None:
        abort(404)
    return draft


@bp.route('/reports/<rid>')
def edit(rid):
    return render_template('report_edit.html', r=_get(rid))


@bp.route('/reports/<rid>/save', methods=['POST'])
def save(rid):
    draft = _get(rid)
    sections = {}
    for sec in draft['sections']:
        k = sec['key']
        sections[k] = {'narrative': request.form.get(f'n_{k}', sec['narrative']),
                       'include': request.form.get(f'i_{k}') == 'on'}
        if sec.get('custom'):
            sections[k]['title'] = request.form.get(f't_{k}', sec['title'])
    mutate(lambda s: RP.edit(s, rid, actor(), title=request.form.get('title'),
                             subtitle=request.form.get('subtitle'), sections=sections), 'Draft saved.')
    action = request.form.get('then')
    if action == 'preview':
        return redirect(url_for('reports.preview', rid=rid))
    if action == 'pdf':
        return redirect(url_for('reports.draft_pdf', rid=rid))
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/refresh', methods=['POST'])
def refresh(rid):
    mutate(lambda s: RP.refresh(s, rid, actor(), today()),
           'Data refreshed. Your edited narratives were kept; untouched ones were rewritten.')
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/section', methods=['POST'])
def add_section(rid):
    mutate(lambda s: RP.add_section(s, rid, actor(), request.form.get('title', ''),
                                    request.form.get('narrative', ''), request.form.get('after')),
           'Section added.')
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/section/<key>/remove', methods=['POST'])
def remove_section(rid, key):
    mutate(lambda s: RP.remove_section(s, rid, actor(), key), 'Section removed.')
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/section/<key>/reset', methods=['POST'])
def reset_section(rid, key):
    mutate(lambda s: RP.reset_narrative(s, rid, actor(), key), 'Narrative reset to the generated text.')
    return redirect(url_for('reports.edit', rid=rid) + f'#{key}')


@bp.route('/reports/<rid>/preview')
def preview(rid):
    return render_template('report_preview.html', r=_get(rid))


@bp.route('/reports/<rid>/draft.pdf')
def draft_pdf(rid):
    draft = _get(rid)
    tmp = Path(tempfile.mkdtemp()) / f"{rid}-draft.pdf"
    render(draft, tmp, final=False)
    return send_file(tmp, mimetype='application/pdf', as_attachment=False, download_name=tmp.name)


@bp.route('/reports/<rid>/issue', methods=['POST'])
def issue(rid):
    draft = mutate(lambda s: RP.issue(s, rid, actor(), today(), current_app.config['REPORTS_DIR']))
    if draft and draft is not True:
        flash(f"{draft['code']} issued as version {draft['version']} and recorded in Committee Operations.", 'ok')
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/reopen', methods=['POST'])
def reopen(rid):
    mutate(lambda s: RP.reopen(s, rid, actor()), 'Reopened as a draft; issuing again creates a new version.')
    return redirect(url_for('reports.edit', rid=rid))


@bp.route('/reports/<rid>/file/<name>')
def file(rid, name):
    draft = _get(rid)
    if name not in {f['file'] for f in draft.get('files', [])}:
        abort(404)
    path = Path(current_app.config['REPORTS_DIR']) / name
    if not path.exists():
        abort(404)
    return send_file(path, mimetype='application/pdf', download_name=name)

"""Review manager pages."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import reviews as RV
from .auth import actor, repo
from .common import mutate, wb
from .filters import today

bp = Blueprint('reviews', __name__)


@bp.route('/reviews')
def index():
    w = wb()
    current = []
    for kind in (RV.WEEKLY, RV.MONTHLY, RV.QUARTERLY):
        rid, start, end, due = RV.period(kind, today())
        review = w.store['reviews'].get(rid)
        done, total = RV.progress(w, review) if review else (0, len(RV.CHECKLISTS[kind]))
        auto = RV.evaluate(w, review or {'kind': kind, 'items': {}, 'start': start.isoformat(),
                                         'end': end.isoformat(), 'id': rid})
        current.append({'kind': kind, 'label': RV.LABELS[kind], 'id': rid, 'start': start, 'end': end,
                        'due': due, 'review': review, 'done': done, 'total': total,
                        'auto_ok': sum(1 for r in auto if r['auto_ok'])})
    history = sorted(w.store['reviews'].values(), key=lambda r: r['start'], reverse=True)
    return render_template('reviews.html', current=current, history=history)


@bp.route('/reviews/start/<kind>', methods=['POST'])
def start(kind):
    if kind not in RV.CHECKLISTS:
        abort(404)
    review = mutate(lambda s: RV.get(s, kind, today(), create=True))
    if review and review is not True:
        return redirect(url_for('reviews.detail', rid=review['id']))
    return redirect(url_for('reviews.index'))


@bp.route('/reviews/<rid>')
def detail(rid):
    w = wb()
    review = w.store['reviews'].get(rid)
    if review is None:
        abort(404)
    rows = RV.evaluate(w, review)
    return render_template('review.html', review=review, rows=rows, label=RV.LABELS[review['kind']])


@bp.route('/reviews/<rid>/item/<key>', methods=['POST'])
def item(rid, key):
    done = request.form.get('done', '1') == '1'
    note = request.form.get('note', '')
    mutate(lambda s: RV.confirm(s, rid, key, actor(), note, done, wb=wb(s)),
           'Item confirmed.' if done else 'Item reopened.')
    return redirect(url_for('reviews.detail', rid=rid) + f'#{key}')


@bp.route('/reviews/<rid>/signoff', methods=['POST'])
def signoff(rid):
    mutate(lambda s: RV.sign_off(s, rid, actor(), wb(s), request.form.get('notes', '')), 'Review signed off.')
    return redirect(url_for('reviews.detail', rid=rid))


@bp.route('/reviews/<rid>/reopen', methods=['POST'])
def reopen(rid):
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Give a reason for reopening a signed-off review.', 'error')
    else:
        mutate(lambda s: RV.reopen(s, rid, actor(), reason), 'Review reopened.')
    return redirect(url_for('reviews.detail', rid=rid))


@bp.app_template_global()
def review_link(kind):
    rid = RV.period(kind, today())[0]
    return url_for('reviews.detail', rid=rid) if rid in repo().read()['reviews'] else url_for('reviews.index')

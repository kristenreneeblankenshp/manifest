"""Navigation: one definition drives the sidebar, the section sub-tabs and quick jump.

The sidebar keeps to the weekly operating loop; detail pages sit behind a hub's sub-tabs, so
every page is one click from its hub and two from anywhere.
"""

from __future__ import annotations

from flask import request

from .. import schema as S

# (label, url, sub-tabs [(label, url)], badge key)
NAV = (
    ('Operate', (
        ('Console', '/', (), None),
        ('Decisions', '/decisions', (), None),
        ('Actions & notebook', '/actions', (), None),
    )),
    ('Weekly cycle', (
        ('Data & inbox', '/data', (), 'inbox'),
        ('MWIR', '/mwir', (), 'mwir'),
        ('Reviews', '/reviews', (), None),
        ('Reports', '/reports', (), None),
    )),
    ('Research · MOPS-003', (
        ('Research', '/research', (
            ('Overview', '/research'), ('Evidence ledger', '/t/evidence'), ('MIAR registry', '/t/miar'),
            ('MIAR review log', '/t/review'), ('MASR registry', '/t/masr'), ('Intelligence', '/intel'),
            ('Control centers', '/rcc/1')), None),
        ('Candidate pipeline', '/pipeline', (), None),
    )),
    ('Portfolio · MOPS-002', (
        ('Portfolio', '/t/portfolio', (
            ('Certified allocation', '/t/portfolio'), ('Conviction', '/t/conviction'),
            ('Dashboard controls', '/controls')), None),
        ('Engineering', '/pew', (
            ('Control center', '/pew'), ('Allocation lab', '/lab'), ('Validation & cert', '/validation'),
            ('Candidate comparison', '/t/pew004'), ('Roles', '/t/roles'), ('Mandate', '/t/mandate'),
            ('Sleeves', '/t/sleeves'), ('Change register', '/t/changes')), None),
    )),
    ('System', (
        ('Workbook sheets', '/sheets', (), None),
        ('Audit trail', '/audit', (), None),
        ('Settings & users', '/settings', (), 'admin'),
    )),
)

# Extra paths that belong to an item without being one of its tabs.
ALSO = {'/research': ('/rcc',), '/reports': (), '/data': ('/settings/users',)}


def _match(path: str, url: str) -> bool:
    if url == '/':
        return path == '/'
    return path == url or path.startswith(url.rstrip('/') + '/')


def _tab_match(path: str, url: str) -> bool:
    if url.startswith('/rcc'):
        return path.startswith('/rcc')
    return _match(path, url)


def build(path: str, badges: dict, is_admin: bool) -> tuple:
    """Sidebar sections with active flags, and the sub-tabs for the current page."""
    sections, subnav = [], []
    for title, items in NAV:
        out = []
        for label, url, tabs, badge in items:
            if badge == 'admin' and not is_admin:
                continue
            urls = [url] + [u for _, u in tabs] + list(ALSO.get(url, ()))
            active = any(_tab_match(path, u) for u in urls)
            out.append({'label': label, 'url': url, 'active': active,
                        'badge': badges.get(badge) if badge and badge != 'admin' else None})
            if active and tabs:
                subnav = [{'label': t, 'url': u, 'active': _tab_match(path, u)} for t, u in tabs]
        sections.append({'title': title, 'links': out})
    return sections, subnav


def jump_targets() -> list:
    """Everything quick jump can open: pages, then every workbook table."""
    seen, out = set(), []
    for _, items in NAV:
        for label, url, tabs, _ in items:
            for lbl, u in ((label, url),) + tuple(tabs):
                if u not in seen:
                    seen.add(u)
                    out.append((lbl, u))
    for name, spec in S.TABLES.items():
        url = f'/t/{name}' if spec.mode != 'single' else f'/t/{name}/_'
        if url not in seen:
            seen.add(url)
            out.append((f'{spec.title} · {spec.sheet}', url))
    return out


def context(badges: dict, user) -> dict:
    sections, subnav = build(request.path, badges, bool(user and user.get('role') == 'admin'))
    return {'nav_sections': sections, 'subnav': subnav}

"""Data connectors: Zacks, broker weights, research feeds.

Connectors fetch or parse external data and apply it to the store through the same
controlled fields an operator would edit, with every change audited and each run
recorded in ``store['data_log']``.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request

TIMEOUT = 20


class ConnectorError(Exception):
    pass


def http_get(url: str, headers: dict = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - configured URLs
            return resp.read()
    except Exception as exc:  # network, HTTP and TLS errors all surface to the operator
        raise ConnectorError(f'{_redact(url)}: {exc}') from None


def http_json(url: str, headers: dict = None):
    raw = http_get(url, headers)
    try:
        return json.loads(raw.decode('utf-8'))
    except ValueError:
        raise ConnectorError(f'{_redact(url)} did not return JSON') from None


def _redact(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    safe = [(k, '***' if any(s in k.lower() for s in ('key', 'token', 'secret')) else v) for k, v in query]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(safe)))


def setting(store: dict, key: str, env: str = None, default=''):
    """A connector setting; an environment variable overrides the stored value."""
    if env and os.environ.get(env):
        return os.environ[env]
    value = store.get('settings', {}).get(key)
    return default if value in (None, '') else value


def log_run(store: dict, connector: str, actor: str, summary: str, errors=(), counts=None) -> dict:
    entry = {'ts': dt.datetime.now().isoformat(timespec='seconds'), 'connector': connector,
             'actor': actor, 'summary': summary, 'errors': list(errors)[:50],
             'counts': counts or {}}
    store.setdefault('data_log', []).append(entry)
    del store['data_log'][:-200]
    return entry


def last_run(store: dict, connector: str):
    for entry in reversed(store.get('data_log', [])):
        if entry['connector'] == connector:
            return entry
    return None

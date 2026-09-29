"""JSON persistence for the workbench's operating inputs.

Only input (and locked certified) values are stored; every calculated field is
recomputed by :mod:`manifest_workbench.engine` on load, exactly as the workbook
recalculates.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from importlib import resources
from pathlib import Path

FORMAT = 'manifest-workbench/1'
TABLE_KEYS = ('portfolio', 'conviction', 'pew004', 'evidence', 'miar', 'review', 'masr', 'pipeline')
DEFAULT_DATA_FILE = 'manifest_workbench.json'


class StoreError(Exception):
    pass


def default_path() -> Path:
    return Path(os.environ.get('MANIFEST_DATA', DEFAULT_DATA_FILE))


def empty_store() -> dict:
    store = {'format': FORMAT, 'meta': {}, 'audit': []}
    for key in TABLE_KEYS:
        store[key] = []
    return store


def seed_store() -> dict:
    """The operating inputs of the Manifest Workbench v0.4, as issued."""
    text = resources.files('manifest_workbench').joinpath('data/seed.json').read_text('utf-8')
    return _validate(json.loads(text))


def load(path: Path) -> dict:
    try:
        with open(path, encoding='utf-8') as fh:
            return _validate(json.load(fh))
    except FileNotFoundError:
        raise StoreError(f"No data file at {path}. Run 'init' to create one.") from None
    except json.JSONDecodeError as exc:
        raise StoreError(f'{path} is not valid JSON: {exc}') from None


def save(path: Path, store: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(store, fh, indent=1, ensure_ascii=False, default=_json_default)
            fh.write('\n')
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _json_default(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    raise TypeError(f'cannot serialise {type(value).__name__}')


def _validate(store: dict) -> dict:
    if store.get('format') != FORMAT:
        raise StoreError(f"Unsupported data format {store.get('format')!r}; expected {FORMAT!r}")
    for key in TABLE_KEYS:
        store.setdefault(key, [])
    store.setdefault('audit', [])
    store.setdefault('meta', {})
    return store

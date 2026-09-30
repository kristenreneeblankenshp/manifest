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
DEFAULT_DATA_FILE = 'manifest_workbench.json'


def _table_keys():
    from .schema import TABLES
    return tuple(TABLES)


TABLE_KEYS = _table_keys()


class StoreError(Exception):
    pass


def default_path() -> Path:
    return Path(os.environ.get('MANIFEST_DATA', DEFAULT_DATA_FILE))


def empty_store() -> dict:
    from .schema import TABLES
    store = {'format': FORMAT, 'meta': {}, 'audit': []}
    for key, table in TABLES.items():
        store[key] = {} if table.mode == 'single' else []
    return store


def _seed_raw() -> dict:
    text = resources.files('manifest_workbench').joinpath('data/seed.json').read_text('utf-8')
    return json.loads(text)


def seed_store() -> dict:
    """The operating inputs of the Manifest Workbench v0.4, as issued."""
    return _validate(_seed_raw(), migrate=False)


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


def _validate(store: dict, migrate: bool = True) -> dict:
    """Check the format and add any tables missing from an older data file.

    Data files created before a sheet was covered receive that sheet's v0.4 inputs, so
    existing operating data is kept and the new sheets start from the issued workbook.
    """
    if store.get('format') != FORMAT:
        raise StoreError(f"Unsupported data format {store.get('format')!r}; expected {FORMAT!r}")
    missing = [key for key in TABLE_KEYS if key not in store]
    if missing:
        seed = _seed_raw() if migrate else {}
        empty = empty_store()
        for key in missing:
            store[key] = seed.get(key, empty[key])
    store.setdefault('audit', [])
    store.setdefault('meta', {})
    for key, default in APP_SECTIONS.items():
        store.setdefault(key, default())
    return store


# Application sections kept alongside the workbook tables (not part of the workbook itself).
APP_SECTIONS = {
    'settings': dict,   # connector configuration and defaults
    'users': dict,      # web users: username -> {name, role, password_hash}
    'reviews': dict,    # review cycles: review id -> state
    'reports': dict,    # report drafts and issued versions: report id -> draft
    'inbox': list,      # pulled research items awaiting triage
    'data_log': list,   # connector runs
    'staging': dict,    # previews awaiting confirmation (e.g. a weights upload)
}

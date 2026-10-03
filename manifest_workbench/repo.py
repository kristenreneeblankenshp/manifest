"""Locked access to the JSON data file for concurrent use (web workers, CLI).

``Repo.read()`` returns a snapshot; ``Repo.transaction()`` holds an exclusive lock
while a change is made and saved, so simultaneous requests cannot overwrite each
other's edits.
"""

from __future__ import annotations

import contextlib
import os
import threading
from pathlib import Path

from . import store as ST

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

_thread_lock = threading.RLock()


class Repo:
    def __init__(self, path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def ensure(self) -> None:
        """Create the data file from the bundled v0.4 inputs when it does not exist yet."""
        with self._lock():
            if not self.path.exists():
                ST.save(self.path, ST.seed_store())

    def read(self) -> dict:
        with self._lock(shared=True):
            return ST.load(self.path)

    @contextlib.contextmanager
    def transaction(self):
        with self._lock():
            store = ST.load(self.path)
            yield store
            ST.save(self.path, store)

    @contextlib.contextmanager
    def _lock(self, shared=False):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + '.lock')
        with _thread_lock:
            with open(lock_path, 'a+') as fh:
                if fcntl:
                    fcntl.flock(fh, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl:
                        fcntl.flock(fh, fcntl.LOCK_UN)


def data_dir() -> Path:
    return Path(os.environ.get('MANIFEST_DATA_DIR', '.')).resolve()

"""Build the in-Claude edition of the workbench (an Artifact page that runs the app with Pyodide).

    python claude_app/build.py --pyodide PATH_TO_PYODIDE_PACKAGE [--out dist/claude_app]

PATH_TO_PYODIDE_PACKAGE is an unpacked `pyodide` npm package (e.g. node_modules/pyodide).
The output folder holds ``index.html``, ``bundle.json`` (the source of the app and its
pure-Python dependencies, taken from the current interpreter) and ``py/`` (the Pyodide runtime,
with its standard library as ``stdlib.json``). Artifacts serve text and data files but not
archives, so Python sources ship as JSON and the page assembles them in memory. Publish the
folder as one Artifact: the page fetches only its own files.
"""

from __future__ import annotations

import argparse
import base64
import importlib
import importlib.metadata
import io
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACKAGES = ('flask', 'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous', 'click', 'blinker', 'reportlab')
# Only what the app imports; ReportLab's fonts and graphics are not needed for the PDFs it draws.
SKIP = {'reportlab': ('fonts', 'graphics')}
PYODIDE_FILES = ('pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'pyodide-lock.json')
# Parts of the standard library the app never imports.
STDLIB_SKIP = ('_pyrepl', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'venv', 'pydoc_data', 'lib2to3',
               'curses', 'dbm', 'sqlite3', 'turtle.py')
# ReportLab imports Pillow unconditionally but only uses it to draw images, which the app never does.
PIL_STUB = '"""Stand-in for Pillow in the in-Claude build: ReportLab images are not used."""\nImage = None\n'


def _add_tree(zf: zipfile.ZipFile, src: Path, arc: str, skip=()):
    for path in sorted(src.rglob('*')):
        rel = path.relative_to(src)
        if path.is_dir() or '__pycache__' in rel.parts or rel.parts[0] in skip:
            continue
        if path.suffix in ('.so', '.pyd', '.pyc', '.pyi', '.c', '.h') or path.name == 'py.typed':
            continue
        zf.write(path, f'{arc}/{rel.as_posix()}')


def _as_json(zip_bytes: bytes, skip=()) -> str:
    """Every file of a zip as JSON: {"files": [[path, text], ...]}; a binary file is [path, null, base64]."""
    files = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename.split('/')[0] in skip:
                continue
            raw = zf.read(info)
            try:
                files.append([info.filename, raw.decode('utf-8')])
            except UnicodeDecodeError:
                files.append([info.filename, None, base64.b64encode(raw).decode('ascii')])
    # ASCII-only JSON: escapes keep characters such as U+FFFD intact through publishing
    return json.dumps({'files': files}, separators=(',', ':'))


def bundle() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in PACKAGES:
            pkg = Path(importlib.import_module(name).__file__).parent
            _add_tree(zf, pkg, f'site/{name}', SKIP.get(name, ()))
            info = Path(importlib.metadata.distribution(name)._path)  # versions are read from metadata
            _add_tree(zf, info, f'site/{info.name}')
        zf.writestr('site/PIL/__init__.py', PIL_STUB)
        _add_tree(zf, ROOT / 'manifest_workbench', 'app/manifest_workbench')
        zf.write(HERE / 'wb_bridge.py', 'app/wb_bridge.py')
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--pyodide', required=True, help='unpacked pyodide npm package directory')
    ap.add_argument('--out', default=str(ROOT / 'dist' / 'claude_app'))
    args = ap.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / 'py').mkdir(parents=True)
    for name in PYODIDE_FILES:
        shutil.copy2(Path(args.pyodide) / name, out / 'py' / name)
    stdlib = (Path(args.pyodide) / 'python_stdlib.zip').read_bytes()
    (out / 'py' / 'stdlib.json').write_text(_as_json(stdlib, STDLIB_SKIP), encoding='utf-8')
    (out / 'bundle.json').write_text(_as_json(bundle()), encoding='utf-8')
    shutil.copy2(HERE / 'index.html', out / 'index.html')
    for f in sorted(out.rglob('*')):
        if f.is_file():
            print(f'{f.relative_to(out)}  {f.stat().st_size / 1e6:.2f} MB')


if __name__ == '__main__':
    main()

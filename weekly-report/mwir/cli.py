"""Command line entry point: python -m mwir {build,check,new-week}."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from .model import FAIL, PASS, WARN, InputError, build

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = ROOT / "config" / "policy.yaml"


def _print_assertions(report) -> None:
    width = max(len(a.label) for a in report.assertions)
    for a in report.assertions:
        mark = {PASS: "ok  ", WARN: "warn", FAIL: "FAIL"}.get(a.result, "  - ")
        line = f"  [{mark}] {a.label.ljust(width)}  {a.value}"
        if a.detail and a.result != PASS:
            line += f"   ({a.detail})"
        print(line)
    print()
    print("  Certification:", "PASS" if report.certified else "FAIL - report will be marked NOT CERTIFIED")


def _load(args):
    return build(
        Path(args.week),
        Path(args.policy),
        Path(args.holdings) if args.holdings else None,
        Path(args.actual) if args.actual else None,
    )


def cmd_check(args) -> int:
    report = _load(args)
    print(f"MWIR week ending {report.week_ending}: {len(report.holdings)} holdings, total {report.total:.2f}%")
    _print_assertions(report)
    return 0 if report.certified else 1


def cmd_build(args) -> int:
    from .render import LayoutError, render

    report = _load(args)
    out = Path(args.out) if args.out else ROOT / "out" / (
        f"Manifest_MWIR_Week_Ending_{report.week_ending.isoformat()}_"
        f"{'Official' if report.week.get('status') == 'official' and report.certified else 'Draft'}.pdf"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    _print_assertions(report)
    try:
        pages = render(report, str(out))
    except LayoutError as e:
        print(f"\nLayout error: {e}", file=sys.stderr)
        return 3
    print(f"\nWrote {out} ({pages} pages)")
    return 0 if report.certified else 1


def cmd_new_week(args) -> int:
    """Copy last week's file forward so only what changed needs editing."""
    src = Path(args.week)
    text = src.read_text(encoding="utf-8")
    m = re.search(r"^week_ending:\s*(\S+)", text, re.M)
    if not m:
        raise InputError(f"{src}: no week_ending line")
    prev = dt.date.fromisoformat(m.group(1))
    new = prev + dt.timedelta(days=7)
    pub = new + dt.timedelta(days=3)  # following Monday

    comp = re.search(r"^\s+composite:\s*(\S+)", text, re.M)
    text = re.sub(r"^week_ending:.*$", f"week_ending: {new.isoformat()}", text, count=1, flags=re.M)
    text = re.sub(r"^publication_date:.*$", f"publication_date: {pub.isoformat()}", text, count=1, flags=re.M)
    text = re.sub(r"^status:\s*\S+", "status: draft", text, count=1, flags=re.M)
    if comp:
        text = re.sub(r"^(\s+prior_composite:).*$", rf"\g<1> {comp.group(1)}", text, count=1, flags=re.M)
    holdings = args.holdings or f"../holdings/{new.isoformat()}.csv"
    text = re.sub(r"^holdings_csv:.*$", f"holdings_csv: {holdings}", text, count=1, flags=re.M)

    dst = Path(args.out) if args.out else src.parent / f"{new.isoformat()}.yaml"
    if dst.exists() and not args.force:
        print(f"{dst} already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    header = (
        f"# DRAFT carried forward from {src.name}. Update the narrative, scores,\n"
        f"# market tape, event gates and guidance, then set status: official.\n"
    )
    dst.write_text(header + text, encoding="utf-8")
    print(f"Wrote {dst} (week ending {new}, status draft, prior composite carried forward)")
    print(f"Holdings expected at: {holdings}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mwir", description="Manifest Weekly Institutional Report builder")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("week", help="weekly inputs file, e.g. weeks/2026-08-28.yaml")
        p.add_argument("--holdings", help="holdings template CSV (overrides holdings_csv in the week file)")
        p.add_argument("--actual", help="actual account weights CSV, same template format; enables drift")
        p.add_argument("--policy", default=str(DEFAULT_POLICY), help="policy file (default: config/policy.yaml)")

    b = sub.add_parser("build", help="run controls and render the PDF")
    common(b)
    b.add_argument("--out", help="output PDF path (default: out/Manifest_MWIR_Week_Ending_<date>_<status>.pdf)")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check", help="run controls only; exit 1 if any fail")
    common(c)
    c.set_defaults(func=cmd_check)

    n = sub.add_parser("new-week", help="start next week's file from this one")
    n.add_argument("week")
    n.add_argument("--holdings", help="holdings_csv path to write into the new file")
    n.add_argument("--out")
    n.add_argument("--force", action="store_true")
    n.set_defaults(func=cmd_new_week)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except InputError as e:
        print(f"Input error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

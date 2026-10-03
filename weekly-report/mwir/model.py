"""Load the weekly inputs and holdings, and compute everything the report shows.

Nothing in here draws. Every number on the PDF that is derived (bands, sleeve
totals, top 10, control assertions, drift) is computed here so it can be
tested and checked without rendering.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
TOLERANCE = 0.005  # percentage points


class InputError(Exception):
    """Raised for inputs the tool cannot build a report from at all."""


@dataclass
class Holding:
    ticker: str
    sleeve: str
    mfpdf: float
    current: float
    band_lo: float
    band_hi: float
    guidance: str
    rationale: str
    status: str
    actual: float | None = None

    @property
    def drift(self) -> str | None:
        if self.actual is None:
            return None
        if self.actual < self.band_lo - TOLERANCE:
            return "BELOW BAND"
        if self.actual > self.band_hi + TOLERANCE:
            return "ABOVE BAND"
        return "IN BAND"


@dataclass
class Assertion:
    label: str
    value: str
    result: str  # PASS / WARN / FAIL / "disclosed"
    detail: str = ""


@dataclass
class Report:
    week: dict
    policy: dict
    week_ending: dt.date
    publication_date: dt.date
    holdings: list[Holding]
    sleeve_totals: dict[str, float]
    total: float
    csv_raw_total: float
    actual_supplied: bool
    assertions: list[Assertion] = field(default_factory=list)

    @property
    def certified(self) -> bool:
        return all(a.result != FAIL for a in self.assertions)

    @property
    def top10(self) -> list[Holding]:
        # Stable sort keeps holdings-file order for ties, as the MWIR does.
        return sorted(self.holdings, key=lambda h: -round(h.current, 2))[:10]

    def gauge_zone(self) -> dict:
        return zone_for(self.week["gauge"]["composite"], self.policy["gauge_zones"])

    def fill(self, text: str) -> str:
        """Replace {placeholders} in narrative text with computed values."""
        values = {
            "total": pct(self.total),
            "positions": str(len(self.holdings)),
            "composite": str(self.week["gauge"]["composite"]),
            "week_ending": long_date(self.week_ending),
            "publication_date": long_date(self.publication_date),
        }

        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key.startswith("sleeve:"):
                sleeve = key.split(":", 1)[1]
                if sleeve in self.sleeve_totals:
                    return pct(self.sleeve_totals[sleeve])
            return values.get(key, m.group(0))

        return re.sub(r"\{([a-z_]+(?::[a-z_]+)?)\}", sub, str(text))


def pct(x: float) -> str:
    return f"{x:.2f}%"


def long_date(d: dt.date) -> str:
    return d.strftime("%d %b %Y").upper()


def zone_for(score: float, zones: list[dict]) -> dict:
    for z in zones:
        if score >= z["min"]:
            return z
    return zones[-1]


def band_for(target: float, bands: dict) -> tuple[float, float]:
    """MWIR-WGT-001: 75%-125% of target, lower bound floored, upper capped.

    The floor never pushes the lower bound above the target itself, and the
    cap never pulls the upper bound below it.
    """
    lo = target * bands["lower_pct_of_target"] / 100
    hi = target * bands["upper_pct_of_target"] / 100
    lo = min(max(lo, bands["floor"]), target)
    hi = max(min(hi, bands["cap"]), target)
    return lo, hi


def _parse_date(value) -> dt.date:
    if isinstance(value, dt.date):
        return value
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            pass
    raise InputError(f"Unrecognised date: {value!r}")


def load_holdings_csv(path: Path) -> tuple[dt.date | None, list[tuple[str, float]]]:
    """Read the holdings template (Date, Symbol, Weights in the first 3 columns).

    Extra template columns to the right are ignored. Weights may be decimals
    (0.035) or percents (3.5); they are returned in percent.
    """
    if not path.exists():
        raise InputError(f"Holdings file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows or [c.strip().lower() for c in rows[0][:3]] != ["date", "symbol", "weights"]:
        raise InputError(f"{path}: first three columns must be Date, Symbol, Weights")

    dates, out, seen = set(), [], set()
    for n, row in enumerate(rows[1:], start=2):
        if len(row) < 3 or not row[1].strip():
            continue
        ticker = row[1].strip().upper()
        if ticker in seen:
            raise InputError(f"{path}:{n}: duplicate ticker {ticker}")
        seen.add(ticker)
        try:
            weight = float(row[2])
        except ValueError:
            raise InputError(f"{path}:{n}: weight for {ticker} is not a number: {row[2]!r}")
        if row[0].strip():
            dates.add(_parse_date(row[0]))
        out.append((ticker, weight))

    if not out:
        raise InputError(f"{path}: no holdings rows")
    if len(dates) > 1:
        raise InputError(f"{path}: rows carry more than one date: {sorted(dates)}")
    if sum(w for _, w in out) <= 1.5:
        out = [(t, w * 100) for t, w in out]
    return (dates.pop() if dates else None), out


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputError(f"File not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build(
    week_path: Path,
    policy_path: Path,
    holdings_path: Path | None = None,
    actual_path: Path | None = None,
) -> Report:
    week = load_yaml(week_path)
    policy = load_yaml(policy_path)
    for key in ("week_ending", "publication_date", "gauge", "holdings"):
        if key not in week:
            raise InputError(f"{week_path}: missing required field '{key}'")

    if holdings_path is None:
        if "holdings_csv" not in week:
            raise InputError("No holdings CSV given (--holdings or holdings_csv in the week file)")
        holdings_path = (week_path.parent / week["holdings_csv"]).resolve()

    week_ending = _parse_date(week["week_ending"])
    publication_date = _parse_date(week["publication_date"])
    csv_date, weights = load_holdings_csv(holdings_path)
    raw_total = sum(w for _, w in weights)

    actual: dict[str, float] = {}
    if actual_path is not None:
        _, actual_rows = load_holdings_csv(actual_path)
        actual = dict(actual_rows)

    sleeves = policy["sleeves"]
    default_status = week.get("default_status", "EVIDENCE HOLD")
    guidance = week["holdings"]
    holdings: list[Holding] = []
    unknown_sleeve = []
    for ticker, weight in weights:
        row = guidance.get(ticker)
        if row is None:
            continue
        sleeve, mfpdf, action, rationale, *rest = row
        if sleeve not in sleeves:
            unknown_sleeve.append(f"{ticker}:{sleeve}")
        lo, hi = band_for(weight, policy["bands"])
        holdings.append(
            Holding(
                ticker=ticker,
                sleeve=sleeve,
                mfpdf=float(mfpdf),
                current=weight,
                band_lo=lo,
                band_hi=hi,
                guidance=str(action),
                rationale=str(rationale),
                status=str(rest[0]) if rest else default_status,
                actual=actual.get(ticker),
            )
        )
    if unknown_sleeve:
        raise InputError(f"Unknown sleeve key(s): {', '.join(unknown_sleeve)}; define them in the policy file")

    sleeve_totals = {k: 0.0 for k in sleeves}
    for h in holdings:
        sleeve_totals[h.sleeve] += h.current

    report = Report(
        week=week,
        policy=policy,
        week_ending=week_ending,
        publication_date=publication_date,
        holdings=holdings,
        sleeve_totals=sleeve_totals,
        total=sum(h.current for h in holdings),
        csv_raw_total=raw_total,
        actual_supplied=actual_path is not None,
    )
    report.assertions = _assert_controls(report, weights, csv_date, actual)
    return report


def _assert_controls(r: Report, weights, csv_date, actual) -> list[Assertion]:
    out: list[Assertion] = []
    week, policy = r.week, r.policy
    csv_tickers = [t for t, _ in weights]
    matrix = set(week["holdings"])
    excluded = week.get("excluded") or {}

    def ok(cond: bool, bad: str = FAIL) -> str:
        return PASS if cond else bad

    # Date on the holdings file matches the report week.
    if csv_date is not None:
        out.append(Assertion(
            "Holdings file date", csv_date.isoformat(), ok(csv_date == r.week_ending),
            "" if csv_date == r.week_ending else f"report week is {r.week_ending.isoformat()}",
        ))

    expected = policy.get("expected_positions")
    n = len(r.holdings)
    out.append(Assertion(
        "Executable holdings", str(n), ok(expected is None or n == expected),
        "" if expected is None or n == expected else f"policy expects {expected}",
    ))

    out.append(Assertion(
        "Executable target total", pct(r.total), ok(abs(r.total - 100) <= TOLERANCE),
    ))

    missing = [t for t in csv_tickers if t not in matrix and t not in excluded]
    orphan = sorted(matrix - set(csv_tickers))
    detail = "; ".join(filter(None, [
        f"in CSV, no guidance: {', '.join(missing)}" if missing else "",
        f"guidance, not in CSV: {', '.join(orphan)}" if orphan else "",
    ]))
    covered = len(csv_tickers) - len(missing)
    out.append(Assertion("Guidance coverage", f"{covered}/{len(csv_tickers)}",
                         ok(not missing and not orphan), detail))

    for ticker, info in excluded.items():
        rows = sum(1 for t in csv_tickers if t == ticker)
        out.append(Assertion(f"{ticker} executable rows", str(rows), ok(rows == 0)))

    # Redistribution must keep each affected sleeve's share of the model the
    # same as its share of the MFPDF baseline (including the excluded name).
    mfpdf_total = sum(h.mfpdf for h in r.holdings) + sum(float(e["mfpdf"]) for e in excluded.values())
    for sleeve in sorted({e["sleeve"] for e in excluded.values()}):
        base = sum(h.mfpdf for h in r.holdings if h.sleeve == sleeve) + sum(
            float(e["mfpdf"]) for e in excluded.values() if e["sleeve"] == sleeve)
        want = base / mfpdf_total * 100 if mfpdf_total else 0
        got = r.sleeve_totals[sleeve] / r.total * 100 if r.total else 0
        out.append(Assertion(
            f"{policy['sleeves'][sleeve]['name']} (redistributed)", pct(r.sleeve_totals[sleeve]),
            ok(abs(got - want) <= 0.05),
            "" if abs(got - want) <= 0.05 else f"expected {pct(want)} of model after redistribution",
        ))

    # The baseline itself should sum to 100%; a gap usually means a position
    # fell out of the matrix. Disclosed, not blocking: the executable model is
    # what gets certified.
    out.append(Assertion(
        "MFPDF baseline total", pct(mfpdf_total), ok(abs(mfpdf_total - 100) <= 0.05, WARN),
        "" if abs(mfpdf_total - 100) <= 0.05 else "baseline does not sum to 100%; executable targets normalised from CSV",
    ))

    if abs(r.csv_raw_total - 100) > TOLERANCE:
        out.append(Assertion("Holdings CSV raw total", pct(r.csv_raw_total), WARN, "CSV weights do not sum to 100%"))

    cap = policy["bands"]["cap"]
    over = [h.ticker for h in r.holdings if h.current > cap + TOLERANCE]
    out.append(Assertion("Targets within cap", f"max {pct(max(h.current for h in r.holdings))}",
                         ok(not over), f"over {pct(cap)}: {', '.join(over)}" if over else ""))

    allowed = set(policy.get("guidance_actions") or [])
    bad = [f"{h.ticker}={h.guidance}" for h in r.holdings if allowed and h.guidance not in allowed]
    out.append(Assertion("Guidance vocabulary", f"{len(r.holdings) - len(bad)}/{len(r.holdings)}", ok(not bad), ", ".join(bad)))

    if r.actual_supplied:
        below = sum(1 for h in r.holdings if h.drift == "BELOW BAND")
        above = sum(1 for h in r.holdings if h.drift == "ABOVE BAND")
        absent = [h.ticker for h in r.holdings if h.actual is None]
        out.append(Assertion("Actual weights", f"{below} below / {above} above band", "disclosed",
                             f"no actual weight: {', '.join(absent)}" if absent else ""))
    else:
        out.append(Assertion("Actual weights", "unavailable", "disclosed"))

    for label, value in week.get("disclosures") or []:
        out.append(Assertion(str(label), str(value), "disclosed"))
    return out

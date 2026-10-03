from pathlib import Path

import pytest
import yaml

from mwir.cli import main
from mwir.model import FAIL, PASS, WARN, InputError, band_for, build, load_holdings_csv

ROOT = Path(__file__).resolve().parent.parent
WEEK = ROOT / "weeks" / "2026-08-28.yaml"
POLICY = ROOT / "config" / "policy.yaml"
CSV = ROOT / "holdings" / "2026-08-28.csv"
BANDS = {"lower_pct_of_target": 75, "upper_pct_of_target": 125, "floor": 1.0, "cap": 4.0}


def result(report, label):
    return next(a for a in report.assertions if a.label.startswith(label)).result


def write_csv(path, rows, date="8/28/2026"):
    path.write_text("Date,Symbol,Weights\n" + "".join(f"{date},{t},{w}\n" for t, w in rows))
    return path


def test_bands_match_published_mwir():
    # Values from the 28 Aug 2026 MWIR holding matrix.
    assert [round(x, 2) for x in band_for(3.49, BANDS)] == [2.62, 4.00]  # cap
    assert [round(x, 2) for x in band_for(1.85, BANDS)] == [1.39, 2.31]
    assert [round(x, 2) for x in band_for(3.02, BANDS)] == [2.27, 3.77]


def test_floor_never_exceeds_target():
    assert band_for(0.8, BANDS) == (0.8, 1.0)
    assert band_for(1.2, BANDS)[0] == 1.0


def test_template_csv_reads_first_three_columns_as_percent():
    date, rows = load_holdings_csv(CSV)
    assert str(date) == "2026-08-28"
    assert len(rows) == 45
    assert rows[0][0] == "COST" and rows[0][1] == pytest.approx(3.5987)
    assert sum(w for _, w in rows) == pytest.approx(100)


def test_example_week_certifies():
    r = build(WEEK, POLICY)
    assert r.certified
    assert r.total == pytest.approx(100)
    assert [h.ticker for h in r.top10] == ["COST", "JNJ", "MSFT", "V", "GOOGL", "AVGO", "LLY", "CME", "LNG", "VPU"]
    assert result(r, "Strategic Anchors") == PASS
    # The frozen baseline in the 28 Aug report sums to 96.98%, not 100%.
    assert result(r, "MFPDF baseline total") == WARN
    assert r.fill("{positions}-position, {total}, {sleeve:energy}, {unknown}") == "45-position, 100.00%, 12.08%, {unknown}"


def test_missing_guidance_and_excluded_name_fail(tmp_path):
    _, rows = load_holdings_csv(CSV)
    rows = rows[1:] + [("BRK.B", 3.0), ("XYZ", 0.5)]
    r = build(WEEK, POLICY, write_csv(tmp_path / "h.csv", rows))
    assert not r.certified
    assert result(r, "Guidance coverage") == FAIL
    assert result(r, "BRK.B executable rows") == FAIL
    assert result(r, "Executable holdings") == FAIL


def test_wrong_date_and_bad_vocabulary_fail(tmp_path):
    _, rows = load_holdings_csv(CSV)
    week = yaml.safe_load(WEEK.read_text())
    week["holdings"]["COST"][2] = "MAINTIAN"
    week["holdings_csv"] = str(write_csv(tmp_path / "h.csv", rows, date="9/4/2026"))
    wp = tmp_path / "w.yaml"
    wp.write_text(yaml.safe_dump(week))
    r = build(wp, POLICY)
    assert result(r, "Holdings file date") == FAIL
    assert result(r, "Guidance vocabulary") == FAIL


def test_actual_weights_classify_drift(tmp_path):
    _, rows = load_holdings_csv(CSV)
    actual = dict(rows)
    actual["COST"] = 2.0   # below 2.70 lower band
    actual["NVDA"] = 5.0   # above band
    r = build(WEEK, POLICY, actual_path=write_csv(tmp_path / "a.csv", actual.items()))
    drift = {h.ticker: h.drift for h in r.holdings}
    assert drift["COST"] == "BELOW BAND"
    assert drift["NVDA"] == "ABOVE BAND"
    assert drift["JNJ"] == "IN BAND"


def test_bad_csv_header_is_an_input_error(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("Ticker,Weight\nAAPL,1\n")
    with pytest.raises(InputError):
        load_holdings_csv(p)


def test_build_writes_pdf(tmp_path):
    out = tmp_path / "r.pdf"
    assert main(["build", str(WEEK), "--out", str(out)]) == 0
    assert out.read_bytes()[:5] == b"%PDF-"


def test_overflowing_text_is_a_layout_error(tmp_path):
    week = yaml.safe_load(WEEK.read_text())
    week["holdings_csv"] = str(CSV)
    week["executive_summary"] = [["Too long", "word " * 3000]]
    wp = tmp_path / "w.yaml"
    wp.write_text(yaml.safe_dump(week))
    assert main(["build", str(wp), "--out", str(tmp_path / "r.pdf")]) == 3


def test_new_week_rolls_forward(tmp_path):
    src = tmp_path / "2026-08-28.yaml"
    src.write_text(WEEK.read_text())
    assert main(["new-week", str(src)]) == 0
    new = yaml.safe_load((tmp_path / "2026-09-04.yaml").read_text())
    assert str(new["week_ending"]) == "2026-09-04"
    assert str(new["publication_date"]) == "2026-09-07"
    assert new["status"] == "draft"
    assert new["gauge"]["prior_composite"] == 62
    assert new["holdings_csv"] == "../holdings/2026-09-04.csv"

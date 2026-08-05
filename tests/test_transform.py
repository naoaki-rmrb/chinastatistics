"""transform の派生列計算のオフライン検証。

NBS へは接続しない。合成データで YoY / MoM / 乖離 / 単月復元 を確認する。
実行: PYTHONPATH=src python -m pytest tests/ -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chinastats.transform import detect_base_revisions, records_to_frame  # noqa: E402


def _rec(indicator, kind, freq, code, year, sub, period, value, official=None):
    return {
        "indicator": indicator, "level_kind": kind,
        "name_zh": "z", "name_ja": "j", "name_en": "e",
        "unit_zh": "u", "unit_ja": "u", "unit_en": "u",
        "freq": freq, "region_code": code, "region_zh": "全国", "region_ja": "全国",
        "period": period, "year": year, "sub": sub,
        "value": value, "official_yoy": official,
    }


def test_yoy_and_gap_monthly():
    recs = [
        _rec("retail", "current", "monthly", "000000", 2023, 6, "2023-06", 100, official=5.0),
        _rec("retail", "current", "monthly", "000000", 2024, 6, "2024-06", 110, official=8.0),
    ]
    df = records_to_frame(recs)
    row = df[df["period"] == "2024-06"].iloc[0]
    # 110/100 - 1 = 10%
    assert abs(row["computed_yoy"] - 10.0) < 1e-9
    # 乖離 = 計算(10) - 公式(8) = +2  → 公式が低い＝改定嵩上げの疑い方向
    assert abs(row["yoy_gap"] - 2.0) < 1e-9


def test_mom_monthly():
    recs = [
        _rec("retail", "current", "monthly", "000000", 2024, 5, "2024-05", 200),
        _rec("retail", "current", "monthly", "000000", 2024, 6, "2024-06", 210),
    ]
    df = records_to_frame(recs)
    row = df[df["period"] == "2024-06"].iloc[0]
    assert abs(row["mom"] - 5.0) < 1e-9  # 210/200-1


def test_january_gap_does_not_break_yoy():
    # 1月欠測でも「同月前年」で厳密対応する
    recs = [
        _rec("retail", "current", "monthly", "000000", 2023, 2, "2023-02", 100),
        _rec("retail", "current", "monthly", "000000", 2023, 3, "2023-03", 105),
        _rec("retail", "current", "monthly", "000000", 2024, 2, "2024-02", 120),
        _rec("retail", "current", "monthly", "000000", 2024, 3, "2024-03", 130),
    ]
    df = records_to_frame(recs)
    r2 = df[df["period"] == "2024-02"].iloc[0]
    r3 = df[df["period"] == "2024-03"].iloc[0]
    assert abs(r2["computed_yoy"] - 20.0) < 1e-9   # 120/100
    assert abs(r3["computed_yoy"] - (130/105-1)*100) < 1e-9
    # 2024-02 の前月比は 2024-01 が無いので None（1月へ遡らない）
    assert r2["mom"] is None or (r2["mom"] != r2["mom"])  # None or NaN


def test_cumulative_single_month_reconstruction():
    # 累計: 3月累計=300, 4月累計=450 → 4月単月=150
    recs = [
        _rec("re_investment", "cumulative", "monthly", "000000", 2024, 3, "2024-03", 300),
        _rec("re_investment", "cumulative", "monthly", "000000", 2024, 4, "2024-04", 450),
    ]
    df = records_to_frame(recs)
    r4 = df[df["period"] == "2024-04"].iloc[0]
    assert abs(r4["single_month"] - 150.0) < 1e-9


def test_quarterly_yoy():
    recs = [
        _rec("gdp", "current", "quarterly", "000000", 2023, 2, "2023-Q2", 1000, official=5.0),
        _rec("gdp", "current", "quarterly", "000000", 2024, 2, "2024-Q2", 1060, official=6.0),
    ]
    df = records_to_frame(recs)
    row = df[df["period"] == "2024-Q2"].iloc[0]
    assert abs(row["computed_yoy"] - 6.0) < 1e-9
    assert abs(row["yoy_gap"] - 0.0) < 1e-9


def test_detect_base_revision():
    prev = records_to_frame([
        _rec("retail", "current", "monthly", "000000", 2023, 6, "2023-06", 100),
    ])
    cur = records_to_frame([
        _rec("retail", "current", "monthly", "000000", 2023, 6, "2023-06", 95),  # 下方改定
    ])
    rev = detect_base_revisions(cur, prev)
    assert len(rev) == 1
    assert abs(rev.iloc[0]["diff"] - (-5.0)) < 1e-9
    assert rev.iloc[0]["pct_change"] < 0

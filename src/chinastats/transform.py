"""tidy レコードから前年比・前月比・乖離を計算する。

計算する派生列:
  computed_yoy   : 計算前年比 = value / 前年同期 value - 1  (%)
  official_yoy   : NBS 公表の同比（取得値をそのまま％で）
  yoy_gap        : 乖離 = computed_yoy - official_yoy (%ポイント)
                   → 大きな正の乖離は「前年値の下方改定で公式同比が
                     嵩上げされた」疑いのシグナル
  mom            : 前月比(月次) / 前期比(四半期) = value / 直前期 value - 1 (%)
  single_month   : 累計指標のとき、累計から復元した単月値
  single_mom     : 単月値ベースの前月比 (%)

前年同期・直前期は「暦上の同月/前月」で厳密に対応付ける
（1月欠測などの穴で誤ってずれないように）。
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _prev_period(freq: str, year: int, sub: int) -> tuple[int, int]:
    """直前期 (year, sub) を返す。"""
    if freq == "monthly":
        if sub == 1:
            return year - 1, 12
        return year, sub - 1
    # quarterly
    if sub == 1:
        return year - 1, 4
    return year, sub - 1


def records_to_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """レコード列を DataFrame にし、派生列を計算する。"""
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)
    # 型の正規化
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["official_yoy"] = pd.to_numeric(df["official_yoy"], errors="coerce")
    df["year"] = df["year"].astype(int)
    df["sub"] = df["sub"].astype(int)

    # 高速参照用のルックアップ: (indicator, region_code, year, sub) -> value
    val_lookup: dict[tuple, float] = {}
    for row in df.itertuples(index=False):
        val_lookup[(row.indicator, row.region_code, row.year, row.sub)] = row.value

    computed_yoy: list[float | None] = []
    mom: list[float | None] = []
    single_month: list[float | None] = []
    single_mom: list[float | None] = []
    yoy_gap: list[float | None] = []

    # 累計指標かどうかは indicator ごとに判定する必要があるが、
    # records には level_kind を載せていないので、ヒューリスティックに
    # 「同一年内で概ね単調増加」なら累計とみなす…のは不安定。
    # ここでは呼び出し側が付与する 'level_kind' 列があれば使う。
    has_kind = "level_kind" in df.columns

    for row in df.itertuples(index=False):
        key = (row.indicator, row.region_code)
        value = row.value

        # --- 計算前年比 (YoY) ---
        py_val = val_lookup.get((row.indicator, row.region_code, row.year - 1, row.sub))
        if value is not None and py_val not in (None, 0) and pd.notna(value) and pd.notna(py_val):
            cy = (value / py_val - 1.0) * 100.0
        else:
            cy = None
        computed_yoy.append(cy)

        # --- 乖離 = 計算 - 公式 ---
        off = row.official_yoy
        if cy is not None and off is not None and pd.notna(off):
            yoy_gap.append(cy - off)
        else:
            yoy_gap.append(None)

        # --- 前月比 / 前期比 (level ベース) ---
        pyear, psub = _prev_period(row.freq, row.year, row.sub)
        prev_val = val_lookup.get((row.indicator, row.region_code, pyear, psub))
        if value is not None and prev_val not in (None, 0) and pd.notna(value) and pd.notna(prev_val):
            mom.append((value / prev_val - 1.0) * 100.0)
        else:
            mom.append(None)

        # --- 累計 → 単月復元 ---
        kind = getattr(row, "level_kind", None) if has_kind else None
        if kind == "cumulative" and value is not None and pd.notna(value):
            if row.sub == 1 or (row.freq == "quarterly" and row.sub == 1):
                # 年初（1月 or Q1）は累計＝単月
                sm = value
            else:
                prev_cum = val_lookup.get((row.indicator, row.region_code, pyear, psub))
                if prev_cum is not None and pd.notna(prev_cum) and pyear == row.year:
                    sm = value - prev_cum
                else:
                    sm = None
            single_month.append(sm)
        else:
            single_month.append(None)

    df["computed_yoy"] = computed_yoy
    df["official_yoy_pct"] = df["official_yoy"]
    df["yoy_gap"] = yoy_gap
    df["mom"] = mom
    df["single_month"] = single_month

    # 単月ベースの前月比（単月列がある行だけ）
    sm_lookup: dict[tuple, float] = {}
    for row in df.itertuples(index=False):
        if pd.notna(row.single_month):
            sm_lookup[(row.indicator, row.region_code, row.year, row.sub)] = row.single_month
    for row in df.itertuples(index=False):
        if pd.isna(row.single_month):
            single_mom.append(None)
            continue
        pyear, psub = _prev_period(row.freq, row.year, row.sub)
        prev_sm = sm_lookup.get((row.indicator, row.region_code, pyear, psub))
        if prev_sm not in (None, 0) and prev_sm is not None and pd.notna(prev_sm):
            single_mom.append((row.single_month / prev_sm - 1.0) * 100.0)
        else:
            single_mom.append(None)
    df["single_mom"] = single_mom

    # ソート: 指標→地区→時点
    df = df.sort_values(
        ["indicator", "region_code", "year", "sub"], kind="stable"
    ).reset_index(drop=True)
    return df


def detect_base_revisions(
    current: pd.DataFrame, previous: pd.DataFrame | None
) -> pd.DataFrame:
    """前回スナップショット(previous)と比較し、過去値の改定を検出する。

    毎月コミットしているため、previous には「先月時点で公表されていた
    過去の水準」が入っている。同じ (indicator, region, period) で
    value が変わっていれば改定。特に「昨年同期が下方改定」されると
    公式前年比が嵩上げされるため、その差分を明示する。

    Returns
    -------
    DataFrame(columns: indicator, region_zh, period, old_value, new_value,
              diff, pct_change)
    """
    if previous is None or previous.empty or current.empty:
        return pd.DataFrame(
            columns=["indicator", "name_ja", "region_zh", "period",
                     "old_value", "new_value", "diff", "pct_change"]
        )

    key = ["indicator", "region_code", "period"]
    cur = current[key + ["name_ja", "region_zh", "value"]].copy()
    prev = previous[key + ["value"]].copy().rename(columns={"value": "old_value"})
    merged = cur.merge(prev, on=key, how="inner")
    merged = merged.rename(columns={"value": "new_value"})
    merged["old_value"] = pd.to_numeric(merged["old_value"], errors="coerce")
    merged["new_value"] = pd.to_numeric(merged["new_value"], errors="coerce")
    merged = merged.dropna(subset=["old_value", "new_value"])
    merged["diff"] = merged["new_value"] - merged["old_value"]
    # 微小な丸め差は無視（0.01%超の変化のみ改定とみなす）
    denom = merged["old_value"].replace(0, pd.NA)
    merged["pct_change"] = (merged["diff"] / denom) * 100.0
    revised = merged[merged["pct_change"].abs() > 0.01].copy()
    revised = revised.sort_values("pct_change").reset_index(drop=True)
    return revised[["indicator", "name_ja", "region_zh", "period",
                    "old_value", "new_value", "diff", "pct_change"]]

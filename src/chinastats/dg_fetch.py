"""新版DG APIから指標×地区×期間を取得し、tidyレコードにする。

各レポートは DA=000000000000(全国) の1回で、対象地区の全行が返る:
  - scope=national   → 全国のみ
  - scope=provincial → 全国＋31省
返却行から対象指標(EK_NAME==target)を抜き、DP_NAMEで
  値(本期/本期累计, 単位≠%) と 公式同比(同比を含むDP_NAME) を取り出す。
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from .dg_client import DGClient

logger = logging.getLogger(__name__)


def _months(from_yyyymm: str) -> list[str]:
    """from(YYYYMM)〜当月 の "YYYYMM"+"MM" 期間コード一覧。"""
    y, m = int(from_yyyymm[:4]), int(from_yyyymm[4:6])
    now = _dt.date.today()
    out = []
    while (y, m) <= (now.year, now.month):
        out.append(f"{y}{m:02d}MM")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_yoy(dp_name: str | None) -> bool:
    return bool(dp_name) and "同比" in dp_name


def _is_level(row: dict) -> bool:
    du = row.get("DU_NAME")
    dp = row.get("DP_NAME") or ""
    return du != "%" and ("同比" not in dp) and ("环比" not in dp)


def fetch_indicator(
    client: DGClient,
    ind: dict[str, Any],
    regions_by_name: dict[str, dict],
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    freq = ind["freq"]
    if freq != "monthly":
        logger.info("[%s] freq=%s は現状スキップ(月次のみ実装)", ind["key"], freq)
        return []
    periods = _months(settings.get("monthly_from", "201001"))
    target = ind["target"]
    records: list[dict] = []
    got = 0
    for dt in periods:
        rows = client.query_data(ind["report_id"], "000000000000", dt)
        if not rows:
            continue
        # (DA_NAME) -> {level, yoy, year, sub, period}
        by_region: dict[str, dict] = {}
        for r in rows:
            if r.get("EK_NAME") != target:
                continue
            da_name = r.get("DA_NAME")
            reg = regions_by_name.get(da_name)
            if reg is None:
                continue
            dtcode = str(r.get("DT") or dt)
            year = int(dtcode[:4])
            sub = int(dtcode[4:6])
            key = da_name
            slot = by_region.setdefault(key, {
                "region_code": reg["code"], "region_zh": reg["name_zh"],
                "region_ja": reg.get("name_ja", reg["name_zh"]),
                "year": year, "sub": sub, "period": f"{year}-{sub:02d}",
                "value": None, "official_yoy": None,
            })
            val = _num(r.get("V"))
            if val is None:
                continue
            if _is_yoy(r.get("DP_NAME")):
                if slot["official_yoy"] is None:
                    slot["official_yoy"] = val
            elif _is_level(r):
                if slot["value"] is None:
                    slot["value"] = val
        for slot in by_region.values():
            if slot["value"] is None and slot["official_yoy"] is None:
                continue
            records.append({
                "indicator": ind["key"], "level_kind": ind.get("level_kind"),
                "name_zh": ind["name_zh"], "name_ja": ind["name_ja"], "name_en": ind["name_en"],
                "unit_zh": ind.get("unit_zh"), "unit_ja": ind.get("unit_ja"),
                "unit_en": ind.get("unit_en"),
                "freq": "monthly",
                "region_code": slot["region_code"], "region_zh": slot["region_zh"],
                "region_ja": slot["region_ja"],
                "period": slot["period"], "year": slot["year"], "sub": slot["sub"],
                "value": slot["value"], "official_yoy": slot["official_yoy"],
            })
            got += 1
    logger.info("[%s] 取得 %d レコード (%d 期間)", ind["key"], got, len(periods))
    return records


def fetch_all(client: DGClient, config: dict, regions_config: dict) -> list[dict]:
    settings = config.get("settings", {})
    regions_by_name: dict[str, dict] = {}
    nat = regions_config.get("national")
    if nat:
        regions_by_name[nat["name_zh"]] = nat
    for r in regions_config.get("provinces", []):
        regions_by_name[r["name_zh"]] = r

    out: list[dict] = []
    for ind in config.get("indicators", []):
        if ind.get("enabled") is False:
            continue
        out.extend(fetch_indicator(client, ind, regions_by_name, settings))
    return out

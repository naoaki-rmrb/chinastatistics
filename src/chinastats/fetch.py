"""指標×地区の時系列をNBSから取得し、tidy なレコード列にする。

出力レコード(1行 = 1指標×1地区×1時点):
  {
    indicator, name_zh, name_ja, name_en, unit_zh, unit_ja, unit_en,
    freq, region_code, region_zh, region_ja,
    period,          # 内部キー "YYYY-MM"(月次) / "YYYY-Qn"(四半期)
    year, sub,       # sub = 月(1-12) or 四半期(1-4)
    value,           # 水準
    official_yoy,    # NBS公表の同比(%)。無ければ None
  }
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from .nbs_client import NBSClient, parse_datanodes
from .resolver import Resolver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 時間コードの解釈
# ---------------------------------------------------------------------
def parse_sj_code(freq: str, code: str) -> tuple[int, int, str] | None:
    """NBS の時間コードを (year, sub, period_key) に変換する。

    月次: "202401" -> (2024, 1, "2024-01")
    四半期: "2024A"/"2024B"/"2024C"/"2024D" -> (2024, 1..4, "2024-Q1")
            "202401"形式で来た場合は 03->Q1,06->Q2,09->Q3,12->Q4 とみなす
    """
    code = str(code).strip()
    if freq == "monthly":
        m = re.fullmatch(r"(\d{4})(\d{2})", code)
        if m:
            y, mm = int(m.group(1)), int(m.group(2))
            if 1 <= mm <= 12:
                return y, mm, f"{y}-{mm:02d}"
        return None

    # quarterly
    m = re.fullmatch(r"(\d{4})([A-D])", code)
    if m:
        y = int(m.group(1))
        q = "ABCD".index(m.group(2)) + 1
        return y, q, f"{y}-Q{q}"
    m = re.fullmatch(r"(\d{4})(\d{2})", code)
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        q = {3: 1, 6: 2, 9: 3, 12: 4}.get(mm)
        if q:
            return y, q, f"{y}-Q{q}"
    return None


# ---------------------------------------------------------------------
def _series(
    client: NBSClient,
    dbcode: str,
    zb_code: str,
    freq: str,
    sj_valuecode: str,
    reg_code: str | None,
) -> dict[str, tuple[int, int, float]]:
    """1系列を取得して {period_key: (year, sub, value)} を返す。"""
    returndata = client.query_data(
        dbcode=dbcode,
        zb_code=zb_code,
        sj_valuecode=sj_valuecode,
        reg_code=reg_code,
    )
    raw = parse_datanodes(returndata)  # {sj_code: value}
    out: dict[str, tuple[int, int, float]] = {}
    for sj_code, val in raw.items():
        parsed = parse_sj_code(freq, sj_code)
        if parsed is None:
            continue
        year, sub, key = parsed
        out[key] = (year, sub, val)
    return out


def fetch_indicator(
    client: NBSClient,
    resolver: Resolver,
    databases: dict[str, dict[str, str]],
    indicator: dict[str, Any],
    regions: list[dict[str, str]],
    national: dict[str, str] | None,
    sj_valuecode_monthly: str,
    sj_valuecode_quarterly: str,
) -> list[dict[str, Any]]:
    """1指標について全地区(全国+省)の水準と公式同比を取得する。"""
    freq = indicator["freq"] if "freq" in indicator else indicator["frequency"]
    db = databases["monthly"] if freq == "monthly" else databases["quarterly"]
    sj_code = sj_valuecode_monthly if freq == "monthly" else sj_valuecode_quarterly

    records: list[dict[str, Any]] = []

    # 対象地区: 全国(reg=None, national DB) + 各省(reg=code, province DB)
    targets: list[tuple[str, str | None, str, str, str]] = []
    if national is not None:
        targets.append((db["national"], None, national["code"],
                        national["name_zh"], national.get("name_ja", national["name_zh"])))
    for r in regions:
        targets.append((db["province"], r["code"], r["code"], r["name_zh"], r["name_ja"]))

    # 指標コードは DB ごとに1回だけ解決する
    level_code_cache: dict[str, str | None] = {}
    yoy_code_cache: dict[str, str | None] = {}

    for dbcode, reg_code, region_code, region_zh, region_ja in targets:
        scope = "national" if reg_code is None else "province"
        # --- 水準系列のコード解決 ---
        if dbcode not in level_code_cache:
            cands = indicator["level"].get(f"match_{scope}", [])
            code, matched = resolver.resolve(
                dbcode, cands, context={"indicator": indicator["key"], "role": "level"})
            if code is None:
                logger.warning("[%s] 水準コード未解決 db=%s 候補=%s",
                               indicator["key"], dbcode, cands)
            else:
                logger.info("[%s] 水準コード解決 db=%s -> %s (%s)",
                            indicator["key"], dbcode, code, matched)
            level_code_cache[dbcode] = code
        level_code = level_code_cache[dbcode]

        # --- 公式同比系列のコード解決 ---
        if dbcode not in yoy_code_cache:
            yoy_spec = indicator.get("official_yoy") or {}
            cands = yoy_spec.get(f"match_{scope}", [])
            code, matched = (
                resolver.resolve(
                    dbcode, cands,
                    context={"indicator": indicator["key"], "role": "official_yoy"})
                if cands else (None, None)
            )
            if cands and code is None:
                logger.info("[%s] 公式同比コード未解決 db=%s（欠測扱い）",
                            indicator["key"], dbcode)
            yoy_code_cache[dbcode] = code
        yoy_code = yoy_code_cache[dbcode]

        level_series: dict[str, tuple[int, int, float]] = {}
        yoy_series: dict[str, tuple[int, int, float]] = {}
        if level_code:
            try:
                level_series = _series(client, dbcode, level_code, freq, sj_code, reg_code)
            except Exception as exc:  # noqa: BLE001 - 1地区の失敗で全体を止めない
                logger.warning("[%s] 水準取得失敗 region=%s: %s",
                               indicator["key"], region_zh, exc)
        if yoy_code:
            try:
                yoy_series = _series(client, dbcode, yoy_code, freq, sj_code, reg_code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] 公式同比取得失敗 region=%s: %s",
                               indicator["key"], region_zh, exc)

        # 水準の期間を基準にレコード化（同比のみ存在する期間も拾う）
        all_keys = set(level_series) | set(yoy_series)
        for key in all_keys:
            if key in level_series:
                year, sub, value = level_series[key]
            else:
                year, sub, _ = yoy_series[key]
                value = None
            official = yoy_series.get(key, (None, None, None))[2]
            records.append({
                "indicator": indicator["key"],
                "level_kind": indicator.get("level_kind"),
                "name_zh": indicator["name_zh"],
                "name_ja": indicator["name_ja"],
                "name_en": indicator["name_en"],
                "unit_zh": indicator.get("unit_zh"),
                "unit_ja": indicator.get("unit_ja"),
                "unit_en": indicator.get("unit_en"),
                "freq": freq,
                "region_code": region_code,
                "region_zh": region_zh,
                "region_ja": region_ja,
                "period": key,
                "year": year,
                "sub": sub,
                "value": value,
                "official_yoy": official,
            })

    logger.info("[%s] 取得完了: %d レコード", indicator["key"], len(records))
    return records


def fetch_all(
    client: NBSClient,
    resolver: Resolver,
    config: dict[str, Any],
    regions_config: dict[str, Any],
    settings: dict[str, Any],
    only: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """全指標×全地区を取得して1本のレコード列にまとめる。"""
    databases = config["databases"]
    indicators = config["indicators"]
    if only:
        only = set(only)
        indicators = [i for i in indicators if i["key"] in only]

    national = regions_config.get("national")
    provinces = regions_config.get("provinces", [])

    sj_m = settings.get("sj_valuecode_monthly", "LAST120")
    sj_q = settings.get("sj_valuecode_quarterly", "LAST80")

    all_records: list[dict[str, Any]] = []
    for ind in indicators:
        # frequency キー名の揺れを吸収
        if "freq" not in ind and "frequency" in ind:
            ind = {**ind, "freq": ind["frequency"]}
        all_records.extend(
            fetch_indicator(
                client=client,
                resolver=resolver,
                databases=databases,
                indicator=ind,
                regions=provinces,
                national=national,
                sj_valuecode_monthly=sj_m,
                sj_valuecode_quarterly=sj_q,
            )
        )
    return all_records

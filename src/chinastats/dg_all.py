"""新版DG API 汎用エンジン: 月度カタログの全レポート×全指標×全地区×全期間を取得。

- queryPbLibCatalogTree(code=1) で月度の全レポートを列挙
- 各レポートを月ごとに queryMacroReportDataById(REPORTID, DA=全国, DT=YYYYMM+MM)
  → 1回で全地区・全指標・全DP(本期/同比/累计/累计同比)が返る
- DPをピボットして level / official_yoy を作り、computed_yoy / mom を pandas で計算
- 出力:
    output/dg_master.csv.gz   全件tidy(圧縮)
    output/dg_index.csv       レポート一覧(名前・report_id・行数)
- インクリメンタル: 既存master を読み、未取得期間＋直近数か月(改定用)だけ取得してマージ
"""

from __future__ import annotations

import datetime as _dt
import gzip
import logging
import os
from pathlib import Path

import pandas as pd

from .dg_client import DGClient, walk_catalog

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output"
MASTER = OUTPUT / "dg_master.csv.gz"
INDEX = OUTPUT / "dg_index.csv"
NAT = "000000000000"

DP_LEVEL = {"本期", "本期累计", "本期累计值", "本期值"}
DP_YOY = {"同比增减%", "累计同比增减%", "同比增长%", "累计同比增长%"}

KEEP_DP = DP_LEVEL | DP_YOY | {"本期", "累计"}


def months(start_yyyymm: str, end: tuple[int, int]) -> list[str]:
    y, m = int(start_yyyymm[:4]), int(start_yyyymm[4:6])
    ey, em = end
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y}{m:02d}MM")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _now_ym() -> tuple[int, int]:
    d = _dt.datetime.now(_dt.timezone.utc)
    return d.year, d.month


def list_monthly_reports(client: DGClient) -> list[dict]:
    tree = client.catalog_tree(1)
    leaves = walk_catalog(tree)
    for lf in leaves:
        lf["freq"] = "monthly"
    return leaves


def fetch_records(client: DGClient, reports: list[dict], periods: list[str],
                  sleep_log_every: int = 200) -> list[dict]:
    recs: list[dict] = []
    n = 0
    for rp in reports:
        rid = rp["report_id"]
        rname = rp["name"]
        got = 0
        for dt in periods:
            rows = client.query_data(rid, NAT, dt)
            n += 1
            for r in rows:
                dp = r.get("DP_NAME")
                if dp not in KEEP_DP:
                    continue
                v = r.get("V")
                if v in (None, ""):
                    continue
                recs.append({
                    "report": rname, "report_id": rid,
                    "indicator": r.get("EK_NAME") or r.get("I_NAME"),
                    "i_name": r.get("I_NAME"), "kj1": r.get("KJ1_NAME"),
                    "region_code": r.get("DA"), "region_name": r.get("DA_NAME"),
                    "period": _period(dt), "dp": dp, "unit": r.get("DU_NAME"),
                    "v": v,
                })
                got += 1
            if n % sleep_log_every == 0:
                logger.info("...%d calls, %d rows", n, len(recs))
        logger.info("[%s] %d rows (report_id=%s)", rname, got, rid)
    return recs


def _period(dt: str) -> str:
    # "202506MM" -> "2025-06"
    return f"{dt[:4]}-{dt[4:6]}"


def to_processed(df_raw: pd.DataFrame) -> pd.DataFrame:
    """DPをピボットして level/official_yoy を作り、computed_yoy/mom を計算。"""
    if df_raw.empty:
        return df_raw
    df = df_raw.copy()
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    df["is_yoy"] = df["dp"].isin(DP_YOY)
    df["is_level"] = df["dp"].isin(DP_LEVEL) & (df["unit"] != "%")

    key = ["report", "report_id", "indicator", "region_code", "region_name", "period"]
    level = (df[df["is_level"]].groupby(key, as_index=False)
             .agg(level=("v", "first"), unit=("unit", "first")))
    yoy = (df[df["is_yoy"]].groupby(key, as_index=False)
           .agg(official_yoy=("v", "first")))
    out = level.merge(yoy, on=key, how="outer")

    # computed_yoy / mom（同一 report×indicator×region 内で期間比較）
    out["year"] = out["period"].str[:4].astype(int)
    out["mon"] = out["period"].str[5:7].astype(int)
    out = out.sort_values(["report_id", "indicator", "region_code", "year", "mon"])
    g = out.groupby(["report_id", "indicator", "region_code"], group_keys=False)

    def _derive(sub: pd.DataFrame) -> pd.DataFrame:
        sub = sub.copy()
        lut = {(r.year, r.mon): r.level for r in sub.itertuples(index=False)}
        cy, mo = [], []
        prev = {}
        for r in sub.itertuples(index=False):
            py = lut.get((r.year - 1, r.mon))
            cy.append((r.level / py - 1) * 100 if pd.notna(r.level) and py not in (None, 0)
                      and pd.notna(py) else None)
            pm = prev.get("v")
            mo.append((r.level / pm - 1) * 100 if pd.notna(r.level) and pm not in (None, 0)
                      and pm is not None and pd.notna(pm) else None)
            prev["v"] = r.level
        sub["computed_yoy"] = cy
        sub["mom"] = mo
        return sub

    out = g.apply(_derive)
    out["yoy_gap"] = out.apply(
        lambda r: (r["computed_yoy"] - r["official_yoy"])
        if pd.notna(r.get("computed_yoy")) and pd.notna(r.get("official_yoy")) else None,
        axis=1)
    return out.drop(columns=["year", "mon"]).reset_index(drop=True)


def load_master() -> pd.DataFrame:
    if MASTER.exists():
        try:
            with gzip.open(MASTER, "rt", encoding="utf-8") as f:
                return pd.read_csv(f, dtype={"region_code": str})
        except Exception as exc:  # noqa: BLE001
            logger.warning("master 読込失敗: %s", exc)
    return pd.DataFrame()


def save_master(df: pd.DataFrame) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(MASTER, "wt", encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False)


def run(monthly_from: str = "201501", only_recent: int | None = None,
        sleep: float = 0.15, timeout: float = 30.0) -> pd.DataFrame:
    client = DGClient(sleep=sleep, timeout=timeout)
    reports = list_monthly_reports(client)
    logger.info("月度レポート数: %d", len(reports))

    end = _now_ym()
    if only_recent:
        # 直近 only_recent か月だけ（インクリメンタル用）
        y, m = end
        ys = y - (only_recent // 12)
        ms = m - (only_recent % 12)
        while ms <= 0:
            ms += 12
            ys -= 1
        periods = months(f"{ys}{ms:02d}", end)
    else:
        periods = months(monthly_from, end)
    logger.info("取得期間: %s..%s (%d か月)", periods[0], periods[-1], len(periods))

    raw = pd.DataFrame.from_records(
        fetch_records(client, reports, periods))
    if raw.empty:
        logger.error("データ取得0件")
        return raw

    proc = to_processed(raw)

    # 既存とマージ（同一キーは新しい方で上書き）
    prev = load_master()
    if not prev.empty:
        key = ["report_id", "indicator", "region_code", "period"]
        merged = pd.concat([prev, proc], ignore_index=True)
        merged = merged.drop_duplicates(subset=key, keep="last")
    else:
        merged = proc
    merged = merged.sort_values(["report", "indicator", "region_code", "period"])
    save_master(merged)

    # レポート索引
    idx = (merged.groupby(["report", "report_id"], as_index=False)
           .agg(rows=("period", "size"),
                indicators=("indicator", "nunique"),
                regions=("region_code", "nunique"),
                period_min=("period", "min"), period_max=("period", "max")))
    idx.to_csv(INDEX, index=False)
    logger.info("master 保存: %d 行 / レポート %d", len(merged), idx.shape[0])
    return merged

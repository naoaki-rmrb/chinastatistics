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


def _rows_to_records(rp: dict, dt: str, rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        dp = r.get("DP_NAME")
        if dp not in KEEP_DP:
            continue
        v = r.get("V")
        if v in (None, ""):
            continue
        out.append({
            "report": rp["name"], "report_id": rp["report_id"],
            "indicator": r.get("EK_NAME") or r.get("I_NAME"),
            "i_name": r.get("I_NAME"), "kj1": r.get("KJ1_NAME"),
            "region_code": r.get("DA"), "region_name": r.get("DA_NAME"),
            "period": _period(dt), "dp": dp, "unit": r.get("DU_NAME"),
            "v": v,
        })
    return out


def fetch_records(client: DGClient, reports: list[dict], periods: list[str],
                  workers: int = 8, timeout: float = 15.0,
                  retries: int = 2) -> list[dict]:
    """(report×period) を並列取得。スレッドごとに専用 DGClient を使う。

    NBS はGitHub Actionsの海外IPからだと1リクエスト数秒かかる上、時々失敗する。
    ・retries を抑えめ(既定2)＋ timeout を短め(既定15s)にして、1件の遅延が
      ワーカーを長時間占有しないようにする。
    ・throughput は主に workers で稼ぐ（全期間バックフィルは workers を上げる）。
    """
    import concurrent.futures as cf
    import threading

    tasks = [(rp, dt) for rp in reports for dt in periods]
    logger.info("並列取得: タスク %d (workers=%d, timeout=%ss, retries=%d)",
                len(tasks), workers, timeout, retries)
    _tl = threading.local()

    def _client() -> DGClient:
        c = getattr(_tl, "c", None)
        if c is None:
            c = DGClient(sleep=0.0, timeout=timeout, max_retries=retries)
            _tl.c = c
        return c

    def _do(task):
        rp, dt = task
        rows = _client().query_data(rp["report_id"], NAT, dt)
        return _rows_to_records(rp, dt, rows)

    recs: list[dict] = []
    done = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(_do, tasks):
            recs.extend(part)
            done += 1
            if done % 300 == 0:
                logger.info("...%d/%d tasks, %d rows", done, len(tasks), len(recs))
    logger.info("取得完了: %d タスク, %d 行", len(tasks), len(recs))
    return recs


def _period(dt: str) -> str:
    # "202506MM" -> "2025-06"
    return f"{dt[:4]}-{dt[4:6]}"


def _pivot(df_raw: pd.DataFrame) -> pd.DataFrame:
    """DP(本期/同比…)をピボットして level / official_yoy 列を作る（派生計算なし）。"""
    if df_raw.empty:
        return df_raw
    df = df_raw.copy()
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    df["is_yoy"] = df["dp"].isin(DP_YOY)
    df["is_level"] = df["dp"].isin(DP_LEVEL) & (df["unit"] != "%")
    # 内訳(kj1)・指標正式名(i_name)は欠損があり得るので埋めてキーに含める。
    # ※ kj1 をキーに含めないと、同一 indicator の国別・品目別など内訳系列が
    #   1本に潰れて値が混ざる（agg(first)）。必ず区別する。
    df["kj1"] = df["kj1"].fillna("")
    df["i_name"] = df["i_name"].fillna(df["indicator"])

    key = ["report", "report_id", "indicator", "i_name", "kj1",
           "region_code", "region_name", "period"]
    level = (df[df["is_level"]].groupby(key, as_index=False)
             .agg(level=("v", "first"), unit=("unit", "first")))
    yoy = (df[df["is_yoy"]].groupby(key, as_index=False)
           .agg(official_yoy=("v", "first")))
    return level.merge(yoy, on=key, how="outer")


def _derive_yoy_mom(out: pd.DataFrame) -> pd.DataFrame:
    """level/official_yoy を持つ表に computed_yoy / mom / yoy_gap を（再）計算。

    ※ 同一 report×indicator×内訳×region の全期間が同じ表に揃っている前提。
      チャンク取得ではチャンクごとではなく master 全体に対して呼ぶこと。
    ※ pandas 3.x では groupby.apply が group 列を落とすため、
      shift / self-merge のベクトル演算で列を保持したまま計算する。
    """
    if out.empty:
        return out
    import numpy as np

    out = out.drop(columns=[c for c in ("computed_yoy", "mom", "yoy_gap",
                                        "year", "mon", "level_ly")
                            if c in out.columns]).copy()
    out["year"] = out["period"].str[:4].astype(int)
    out["mon"] = out["period"].str[5:7].astype(int)
    gcols = ["report_id", "indicator", "i_name", "kj1", "region_code"]
    out = out.sort_values(gcols + ["year", "mon"]).reset_index(drop=True)

    # 対前月比: グループ内の直前行（＝直前期）と比較
    prev_level = out.groupby(gcols, sort=False)["level"].shift(1)
    out["mom"] = (out["level"] / prev_level - 1) * 100

    # 対前年比(計算値): 同一グループ・同月・前年の level と比較
    ly = out[gcols + ["year", "mon", "level"]].copy()
    ly["year"] = ly["year"] + 1
    ly = ly.rename(columns={"level": "level_ly"})
    ly = ly.drop_duplicates(subset=gcols + ["year", "mon"], keep="first")
    out = out.merge(ly, on=gcols + ["year", "mon"], how="left")
    out["computed_yoy"] = (out["level"] / out["level_ly"] - 1) * 100

    # 0除算・欠損は NaN に
    out[["mom", "computed_yoy"]] = out[["mom", "computed_yoy"]].replace(
        [np.inf, -np.inf], np.nan)

    out["yoy_gap"] = out["computed_yoy"] - out["official_yoy"]
    return out.drop(columns=["year", "mon", "level_ly"]).reset_index(drop=True)


def to_processed(df_raw: pd.DataFrame) -> pd.DataFrame:
    """DPをピボットして level/official_yoy を作り、computed_yoy/mom を計算。"""
    if df_raw.empty:
        return df_raw
    return _derive_yoy_mom(_pivot(df_raw))


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


def _merge_and_save(prev: pd.DataFrame, pivoted: pd.DataFrame) -> pd.DataFrame:
    """新規ピボット行を既存 master にマージ→全体で派生列を再計算→保存。"""
    key = ["report_id", "indicator", "i_name", "kj1", "region_code", "period"]
    keep_cols = ["report", "report_id", "indicator", "i_name", "kj1",
                 "region_code", "region_name", "period", "level", "unit",
                 "official_yoy"]
    frames = [f[[c for c in keep_cols if c in f.columns]]
              for f in (prev, pivoted) if f is not None and not f.empty]
    if not frames:
        return prev if prev is not None else pd.DataFrame()
    base = pd.concat(frames, ignore_index=True).drop_duplicates(
        subset=key, keep="last")
    # master 全体で computed_yoy / mom / yoy_gap を再計算（前年同月比のため）
    merged = _derive_yoy_mom(base)
    merged = merged.sort_values(["report", "indicator", "region_code", "period"])
    save_master(merged)
    idx = (merged.groupby(["report", "report_id"], as_index=False)
           .agg(rows=("period", "size"),
                indicators=("indicator", "nunique"),
                regions=("region_code", "nunique"),
                period_min=("period", "min"), period_max=("period", "max")))
    idx.to_csv(INDEX, index=False)
    return merged


def _chunks_by_year(periods: list[str]) -> list[list[str]]:
    out: dict[str, list[str]] = {}
    for p in periods:
        out.setdefault(p[:4], []).append(p)
    return list(out.values())


def run(monthly_from: str = "201501", only_recent: int | None = None,
        sleep: float = 0.0, timeout: float = 15.0, workers: int = 8,
        retries: int = 2, only_reports: str | None = None) -> pd.DataFrame:
    client = DGClient(sleep=sleep, timeout=timeout)
    reports = list_monthly_reports(client)
    if only_reports:
        # 名前 or report_id の部分一致でレポートを絞り込む（カンマ区切り）。
        needles = [s.strip() for s in only_reports.split(",") if s.strip()]
        reports = [r for r in reports
                   if any(n in r["name"] or n == r["report_id"] for n in needles)]
        logger.info("レポート絞り込み: %s -> %d 件", needles, len(reports))
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

    # 年単位のチャンクで取得→処理→マージ→保存（チェックポイント）。
    # 途中でタイムアウトしても、完了済みの年までは master に保存済みになる。
    # ※ computed_yoy は同一 report×indicator×region の全期間で計算する必要が
    #   あるため、各チャンク処理では「新規raw＋既存masterのlevel」を合わせて
    #   to_processed し、前年同月比が途切れないようにする。
    chunks = _chunks_by_year(periods)
    merged = load_master()
    for i, chunk in enumerate(chunks, 1):
        logger.info("=== チャンク %d/%d: %s..%s ===", i, len(chunks),
                    chunk[0], chunk[-1])
        raw = pd.DataFrame.from_records(
            fetch_records(client, reports, chunk, workers=workers,
                          timeout=timeout, retries=retries))
        if raw.empty:
            logger.warning("チャンク %d はデータ0件、スキップ", i)
            continue
        pivoted = _pivot(raw)
        merged = _merge_and_save(merged, pivoted)
        logger.info("... master 保存: %d 行", 0 if merged is None else len(merged))

    if merged is None or merged.empty:
        logger.error("データ取得0件")
        return pd.DataFrame()
    logger.info("完了: master %d 行", len(merged))
    return merged

"""コマンドラインエントリ。

  python -m chinastats.cli build     # NBSから取得してExcel生成/更新
  python -m chinastats.cli discover --db fsyd   # 指標ツリーを出力(コード確認)
  python -m chinastats.cli demo      # 合成データでExcel生成(オフライン検証)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .excel_writer import write_workbook
from .transform import detect_base_revisions, records_to_frame

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
XLSX_PATH = OUTPUT_DIR / "china_indicators.xlsx"
SNAPSHOT_CSV = OUTPUT_DIR / "china_indicators_data.csv"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    indicators = _load_yaml(CONFIG_DIR / "indicators.yaml")
    regions = _load_yaml(CONFIG_DIR / "regions.yaml")
    settings_path = CONFIG_DIR / "settings.yaml"
    settings = _load_yaml(settings_path) if settings_path.exists() else {}
    return indicators, regions, settings


def _now_iso() -> str:
    # 環境依存を避けるため UTC を明示（この関数は cron 実行時のみ呼ばれる）
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _read_previous() -> pd.DataFrame | None:
    if SNAPSHOT_CSV.exists():
        try:
            return pd.read_csv(SNAPSHOT_CSV, dtype={"region_code": str})
        except Exception as exc:  # noqa: BLE001
            logger.warning("前回スナップショット読込失敗: %s", exc)
    return None


def _finalize(df: pd.DataFrame, indicators: dict, regions: dict, settings: dict,
              resolved_codes: list[dict] | None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    previous = _read_previous()
    revisions = detect_base_revisions(df, previous)
    meta = {
        "updated_at": _now_iso(),
        "sj_monthly": settings.get("sj_valuecode_monthly", "LAST120"),
        "sj_quarterly": settings.get("sj_valuecode_quarterly", "LAST80"),
        "resolved_codes": resolved_codes or [],
    }
    write_workbook(df, indicators, regions, revisions, meta, str(XLSX_PATH))
    # 次回比較用の tidy スナップショットを保存
    keep = ["indicator", "region_code", "region_zh", "period", "value",
            "official_yoy_pct", "computed_yoy", "yoy_gap", "mom",
            "single_month", "single_mom", "name_ja"]
    cols = [c for c in keep if c in df.columns]
    df[cols].to_csv(SNAPSHOT_CSV, index=False)
    logger.info("スナップショット保存: %s", SNAPSHOT_CSV)


def cmd_build(args: argparse.Namespace) -> int:
    from .fetch import fetch_all
    from .nbs_client import NBSClient
    from .resolver import Resolver

    indicators, regions, settings = load_config()
    client = NBSClient(
        timeout=settings.get("timeout", 30),
        max_retries=settings.get("max_retries", 4),
        sleep=settings.get("sleep", 0.6),
    )
    resolver = Resolver(client=client)

    only = args.only.split(",") if args.only else None
    records = fetch_all(client, resolver, indicators, regions, settings, only=only)
    if not records:
        logger.error("レコードが取得できませんでした。コード解決やネットワークを確認してください。")
        return 2

    df = records_to_frame(records)

    # 解決済みコードを記録（説明シート用）
    resolved = list(resolver.resolutions)
    _finalize(df, indicators, regions, settings, resolved)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    from .nbs_client import NBSClient
    from .resolver import Resolver

    client = NBSClient()
    resolver = Resolver(client=client)
    leaves = resolver.dump_leaves(args.db)
    out = {"db": args.db, "count": len(leaves), "leaves": leaves}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        logger.info("書き出し: %s (%d 件)", args.out, len(leaves))
    else:
        print(text)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """NBS に繋がない合成データで Excel を生成し、パイプラインを検証する。"""
    indicators, regions, settings = load_config()
    records = _synthetic_records(indicators, regions)
    df = records_to_frame(records)
    _finalize(df, indicators, regions, settings, resolved_codes=[
        {"indicator": "demo", "db": "-", "role": "-", "code": "-", "matched": "合成データ"}
    ])
    print(f"demo Excel を生成: {XLSX_PATH}")
    return 0


def _synthetic_records(indicators: dict, regions: dict) -> list[dict]:
    """決定論的な合成時系列（乱数不使用）を作る。"""
    recs: list[dict] = []
    regs = []
    nat = regions.get("national")
    if nat:
        regs.append((nat["code"], nat["name_zh"], nat.get("name_ja", nat["name_zh"])))
    for r in regions.get("provinces", [])[:5]:  # デモは先頭5省
        regs.append((r["code"], r["name_zh"], r["name_ja"]))

    for ind in indicators["indicators"]:
        freq = ind.get("frequency", "monthly")
        kind = ind.get("level_kind")
        for ri, (code, zh, ja) in enumerate(regs):
            base = 1000 + ri * 300
            if freq == "monthly":
                periods = [(y, m) for y in range(2021, 2025) for m in range(1, 13)]
                for idx, (y, m) in enumerate(periods):
                    if m == 1 and ind["key"] in ("retail", "exports", "imports"):
                        continue  # 1月欠測を再現
                    if kind == "cumulative":
                        val = base * m * (1 + 0.03 * (y - 2021))
                    else:
                        val = base * (1 + 0.02 * idx)
                    recs.append(_mk(ind, code, zh, ja, "monthly", y, m,
                                    f"{y}-{m:02d}", val, 5.0 + 0.1 * idx))
            else:
                for y in range(2021, 2025):
                    for q in range(1, 5):
                        val = base * q * (1 + 0.05 * (y - 2021))
                        recs.append(_mk(ind, code, zh, ja, "quarterly", y, q,
                                        f"{y}-Q{q}", val, 4.5 + 0.2 * q))
    return recs


def _mk(ind, code, zh, ja, freq, year, sub, period, value, off) -> dict:
    return {
        "indicator": ind["key"], "level_kind": ind.get("level_kind"),
        "name_zh": ind["name_zh"], "name_ja": ind["name_ja"], "name_en": ind["name_en"],
        "unit_zh": ind.get("unit_zh"), "unit_ja": ind.get("unit_ja"), "unit_en": ind.get("unit_en"),
        "freq": freq, "region_code": code, "region_zh": zh, "region_ja": ja,
        "period": period, "year": year, "sub": sub, "value": value, "official_yoy": off,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(prog="chinastats")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="NBSから取得してExcel生成/更新")
    pb.add_argument("--only", default=os.environ.get("ONLY", ""),
                    help="指標keyをカンマ区切りで限定（例: retail,gdp）")
    pb.set_defaults(func=cmd_build)

    pd_ = sub.add_parser("discover", help="指標ツリーをダンプ")
    pd_.add_argument("--db", required=True, help="hgyd/hgjd/fsyd/fsjd")
    pd_.add_argument("--out", default="", help="出力先JSON（省略時は標準出力）")
    pd_.set_defaults(func=cmd_discover)

    pm = sub.add_parser("demo", help="合成データでExcel生成（オフライン検証）")
    pm.set_defaults(func=cmd_demo)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

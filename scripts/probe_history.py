"""特定レポートについて、過去〜直近の複数DTを叩き、各月の返却行数を出す。

目的: DG公開APIが「多くの月次レポートで直近数か月しか返さない」のか、
それとも過去DTでもデータを返すのかを実証する（履歴バックフィル可否の確認）。
GitHub Actions（海外IP・新版DG APIは到達可）から実行する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chinastats.dg_client import DGClient  # noqa: E402

NAT = "000000000000"

REPORTS = {
    "社会消费品零售总额": "39b254feba05423d8ba72c28f633f343",
    "各地区固定资产投资(不含农户)": "72375b5a0dcf421e8fddbb51fd3a0192",
    "各地区房地产开发投资": "01e95051738d45cb910220aea38b0b4b",
    "各地区商品房销售面积增长情况": "966d64c02ebe4546901722e7c478372b",
    # 深い履歴が取れている参照レポート（比較用）
    "工业生产者购进价格指数": "bb108abc266a43e28a216847c1c3b814",
}

# 過去〜直近を広くサンプリング
DTS = ["201006MM", "201506MM", "201806MM", "202006MM", "202206MM",
       "202306MM", "202406MM", "202506MM", "202512MM", "202603MM",
       "202604MM", "202605MM", "202606MM"]


def dp_names(rows):
    s = {}
    for r in rows:
        dp = r.get("DP_NAME")
        s[dp] = s.get(dp, 0) + 1
    return s


def main() -> int:
    c = DGClient(sleep=0.0, timeout=20.0, max_retries=3)
    for name, rid in REPORTS.items():
        print(f"\n==== {name} ({rid}) ====")
        for dt in DTS:
            rows = c.query_data(rid, NAT, dt)
            n = len(rows)
            dps = dp_names(rows) if rows else {}
            # 本期(level)と同比(yoy)の有無を確認
            has_level = any("本期" in (k or "") for k in dps)
            has_yoy = any("同比" in (k or "") for k in dps)
            print(f"  {dt}: rows={n:4d}  level={has_level}  yoy={has_yoy}  dp={dps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

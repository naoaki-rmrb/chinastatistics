"""1レポートの構造プローブ：DP_NAME / 指標 / 地区 / 単位 の実体を把握する。
使い方(Actions): REPORT_ID と DT を環境変数で渡す。結果は output/probe_report.json。
"""
from __future__ import annotations
import json, os, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "src")
from chinastats.dg_client import DGClient  # noqa: E402

RID = os.environ.get("REPORT_ID", "96d37aa633164cf0a177432d150c4711")
DT = os.environ.get("DT", "202608MM")
OUT = Path("output/probe_report.json")


def main() -> None:
    c = DGClient(sleep=0.2, timeout=30, max_retries=3)
    rows = c.query_data(RID, "000000000000", DT)
    dp = Counter(r.get("DP_NAME") for r in rows)
    iname = Counter(r.get("I_NAME") for r in rows)
    ekname = Counter(r.get("EK_NAME") for r in rows)
    kj1 = Counter(r.get("KJ1_NAME") for r in rows)
    da = Counter(r.get("DA_NAME") for r in rows)
    unit = Counter(r.get("DU_NAME") for r in rows)
    sample = rows[:12]
    out = {
        "report_id": RID, "dt": DT, "nrows": len(rows),
        "DP_NAME": dp.most_common(), "DU_NAME": unit.most_common(),
        "I_NAME": iname.most_common(20), "EK_NAME": ekname.most_common(30),
        "KJ1_NAME": kj1.most_common(20),
        "DA_count": len(da), "DA_sample": da.most_common(12),
        "sample_rows": sample,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rows", len(rows))
    print("DP_NAME:", dp.most_common())
    print("DU_NAME:", unit.most_common())
    print("EK_NAME(top):", ekname.most_common(15))
    print("KJ1_NAME:", kj1.most_common())
    print("DA:", len(da), da.most_common(6))
    print("書き出し:", OUT)


if __name__ == "__main__":
    main()

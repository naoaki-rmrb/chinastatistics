"""新版NBS API 探索v4: 四半期DT形式の特定 + 時間一覧APIの確認。"""

import json
import requests

BASE = "https://data.stats.gov.cn/dg/website/publicrelease/web/external/"
H = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Client": "pc",
    "Referer": "https://data.stats.gov.cn/dg/website/page.html",
}

GDP = "b4241c76593e4f01b2364c01d698f9c6"       # 地区生产总值(四半期) report_id
GDP_NID = "b2682f292e594cac82700fe84bb5ce0c"   # その _id


def q(path, **params):
    r = requests.get(BASE + path, params=params, headers=H, timeout=30)
    return r


def try_dt(dt):
    r = q("queryMacroReportDataById", REPORTID=GDP, DA="000000000000", DT=dt)
    try:
        j = r.json()
    except Exception:
        print(f"  DT={dt} -> {r.status_code} nonjson"); return
    rows = j.get("data") if isinstance(j.get("data"), list) else None
    if rows:
        dts = sorted({str(x.get("DT")) for x in rows})
        print(f"  DT={dt} -> OK rows={len(rows)} DT={dts[:4]} "
              f"sampleV={rows[0].get('V')} DA#={len({x.get('DA_NAME') for x in rows})}")
    else:
        print(f"  DT={dt} -> rows=0 msg={j.get('message')}")


def main():
    print("== 四半期DT 形式ブルートフォース ==")
    cands = []
    for y in (2025, 2024):
        for qn in (1, 2, 3, 4):
            mm = qn * 3
            cands += [
                f"{y}{qn}JD", f"{y}0{qn}JD", f"{y}{mm:02d}JD", f"{y}{mm:02d}",
                f"{y}{'ABCD'[qn-1]}", f"{y}0{qn}", f"{y}Q{qn}",
                f"{y}{mm:02d}LB", f"{y}{qn}LB", f"{y}{mm:02d}JJ", f"{y}0{qn}A",
            ]
    seen = set()
    for dt in cands:
        if dt in seen:
            continue
        seen.add(dt)
        try_dt(dt)

    print("\n== 時間一覧API 候補 ==")
    for path in ("getHtmlContentTime", "getHtmlContent", "queryHtmlContentTime",
                 "getReportTime", "getTimeById"):
        for key in ("id", "reportId", "REPORTID"):
            for val in (GDP_NID, GDP):
                r = q(path, **{key: val})
                if r.status_code == 200 and r.text.strip().startswith(("{", "[")):
                    print(f"  {path}?{key}={val[:8]} -> 200 JSON: {r.text[:400]}")


if __name__ == "__main__":
    main()

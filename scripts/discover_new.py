"""新版NBS API 探索v3: 主要レポートの実データを取得し、DA/DT/値の構造を確認。"""

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


def fetch(rid, da, dt):
    r = requests.get(BASE + "queryMacroReportDataById",
                     params={"REPORTID": rid, "DA": da, "DT": dt},
                     headers=H, timeout=30)
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return r.status_code, None, r.text[:120]
    return r.status_code, j, None


def summarize(name, rid, da, dt):
    st, j, err = fetch(rid, da, dt)
    if err is not None:
        print(f"[{name}] DA={da} DT={dt} -> {st} NON-JSON {err}")
        return
    ok = j.get("success")
    rows = j.get("data") if isinstance(j.get("data"), list) else None
    if not rows:
        print(f"[{name}] DA={da} DT={dt} -> {st} success={ok} rows=0 msg={j.get('message')}")
        return
    das = sorted({str(r.get("DA_NAME")) for r in rows})
    dts = sorted({str(r.get("DT")) for r in rows})
    inds = sorted({str(r.get("EK_NAME") or r.get("I_NAME")) for r in rows})
    print(f"[{name}] DA={da} DT={dt} -> {st} rows={len(rows)} "
          f"#DA={len(das)} #DT={len(dts)} #ind={len(inds)}")
    print(f"   DA_NAMES(sample): {das[:8]}")
    print(f"   DT(sample): {dts[:6]}")
    print(f"   IND(sample): {inds[:6]}")
    for row in rows[:2]:
        print("   ROW:", json.dumps({k: row.get(k) for k in
              ("DA_NAME", "DT", "DT_NAME", "EK_NAME", "I_NAME", "KJ1_NAME",
               "DU_NAME", "DP_NAME", "V")}, ensure_ascii=False))


def main():
    NAT = "000000000000"
    # 小売(月次)
    for dt in ("202506MM", "202505MM"):
        summarize("retail_月次", "39b254feba05423d8ba72c28f633f343", NAT, dt)
    # 各地区固定资产投资(月次・省別) — 全省返るか
    summarize("各地区FAI_月次", "72375b5a0dcf421e8fddbb51fd3a0192", NAT, "202506MM")
    # 各地区房地产开发投资(月次・省別)
    summarize("各地区不動産投資_月次", "01e95051738d45cb910220aea38b0b4b", NAT, "202506MM")
    # GDP 地区生产总值(四半期・省別) — DT形式を複数試す
    for dt in ("2025A", "2025B", "20251", "202503", "2025LB", "2024D", "2024LB"):
        summarize("地区GDP_四半期", "b4241c76593e4f01b2364c01d698f9c6", NAT, dt)
    # 70都市住宅価格(月次)
    summarize("70都市住宅価格_月次", "96d37aa633164cf0a177432d150c4711", NAT, "202506MM")


if __name__ == "__main__":
    main()

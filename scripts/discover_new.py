"""新版NBS API 探索v5: getHtmlContent の完全ダンプ(期間リスト構造) + GDP DT検証。"""

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


def get(path, **params):
    return requests.get(BASE + path, params=params, headers=H, timeout=30)


def main():
    # getHtmlContent フルダンプ: 月次(retail) と 四半期(GDP)
    targets = {
        "retail_月次_nid": "8baef5916d504305a5da8f916094de25",
        "GDP_季度_nid": "b2682f292e594cac82700fe84bb5ce0c",
    }
    for name, nid in targets.items():
        r = get("getHtmlContent", id=nid)
        print(f"\n===== getHtmlContent {name}={nid} -> {r.status_code} =====")
        try:
            j = r.json()
            print(json.dumps(j, ensure_ascii=False)[:5000])
        except Exception as e:  # noqa: BLE001
            print("nonjson", e, r.text[:200])

    # GDP: dt="2024" 等の年ベースを検証
    GDP = "b4241c76593e4f01b2364c01d698f9c6"
    for dt in ("2024", "2023", "2024LB", "2024A", "2025"):
        r = get("queryMacroReportDataById", REPORTID=GDP, DA="000000000000", DT=dt)
        try:
            j = r.json()
        except Exception:
            print(f"GDP DT={dt} nonjson"); continue
        rows = j.get("data") if isinstance(j.get("data"), list) else None
        if rows:
            das = sorted({str(x.get("DA_NAME")) for x in rows})
            print(f"GDP DT={dt} -> OK rows={len(rows)} #DA={len(das)} "
                  f"DA(sample)={das[:6]} sampleV={rows[0].get('V')} "
                  f"DP={sorted({x.get('DP_NAME') for x in rows})}")
        else:
            print(f"GDP DT={dt} -> rows=0 msg={j.get('message')}")


if __name__ == "__main__":
    main()

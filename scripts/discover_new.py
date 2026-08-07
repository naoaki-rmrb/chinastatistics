"""探索v6: 期間(DT)コード形式の特定。時間一覧APIとgetHtmlContentのdt受理を検証。"""

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
# _id (tree node id) 群
NIDS = {
    "月次_工业增加值增速": "731705122d3a42e295988f7d95a595eb",
    "月次_retail": "8baef5916d504305a5da8f916094de25",
    "季度_地区生产总值": "b2682f292e594cac82700fe84bb5ce0c",
    "年度_社会消费品零售总额": "cf9538a8530d4b7bb1f1c459bcde8624",
}
GDP_RID = "b4241c76593e4f01b2364c01d698f9c6"


def g(path, **p):
    return requests.get(BASE + path, params=p, headers=H, timeout=30)


def main():
    # 1) 時間一覧API候補
    for label, nid in NIDS.items():
        for path in ("getHtmlContentTime", "getReportDt", "getDtById", "queryDt"):
            for key in ("id", "reportId"):
                r = g(path, **{key: nid})
                body = r.text.strip()
                if r.status_code == 200 and body[:1] in "{[":
                    print(f"\n[TIME OK] {label} {path}?{key} -> 200")
                    print(body[:1200])

    # 2) getHtmlContent の dt 受理テスト（GDP: 年/四半期の候補）
    gdp_nid = NIDS["季度_地区生产总值"]
    print("\n== getHtmlContent(GDP) dt候補 ==")
    for dt in ("", "2024", "2024LB", "2024A", "2024B", "2024C", "2024D",
               "202412", "2024JD", "20244", "2024ND", "2024Y", "2024LJ"):
        r = g("getHtmlContent", id=gdp_nid, dt=dt)
        try:
            j = r.json(); d = j.get("data") or {}
            print(f"  dt={dt!r} -> {r.status_code} dt_meta={d.get('dt')} "
                  f"has_html={bool(d.get('html_content'))} msg={j.get('message')}")
        except Exception:
            print(f"  dt={dt!r} -> {r.status_code} nonjson")

    # 3) queryMacroReportDataById(GDP) 追加候補
    print("\n== queryMacroReportDataById(GDP) dt候補 ==")
    for dt in ("2024C", "2024D", "20244JD", "202404JD", "2024ND", "2024LJ",
               "2024LB4", "2024B4", "2024年", "2024LN"):
        r = g("queryMacroReportDataById", REPORTID=GDP_RID, DA="000000000000", DT=dt)
        try:
            j = r.json(); rows = j.get("data") if isinstance(j.get("data"), list) else None
            print(f"  dt={dt!r} -> rows={len(rows) if rows else 0} msg={j.get('message')}")
        except Exception:
            print(f"  dt={dt!r} -> nonjson")


if __name__ == "__main__":
    main()

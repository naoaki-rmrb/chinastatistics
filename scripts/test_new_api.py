"""新版 NBS ポータル API (queryMacroReportDataById) の到達性テスト。

旧版 easyquery.htm は WAF で 403 だったが、新版 /dg/website/publicrelease/
web/external/ は公開・外部向けの別エンドポイント。これが GitHub Actions
(Azure/米国IP) からでも通るなら、VPN 不要で完全自動化できる。
"""

import requests

BASE = ("https://data.stats.gov.cn/dg/website/publicrelease/web/external/"
        "queryMacroReportDataById")
PARAMS = {
    "REPORTID": "8c256a820cc34fc08eb4726a91ea7401",  # 居民消费价格分类指数
    "DA": "000000000000",   # 全国
    "DT": "202607MM",       # 2026年7月・月次
}

HEADER_SETS = {
    "minimal": {"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    "with_client": {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Client": "pc",
        "Referer": "https://data.stats.gov.cn/dg/website/page.html",
    },
}


def main() -> None:
    for name, headers in HEADER_SETS.items():
        print("=" * 60)
        print(f"[{name}] headers={list(headers)}")
        try:
            r = requests.get(BASE, params=PARAMS, headers=headers, timeout=25)
            print("STATUS", r.status_code, "len", len(r.text))
            snippet = r.text[:400].replace("\n", " ")
            print("BODY:", snippet)
        except Exception as exc:  # noqa: BLE001
            print("ERROR:", exc)


if __name__ == "__main__":
    main()

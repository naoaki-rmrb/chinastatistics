"""新版NBS API の探索: 指標ツリー・地区・期間・データ構造をダンプする。

エンドポイント(いずれも 200 で公開):
  queryPbLibCatalogTree?code=1   指標カタログ(ツリー)  code=1:月度? 2:季度? 3:年度?
  getChooseDaById?id=<reportid>  その表の地区(DA)一覧
  getHtmlContentTime?id=<reportid> その表の期間(DT)一覧
  queryMacroReportDataById?REPORTID=..&DA=..&DT=..  データ本体
"""

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
    r = requests.get(BASE + path, params=params, headers=H, timeout=30)
    print(f"\n### GET {path} params={params} -> {r.status_code} len={len(r.text)}")
    return r


def dump(obj, limit=6000):
    s = json.dumps(obj, ensure_ascii=False)
    print(s[:limit] + (" …[truncated]" if len(s) > limit else ""))


def walk_tree(code):
    r = get("queryPbLibCatalogTree", code=code)
    try:
        j = r.json()
    except Exception as e:  # noqa: BLE001
        print("NOT JSON:", e, r.text[:200])
        return
    dump(j, 8000)
    return j


def main():
    # 1) カタログツリー（頻度別）
    for code in (1, 2, 3):
        walk_tree(code)

    # 2) サンプル report の地区・期間・データ構造
    sample = "0624a707cf934347ae9e2f6985"  # スクショで見えた REPORTID の先頭
    # 完全なIDが要るので、まずツリーから拾えた最初のleafで試すのが本筋。
    # ここでは既知の一つで DA/DT/データ構造の形を確認する。
    known = "8c256a820cc34fc08eb4726a91ea7401"
    r = get("getChooseDaById", id=known)
    try:
        dump(r.json(), 3000)
    except Exception as e:  # noqa: BLE001
        print("da not json", e, r.text[:200])
    r = get("getHtmlContentTime", id=known)
    try:
        dump(r.json(), 3000)
    except Exception as e:  # noqa: BLE001
        print("time not json", e, r.text[:200])


if __name__ == "__main__":
    main()

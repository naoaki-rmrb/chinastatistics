"""新版NBS API 探索: 指標カタログを平坦化して (code, 分類 > 表名, report_id, _id) を全件出力。

code: 1=月度, 2=季度, 3=年度
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
FREQ = {1: "月度", 2: "季度", 3: "年度"}


def walk(node, path, code, out):
    name = node.get("name")
    p = path + [name] if name else path
    if node.get("type") == "report" and node.get("report_id"):
        out.append((code, " > ".join(p), node["report_id"], node.get("_id")))
    for ch in node.get("children") or []:
        walk(ch, p, code, out)


def main():
    for code in (1, 2, 3):
        r = requests.get(BASE + "queryPbLibCatalogTree", params={"code": code},
                         headers=H, timeout=30)
        try:
            data = r.json().get("data", [])
        except Exception as e:  # noqa: BLE001
            print(f"code={code} NOT JSON: {e} {r.text[:150]}")
            continue
        out = []
        for top in data:
            walk(top, [], code, out)
        print(f"\n========== code={code} ({FREQ[code]})  reports={len(out)} ==========")
        for c, path, rid, nid in out:
            print(f"{FREQ[code]}\t{path}\t{rid}\t{nid}")

    # サンプル: 正しい id(_id) で地区・期間の構造を確認（月度・各地区固定资产投资）
    sample_nid = "a9a777a5d510453bb01d509f15629a54"  # 各地区固定资产投资(不含农户) の _id
    for ep in ("getChooseDaById", "getHtmlContentTime"):
        r = requests.get(BASE + ep, params={"id": sample_nid}, headers=H, timeout=25)
        print(f"\n### {ep}?id={sample_nid} -> {r.status_code} len={len(r.text)}")
        try:
            print(json.dumps(r.json(), ensure_ascii=False)[:1500])
        except Exception:  # noqa: BLE001
            print(r.text[:300])


if __name__ == "__main__":
    main()

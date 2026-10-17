"""NBS 新版DGポータルのカタログ全走査：住宅販売価格(70城・新建/二手)レポートを探す。

- queryPbLibCatalogTree?code=N を code=1..12 まで試し、各ツリーの leaf(report) を平坦化。
- 住宅価格系キーワードに該当する leaf を強調表示。
- 全 leaf を output/catalog_all.json に保存（コミットして手元で確認する）。
NBSはGitHub Actionsの海外IPからのみ安定取得できるため、本スクリプトはActionsで実行する。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")
from chinastats.dg_client import DGClient, walk_catalog  # noqa: E402

OUT = Path("output/catalog_all.json")
KW = ["房价", "销售价格", "二手", "70个", "70大", "七十", "价格指数", "住宅销售价格", "商品住宅"]


def main() -> None:
    c = DGClient(sleep=0.2, timeout=30, max_retries=3)
    all_leaves = []
    per_code = {}
    for code in range(1, 13):
        try:
            tree = c.catalog_tree(code)
        except Exception as exc:  # noqa: BLE001
            print(f"code={code}: error {exc}")
            continue
        if not tree:
            print(f"code={code}: (空)")
            continue
        leaves = walk_catalog(tree)
        for lf in leaves:
            lf["code"] = code
        per_code[code] = len(leaves)
        all_leaves.extend(leaves)
        print(f"code={code}: leaves={len(leaves)}")

    # 重複 report_id を除外しつつ住宅価格系を抽出
    seen = set()
    uniq = []
    for lf in all_leaves:
        rid = lf.get("report_id")
        if rid and rid not in seen:
            seen.add(rid)
            uniq.append(lf)
    print(f"\n総leaf {len(all_leaves)} / ユニークreport {len(uniq)} / codes {per_code}")

    hits = [lf for lf in uniq if any(k in (lf.get("name") or "") or k in (lf.get("path") or "") for k in KW)]
    print(f"\n=== 住宅価格系ヒット {len(hits)} 件 ===")
    for lf in hits:
        print(f"  code={lf['code']}  id={lf['report_id']}  {lf['path']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"per_code": per_code, "hits": hits, "all": uniq},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n書き出し: {OUT}  (ユニーク {len(uniq)} 件)")


if __name__ == "__main__":
    main()

"""NBS(国家統計局)への到達性チェック（VPN経由の可否を確認）。

このPC(＋中国IPのVPN)からNBSのデータAPIに届くかを短時間で判定する。
月次取得の本番前に、まずこれで接続可否を確かめる。
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(message)s")


def main() -> int:
    print("=" * 50)
    print(" NBS(国家統計局)への接続テスト")
    print("=" * 50)
    print("※ 中国IPのVPNがONになっているか確認してください。")
    print()

    try:
        from chinastats.nbs_client import NBSClient
    except Exception as exc:  # noqa: BLE001
        print(f"起動エラー: {exc}")
        print("→ セットアップが未完了です。run_local.bat を先に一度実行してください。")
        return 3

    client = NBSClient(max_retries=2, sleep=0.3)
    print("NBS に問い合わせています...\n")
    try:
        tree = client.get_tree(dbcode="fsyd", node_id="zb")
        if tree:
            print(f"\n✓ 成功しました。NBSから指標ツリーを {len(tree)} 件取得できました。")
            print("→ このPC(VPN)からNBSが使えます。月次データ取得に進めます。")
            return 0
        print("\n△ 応答はありましたが中身が空でした。時間をおいて再実行してください。")
        return 1
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        print(f"\n✗ 失敗しました。")
        if "403" in msg:
            print("  → NBSのWAFに拒否されました(403)。IPが国外/データセンター扱いです。")
            print("     対処: VPNを中国本土の別サーバ(都市)に切替えて再実行してください。")
            print("     住宅系/中国モバイル系の出口IPだと通りやすいです。")
        else:
            print(f"  詳細: {msg}")
            print("  → VPN(中国IP)がONか、通信が安定しているか確認して再実行してください。")
        return 2


if __name__ == "__main__":
    sys.exit(main())

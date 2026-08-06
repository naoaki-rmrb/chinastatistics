"""新版NBSデータポータル(dg)クライアント。

旧 easyquery.htm は WAF で 403 になるが、新版
  https://data.stats.gov.cn/dg/website/publicrelease/web/external/
配下の公開API は GitHub Actions(海外IP)からでも 200 で取得できる。

主なエンドポイント:
  queryPbLibCatalogTree?code=1|2|3   指標カタログ(1=月度,2=季度,3=年度)
  queryMacroReportDataById?REPORTID=&DA=&DT=   データ本体

データ行(JSON data[]) の主なフィールド:
  DA / DA_NAME   地区コード / 地区名 (000000000000=全国)
  DT / DT_NAME   期間コード / 期間名 (例 202506MM = 2025年6月)
  I_NAME         指標名(基本)
  EK_NAME        指標名(内訳込み)
  KJ1_NAME       内訳次元(住宅など)。null=内訳なし(ヘッドライン)
  DU_NAME        単位(亿元 / 万元 / % など)
  DP_NAME        本期 / 本期累计 / 同比增减% / 累计同比增减%
  V              値(文字列)
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

BASE = "https://data.stats.gov.cn/dg/website/publicrelease/web/external/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Client": "pc",
    "Referer": "https://data.stats.gov.cn/dg/website/page.html",
}


class DGClient:
    def __init__(self, timeout: float = 30.0, max_retries: int = 4, sleep: float = 0.25):
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _get(self, path: str, params: dict) -> dict | list | None:
        last = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(BASE + path, params=params, timeout=self.timeout)
                r.raise_for_status()
                if self.sleep:
                    time.sleep(self.sleep)
                return r.json()
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 ** attempt)
        logger.warning("DG API 失敗 %s %s: %s", path, params, last)
        return None

    def catalog_tree(self, code: int) -> list:
        """指標カタログ(code=1月度/2季度/3年度)のトップ配列を返す。"""
        j = self._get("queryPbLibCatalogTree", {"code": code})
        if isinstance(j, dict):
            return j.get("data") or []
        return j or []

    def query_data(self, report_id: str, da: str, dt: str) -> list[dict]:
        """指定レポート・地区・期間のデータ行(list)を返す。失敗時は空。"""
        j = self._get("queryMacroReportDataById",
                      {"REPORTID": report_id, "DA": da, "DT": dt})
        if isinstance(j, dict) and isinstance(j.get("data"), list):
            return j["data"]
        return []


def walk_catalog(top_nodes: list) -> list[dict]:
    """カタログツリーを平坦化して {path, name, report_id, _id} のleaf一覧を返す。"""
    out: list[dict] = []

    def rec(node, path):
        nm = node.get("name")
        p = path + [nm] if nm else path
        if node.get("type") == "report" and node.get("report_id"):
            out.append({"path": " > ".join(p), "name": nm,
                        "report_id": node["report_id"], "nid": node.get("_id")})
        for ch in node.get("children") or []:
            rec(ch, p)

    for t in top_nodes:
        rec(t, [])
    return out

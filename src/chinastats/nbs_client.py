"""国家統計局(NBS)データポータルの低レベルクライアント。

エンドポイント: https://data.stats.gov.cn/easyquery.htm

対応メソッド:
  - getTree   : 指標(zb)や時間(sj)ディメンションのツリーを取得
  - QueryData : 指定した指標・地区・時間のデータを取得

注意:
  * サイトは初回アクセス時に Cookie を発行するため、最初にトップページを
    GET してセッションを温めてから easyquery を叩く。
  * data.stats.gov.cn は証明書まわりが不安定なことがあるため、
    verify=True で失敗したら verify=False にフォールバックする。
  * この作業環境(Claude Code on web)からはネットワークポリシーで
    data.stats.gov.cn がブロックされるため、実データ取得は
    GitHub Actions ランナー上で行う前提。
"""

from __future__ import annotations

import logging
import os
import time
import warnings
from typing import Any

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://data.stats.gov.cn/easyquery.htm"
HOME_URL = "https://data.stats.gov.cn/"
# セッション確立用の照会ページ。ここを先に開くと easyquery が通りやすい。
PRIME_URLS = [
    "https://data.stats.gov.cn/",
    "https://data.stats.gov.cn/easyquery.htm?cn=A01",   # 全国年度の入口
    "https://data.stats.gov.cn/easyquery.htm?cn=E0101",  # 全国月度の入口
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://data.stats.gov.cn/easyquery.htm?cn=E0101",
    "Origin": "https://data.stats.gov.cn",
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "sec-ch-ua": '"Chromium";v="125", "Not.A/Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# 照会ページ閲覧時に送るブラウザ的ヘッダ（ドキュメント遷移）
PRIME_HEADERS = {
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class NBSError(RuntimeError):
    """NBS API 呼び出しに関する例外。"""


def _is_forbidden(exc: Exception) -> bool:
    """例外が HTTP 403 かどうか。"""
    resp = getattr(exc, "response", None)
    return resp is not None and getattr(resp, "status_code", None) == 403


def _mask_proxy(proxy: str) -> str:
    """ログ用に proxy の資格情報を伏せる。"""
    if "@" in proxy:
        scheme_sep = proxy.split("://", 1)
        if len(scheme_sep) == 2:
            scheme, rest = scheme_sep
            host = rest.split("@", 1)[1]
            return f"{scheme}://***@{host}"
    return proxy


class NBSClient:
    """NBS easyquery クライアント。

    Parameters
    ----------
    timeout:
        1リクエストのタイムアウト秒。
    max_retries:
        通信失敗時のリトライ回数（指数バックオフ）。
    sleep:
        連続リクエスト間の待機秒。過度なアクセスを避けるための礼儀。
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 4,
        sleep: float = 0.6,
        proxy: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        # NBS の WAF は中国国外/クラウドの IP を拒否する(reason:UrlACL)。
        # 中国側の IP を持つプロキシを指定すると通過できる。
        # proxy 例: "http://user:pass@host:port"
        self._proxy = proxy or os.environ.get("NBS_PROXY") or None
        if self._proxy:
            self.session.proxies.update({"http": self._proxy, "https": self._proxy})
            logger.info("NBS プロキシを使用します: %s", _mask_proxy(self._proxy))
        self._verify = True
        self._primed = False

    # ------------------------------------------------------------------
    # 内部ユーティリティ
    # ------------------------------------------------------------------
    def _prime(self) -> None:
        """照会ページを順に開いてセッション Cookie を確立する。

        NBS の easyquery は「先に照会ページを閲覧してセッションを張る」
        ことを要求するため、トップ→年度入口→月度入口を GET しておく。
        """
        if self._primed:
            return
        for url in PRIME_URLS:
            try:
                self._request("GET", url, params=None, doc=True)
            except NBSError as exc:
                logger.warning("プライミング失敗 %s: %s", url, exc)
        try:
            names = [c.name for c in self.session.cookies]
            logger.info("プライミング後の Cookie: %s", names or "（なし）")
        except Exception:  # noqa: BLE001
            pass
        self._primed = True

    def _request(
        self, method: str, url: str, params: dict[str, Any] | None, doc: bool = False
    ) -> requests.Response:
        """リトライ＋証明書フォールバック付きの HTTP リクエスト。

        doc=True のときは照会ページ閲覧用のドキュメント系ヘッダを使う。
        403 のときは応答本文の断片をログに出し（WAF/地域ブロック判別用）、
        セッションを張り直してから再試行する。
        """
        last_exc: Exception | None = None
        headers = dict(PRIME_HEADERS) if doc else None
        for attempt in range(self.max_retries):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    resp = self.session.request(
                        method,
                        url,
                        params=params,
                        headers=headers,
                        timeout=self.timeout,
                        verify=self._verify,
                    )
                if resp.status_code == 403:
                    snippet = resp.text[:300].replace("\n", " ") if resp.text else ""
                    logger.warning("403 応答本文の断片: %s", snippet)
                resp.raise_for_status()
                return resp
            except requests.exceptions.SSLError as exc:
                # 証明書エラー時は検証を切って一度だけ切り替え
                if self._verify:
                    logger.warning("SSL検証エラー。verify=False に切替えて再試行します。")
                    self._verify = False
                    last_exc = exc
                    continue
                last_exc = exc
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                # 403/セッション切れは張り直して再挑戦（照会ページ以外のとき）
                if not doc and _is_forbidden(exc):
                    self._primed = False
                    self._reprime_light()

            backoff = 2 ** attempt
            logger.warning(
                "リクエスト失敗 (%s/%s)。%s秒待機して再試行: %s",
                attempt + 1,
                self.max_retries,
                backoff,
                last_exc,
            )
            time.sleep(backoff)

        raise NBSError(f"リクエストに失敗しました: {url} :: {last_exc}")

    def _reprime_light(self) -> None:
        """403 後に照会ページを1枚だけ開いてセッションを張り直す。"""
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.session.get(
                    "https://data.stats.gov.cn/easyquery.htm?cn=E0101",
                    headers=dict(PRIME_HEADERS),
                    timeout=self.timeout,
                    verify=self._verify,
                )
        except requests.exceptions.RequestException:
            pass

    def _get_json(self, params: dict[str, Any]) -> Any:
        """easyquery を叩いて JSON を返す。"""
        self._prime()
        # キャッシュバスター。NBS は同一クエリをキャッシュするため付与する。
        params = dict(params)
        params.setdefault("k1", str(int(time.time() * 1000)))
        resp = self._request("GET", BASE_URL, params=params)
        if self.sleep:
            time.sleep(self.sleep)
        try:
            return resp.json()
        except ValueError as exc:  # JSON でない = ブロック/HTML が返った
            snippet = resp.text[:200].replace("\n", " ")
            raise NBSError(f"JSON でない応答: {snippet!r}") from exc

    # ------------------------------------------------------------------
    # 公開メソッド
    # ------------------------------------------------------------------
    def get_tree(self, dbcode: str, wdcode: str = "zb", node_id: str = "zb") -> list[dict]:
        """ディメンションツリーの子ノード一覧を返す。

        Parameters
        ----------
        dbcode:
            データベースコード（hgyd/hgjd/fsyd/fsjd 等）。
        wdcode:
            ディメンションコード。通常は "zb"（指標）。
        node_id:
            親ノードID。ルートは通常 "zb"。

        Returns
        -------
        list[dict]
            各ノードは id / name / isParent などを持つ。
        """
        params = {
            "m": "getTree",
            "dbcode": dbcode,
            "wdcode": wdcode,
            "id": node_id,
        }
        data = self._get_json(params)
        if not isinstance(data, list):
            raise NBSError(f"getTree の応答が想定外です: {type(data)}")
        return data

    def query_data(
        self,
        dbcode: str,
        zb_code: str,
        sj_valuecode: str = "LAST120",
        reg_code: str | None = None,
    ) -> dict:
        """指標データを取得して raw JSON(returndata) を返す。

        Parameters
        ----------
        dbcode:
            データベースコード。
        zb_code:
            指標(zb)のコード。
        sj_valuecode:
            時間(sj)の値コード。"LAST120" のような相対指定、
            "2015-" のような範囲、"201901" のような単一が使える。
        reg_code:
            分省DB(fsyd/fsjd)のときの地区コード。全国DBでは None。
        """
        rowcode = "zb"
        colcode = "sj"
        wds: list[dict] = []
        dfwds: list[dict] = [
            {"wdcode": "zb", "valuecode": zb_code},
            {"wdcode": "sj", "valuecode": sj_valuecode},
        ]
        if reg_code is not None:
            # 地区は固定ディメンション(wds)に置く
            wds.append({"wdcode": "reg", "valuecode": reg_code})

        params = {
            "m": "QueryData",
            "dbcode": dbcode,
            "rowcode": rowcode,
            "colcode": colcode,
            "wds": _to_json(wds),
            "dfwds": _to_json(dfwds),
        }
        data = self._get_json(params)
        if not isinstance(data, dict):
            raise NBSError(f"QueryData の応答が想定外です: {type(data)}")
        returncode = data.get("returncode")
        if returncode not in (200, None):
            raise NBSError(f"QueryData エラー returncode={returncode}: {data.get('returndata')}")
        returndata = data.get("returndata")
        if not isinstance(returndata, dict):
            raise NBSError("QueryData に returndata がありません")
        return returndata


def _to_json(obj: Any) -> str:
    """NBS が期待するコンパクトな JSON 文字列にする。"""
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def parse_datanodes(returndata: dict) -> dict[str, float]:
    """QueryData の returndata から {時間コード: 値} を取り出す。

    datanodes の各要素:
      code: "zb.A020901_sj.202401_reg.110000"
      data: {data: 12345.6, hasdata: true, strdata: "12345.6"}
    のような構造。時間(sj)コードをキーに値を返す。hasdata=False は除外。
    """
    result: dict[str, float] = {}
    datanodes = returndata.get("datanodes", [])
    for node in datanodes:
        wds = node.get("wds", [])
        sj_code = None
        for w in wds:
            if w.get("wdcode") == "sj":
                sj_code = w.get("valuecode")
                break
        if sj_code is None:
            # code 文字列からのフォールバック抽出
            code = node.get("code", "")
            for part in code.split("_"):
                if part.startswith("sj."):
                    sj_code = part[3:]
                    break
        if sj_code is None:
            continue
        d = node.get("data", {})
        if not d.get("hasdata"):
            continue
        val = d.get("data")
        if val is None:
            continue
        try:
            result[sj_code] = float(val)
        except (TypeError, ValueError):
            continue
    return result

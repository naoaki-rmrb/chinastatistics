"""指標名(中国語) → NBS 指標コード(zb) の解決器。

NBS の指標コードはデータベースや時期で変わりうるため直書きを避け、
安定している中国語の指標名からツリーを歩いてコードを引き当てる。

照合は次の順で行う:
  1. 完全一致（記号ゆらぎを正規化した上で）
  2. 候補名リストの順に完全一致
  3. 部分一致（候補名を含むリーフ）

解決結果はキャッシュして無駄なツリー探索を避ける。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .nbs_client import NBSClient, NBSError

logger = logging.getLogger(__name__)


def normalize(name: str) -> str:
    """指標名を照合用に正規化する。

    全角/半角カッコや空白・下線のゆらぎを吸収する。
    """
    if name is None:
        return ""
    s = str(name)
    # 全角カッコ→半角、各種スペース/下線を除去
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("【", "(").replace("】", ")")
    s = re.sub(r"[\s_·・]", "", s)
    return s.strip()


@dataclass
class TreeNode:
    id: str
    name: str
    is_parent: bool


@dataclass
class Resolver:
    """指標ツリーを歩いてコードを解決する。

    Parameters
    ----------
    client:
        NBSClient インスタンス。
    max_depth:
        ツリー探索の最大深さ（暴走防止）。
    """

    client: NBSClient
    max_depth: int = 8
    _leaf_cache: dict[str, dict[str, str]] = field(default_factory=dict)
    resolutions: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    def _children(self, dbcode: str, node_id: str) -> list[TreeNode]:
        raw = self.client.get_tree(dbcode=dbcode, wdcode="zb", node_id=node_id)
        nodes: list[TreeNode] = []
        for item in raw:
            nid = item.get("id")
            name = item.get("name", "")
            is_parent = bool(item.get("isParent")) or str(item.get("isParent")).lower() == "true"
            if nid:
                nodes.append(TreeNode(id=nid, name=name, is_parent=is_parent))
        return nodes

    def _all_leaves(self, dbcode: str) -> dict[str, str]:
        """DB 内の全リーフ {正規化名: コード} を返す（キャッシュ）。

        深さ優先でツリー全体を歩く。NBS の指標数は DB あたり数百程度なので
        一度歩けば以降はキャッシュから解決できる。
        """
        if dbcode in self._leaf_cache:
            return self._leaf_cache[dbcode]

        leaves: dict[str, str] = {}
        # (node_id, depth)
        stack: list[tuple[str, int]] = [("zb", 0)]
        visited: set[str] = set()
        while stack:
            node_id, depth = stack.pop()
            if node_id in visited or depth > self.max_depth:
                continue
            visited.add(node_id)
            try:
                children = self._children(dbcode, node_id)
            except NBSError as exc:
                logger.warning("ツリー取得失敗 db=%s id=%s: %s", dbcode, node_id, exc)
                continue
            for ch in children:
                if ch.is_parent:
                    stack.append((ch.id, depth + 1))
                else:
                    leaves[normalize(ch.name)] = ch.id
        logger.info("db=%s のリーフ指標を %d 件収集", dbcode, len(leaves))
        self._leaf_cache[dbcode] = leaves
        return leaves

    # ------------------------------------------------------------------
    def resolve(
        self, dbcode: str, candidates: list[str], context: dict | None = None
    ) -> tuple[str | None, str | None]:
        """候補名リストから最初に見つかった (コード, 実際の指標名) を返す。

        見つからなければ (None, None)。context は解決ログ用のメタ情報。
        """
        code, matched = self._resolve_inner(dbcode, candidates)
        if context is not None:
            self.resolutions.append({
                "db": dbcode,
                "indicator": context.get("indicator"),
                "role": context.get("role"),
                "code": code,
                "matched": matched,
            })
        return code, matched

    def _resolve_inner(self, dbcode: str, candidates: list[str]) -> tuple[str | None, str | None]:
        if not candidates:
            return None, None
        leaves = self._all_leaves(dbcode)
        # 正規化名 -> コード の逆引きに、元名の対応も欲しいので再構築
        norm_to_code = leaves
        # 元の名前を保持するため、コード->名 は別途持てないので
        # 完全一致は正規化名で行い、名は候補名を返す。
        # 1) 完全一致
        for cand in candidates:
            ncand = normalize(cand)
            if ncand in norm_to_code:
                return norm_to_code[ncand], cand
        # 2) 部分一致（候補名がリーフ名に含まれる／リーフ名が候補に含まれる）
        for cand in candidates:
            ncand = normalize(cand)
            for nleaf, code in norm_to_code.items():
                if ncand and (ncand in nleaf or nleaf in ncand):
                    return code, cand
        return None, None

    def dump_leaves(self, dbcode: str) -> dict[str, str]:
        """デバッグ用: DB 内の全リーフ {正規化名: コード} を返す。"""
        return dict(self._all_leaves(dbcode))

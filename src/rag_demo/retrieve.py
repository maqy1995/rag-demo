"""Retrieve: 真向量检索 (FAISS + BaseEmbedder, ADR-0002 / MAQ-35).

v1 contract — `docs/dev/design.md` §3.3:
  - `filters: dict | None` kwarg (v1 透传不强制实现, v0.2 升级为 RetrieveFilters TypedDict)
  - 返回 `list[Hit]`
  - 稳定排序: score 降序, 同分按 (file, chunk_id) 升序 (FAISS 顺序天然稳定)
  - snippet ≤ 200 字 (超长截断)

新实现要点 (MAQ-35):
  - 加载 `data/index/faiss.index` + `faiss_meta.json`
  - 用 `embedder.embed_one(query)` 拿 query 向量
  - 调 `VectorStore.search(query_vec, top_k)`
  - 转 list[Hit], vault:// 协议 encode
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .llm import BaseEmbedder
from .vault_uri import encode as vault_uri_encode
from .vector import VectorStore

# 模块级 embedder 单例 — 由 web/__main__ 启动时 set_embedder() 注入
# (MAQ-51: 之前 retrieve() 默认 embedder=None → 全 0 向量, 检索永远 0 分)
_embedder: BaseEmbedder | None = None


def set_embedder(emb: BaseEmbedder | None) -> None:
    """注入 embedder. None 表示 stub 模式 (smoke)."""
    global _embedder
    _embedder = emb


def get_embedder() -> BaseEmbedder | None:
    return _embedder


@dataclass(frozen=True)
class Hit:
    """v1 design §3.3 — single chunk returned from `retrieve()`."""

    source: str  # vault://<vault>/<relpath>#<anchor>  (PRD §7.1)
    file: str  # 相对 vault 根的路径
    heading: str  # 命中所在 heading（原文，不做 slug）
    chunk_id: int  # 文件内唯一编号
    snippet: str  # 命中片段（≤ 200 字）
    score: float  # 0-1，ANN 返回值归一化


def _snippet(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def retrieve(
    query: str,
    *,
    index_dir: str | Path,
    top_k: int = 5,
    filters: dict | None = None,
    embedder: BaseEmbedder | None = None,
    vault_name: str = "my-notes",
    dim: int = 0,
) -> list[Hit]:
    """真向量检索. 返回 Top-K 命中.

    Args:
        query: 用户问题.
        index_dir: data/index 目录 (含 faiss.index + faiss_meta.json).
        top_k: 取前 K.
        filters: v1 透传不强制实现 (预留 §3.2 F11).
        embedder: 注入的 embedder 实例 (None 时用 dummy 全 0 向量, 仅供 smoke).
        vault_name: 用于 vault:// 协议的 {vault} 占位 (默认 "my-notes").
        dim: 向量维度; 0 表示从 index 自动检测 (推荐, 支持任意 provider).
             显式给值时, 必须与 index 实际 dim 一致, 否则 AppError(503).
    """
    _ = filters  # v1 透传, 不强制
    index_path = Path(index_dir)
    store = VectorStore(index_dir=index_path, dim=dim).load()
    if store.is_empty():
        return []
    # MAQ-51: load() 后 store.dim 是 index 实际 dim (auto-detect 时已更新)
    effective_dim = store.dim
    # 真实 query embed — 优先用显式注入, 否则回落模块级单例 (MAQ-51)
    if embedder is None:
        embedder = _embedder
    if embedder is None:
        # smoke 路径: 全 0 向量, 必然搜不到 (US4 等价路径, 返 [])
        query_vec = [0.0] * effective_dim
    else:
        query_vec = embedder.embed_one(query)
    raw_hits = store.search(query_vec, top_k=top_k)
    hits: list[Hit] = []
    for score, meta in raw_hits:
        text = str(meta.get("text", ""))
        hits.append(
            Hit(
                source=vault_uri_encode(
                    vault=vault_name,
                    path=str(meta.get("source", meta.get("file", ""))),
                    anchor=str(meta.get("heading", "")),
                ),
                file=str(meta.get("file", meta.get("source", ""))),
                heading=str(meta.get("heading", "")),
                chunk_id=int(meta.get("chunk_id", 0)),
                snippet=_snippet(text),
                score=float(score),
            )
        )
    return hits

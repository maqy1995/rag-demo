"""Retrieve: stub for fetching top-k chunks relevant to a query.

Returns an empty list until a real vector store is wired in.

v1 contract — `docs/dev/design.md` §3.3:
  - `filters: dict | None` kwarg (v1 未类型化, v0.2 升级为 RetrieveFilters TypedDict)
  - 返回 `list[Hit]`
  - 稳定排序: score 降序, 同分按 (file, chunk_id) 升序
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Hit:
    """v1 design §3.3 — single chunk returned from `retrieve()`."""

    source: str  # vault://<vault>/<relpath>#<anchor>  (PRD §7.1)
    file: str  # 相对 vault 根的路径
    heading: str  # 命中所在 heading（原文，不做 slug）
    chunk_id: int  # 文件内唯一编号
    snippet: str  # 命中片段（≤ 200 字）
    score: float  # 0-1，ANN 返回值归一化


def retrieve(
    query: str,
    *,
    index_dir: str | Path,
    top_k: int = 5,
    filters: dict | None = None,
) -> list[Hit]:
    """Stub: 始终返回空 list. 真实实现接 ADR-0002 向量库."""
    _ = (query, index_dir, top_k, filters)  # TODO: replace stub with real retrieval
    return []

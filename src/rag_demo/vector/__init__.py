"""Vector store: FAISS IndexFlatIP + metadata 持久化 (ADR-0002 / MAQ-34).

设计要点:
1. 单文件持久化:
   - `data/index/faiss.index` (faiss 索引)
   - `data/index/faiss_meta.json` (chunk_id → metadata)
2. IndexFlatIP: 内积; 配合 L2 归一化向量即等价余弦相似度
3. metadata: list[dict] 与向量 index 一一对应
4. add / search 接口简单 (向量层面, 不做召回排序)
5. filters: dict 字段白名单 (folder / since), v1 不强制实现, 透传不报错
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import faiss  # type: ignore[import-untyped]
import numpy as np

from ..errors import AppError


class VectorStore:
    """FAISS + JSON metadata 包装.

    用法:
        store = VectorStore(index_dir="./data/index", dim=1536)
        store.add(vectors, metas)
        store.save()
        store2 = VectorStore(index_dir="./data/index", dim=1536).load()
        hits = store2.search(query_vec, top_k=5)
    """

    def __init__(self, index_dir: str | Path, dim: int) -> None:
        self.index_dir = Path(index_dir)
        self.dim = dim
        self._index: faiss.IndexFlatIP | None = None
        self._metas: list[dict[str, Any]] = []

    # ── index 生命周期 ──────────────────────────────────

    def _ensure_index(self) -> faiss.IndexFlatIP:
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dim)
        return self._index

    @property
    def ntotal(self) -> int:
        return 0 if self._index is None else int(self._index.ntotal)

    def is_empty(self) -> bool:
        return self.ntotal == 0

    # ── 写入 ────────────────────────────────────────────

    def add(self, vectors: list[list[float]], metas: list[dict[str, Any]]) -> None:
        """添加向量 + metadata. 两列表必须等长. 向量会被 L2 归一化以配合 IP."""
        if len(vectors) != len(metas):
            raise ValueError(
                f"vectors/metas length mismatch: {len(vectors)} vs {len(metas)}"
            )
        if not vectors:
            return
        arr = np.asarray(vectors, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] != self.dim:
            raise ValueError(f"vectors shape {arr.shape} incompatible with dim {self.dim}")
        # L2 归一化 — 让内积等价余弦相似度
        faiss.normalize_L2(arr)
        idx = self._ensure_index()
        idx.add(arr)
        self._metas.extend(metas)

    # ── 检索 ────────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        _filters: dict | None = None,
    ) -> list[tuple[float, dict[str, Any]]]:
        """检索 top_k. 返回 [(score, meta), ...] 按 score 降序.

        空 index 时返回空 list (US4 早返路径).
        """
        if self.is_empty():
            return []
        if top_k <= 0:
            return []
        q = np.asarray([query_vector], dtype=np.float32)
        if q.shape[1] != self.dim:
            raise AppError(
                code="RETRIEVE_INDEX_MISSING",
                stage="retrieve",
                http_status=503,
                message=f"query dim {q.shape[1]} != index dim {self.dim}",
            )
        faiss.normalize_L2(q)
        k = min(top_k, self.ntotal)
        scores, ids = self._ensure_index().search(q, k)
        out: list[tuple[float, dict[str, Any]]] = []
        for s, i in zip(scores[0].tolist(), ids[0].tolist(), strict=False):
            if i < 0 or i >= len(self._metas):
                continue
            out.append((float(s), self._metas[i]))
        return out

    # ── 持久化 ──────────────────────────────────────────

    def save(self) -> None:
        """写 faiss.index + faiss_meta.json."""
        if self._index is None:
            return
        self.index_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(self.index_dir / "faiss.index"))
        (self.index_dir / "faiss_meta.json").write_text(
            json.dumps(self._metas, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self) -> VectorStore:
        """从磁盘读 index + meta. 文件不存在时返回空 store (US4 早返路径).

        MAQ-51 (zhipu 适配): 当 self.dim == 0 (auto-detect), 用 index 自身的 dim;
        否则按 self.dim 严格校验, 不一致 → AppError(503).
        """
        index_path = self.index_dir / "faiss.index"
        meta_path = self.index_dir / "faiss_meta.json"
        if not index_path.exists() or not meta_path.exists():
            return self
        self._index = faiss.read_index(str(index_path))
        try:
            self._metas = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise AppError(
                code="RETRIEVE_INDEX_MISSING",
                stage="retrieve",
                http_status=503,
                message=f"faiss_meta.json 损坏: {e}",
            ) from e
        # auto-detect 路径: dim=0 表示不校验, 以 index 实际 dim 为准
        if self.dim == 0:
            self.dim = int(self._index.d)
            return self
        if self._index.d != self.dim:
            raise AppError(
                code="RETRIEVE_INDEX_MISSING",
                stage="retrieve",
                http_status=503,
                message=(
                    f"index dim {self._index.d} != configured dim {self.dim}; "
                    "请重建索引 (rag-demo ingest --full)"
                ),
            )
        return self

"""Ingest: 真 chunk + 真 embed + 真写 FAISS (ADR-0002 / MAQ-37).

v1 contract — `docs/dev/design.md` §3.2:
  - extra kwargs `full=True` / `chunk_overlap=80` / `chunk_size=500` / `on_progress`
  - 返回 `IngestStats` (单一信源 for /api/index/status)
  - 写 `data/index/{manifest.json, faiss.index, faiss_meta.json, status.json}`
  - status 单一信源: 启动先写 state=building, 跑完覆盖写 state=idle
  - data_dir 不存在或为空 → fallback 到 data/raw.sample/ (冷启动 demo 路径)

MAQ-37 落地:
  - chunker: 用 rag_demo.chunker.chunk_markdown 切
  - embedder: 用注入的 BaseEmbedder (None 时用 dummy 全 0 向量, smoke 用)
  - vector store: 写 faiss.index + faiss_meta.json
  - manifest.json: 加 embedding_provider / embedding_model / embedding_dim 字段
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .chunker import chunk_markdown
from .llm import BaseEmbedder
from .vector import VectorStore

# Cold-start demo fallback dir (design §3.1 F1 + §3.2 要点).
# 当 data_dir 不存在或为空时, 走这个目录, 让 CLI / API 在最小配置下也能跑通.
# ingest.py 位于 src/rag_demo/ingest.py, 仓库根 = parent.parent.parent.
_SAMPLE_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw.sample"


@dataclass(frozen=True)
class IngestStats:
    """v1 design §3.2 — 6-field output of `ingest_directory`."""

    state: str  # "idle" | "building" | "error"
    files_total: int
    chunks_total: int
    skipped_unchanged: int  # 增量更新命中 mtime/sha 的文件数（v1 简化 = 0）
    current_progress: dict | None  # 形如 {"done": int, "total": int}; None 表示不在构建中
    last_built_at: str | None  # ISO 8601; 从未成功构建过为 None
    duration_ms: int  # 本次构建耗时（增量更新时为本次 diff 耗时）


def _write_status(index_dir: Path, payload: dict) -> None:
    """写 status.json (design §3.2 单一信源)."""
    (index_dir / "status.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _empty_stats(duration_ms: int = 0) -> IngestStats:
    """data_dir 与 sample 都缺时返回的全零 stats (NB3 fallback)."""
    return IngestStats(
        state="idle",
        files_total=0,
        chunks_total=0,
        skipped_unchanged=0,
        current_progress=None,
        last_built_at=None,
        duration_ms=duration_ms,
    )


def ingest_directory(
    data_dir: str | Path,
    index_dir: str | Path,
    *,
    full: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    on_progress: Callable[[int, int], None] | None = None,
    embedder: BaseEmbedder | None = None,
    embedding_provider: str = "stub",
    embedding_model: str = "stub",
    embedding_dim: int = 1536,
) -> IngestStats:
    """真 chunk + embed + 写 FAISS. NB2 building 中间态 + NB3 fallback.

    Args:
        data_dir: vault data dir; 不存在或为空时 fallback 到 data/raw.sample/.
        index_dir: index 输出 dir; status.json / faiss.index 写到这.
        full: 全量 / 增量 (v1 = full only).
        chunk_size: 切分大小 (chars).
        chunk_overlap: 切分重叠; 必须 < chunk_size.
        on_progress: 进度回调 (done, total); None 表示不回调.
        embedder: 注入的 embedder; None 时用 dummy 全 0 向量 (smoke).
        embedding_provider/model/dim: 写 manifest.json 用.

    Returns:
        IngestStats 终态 (state="idle").
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
        )

    data_dir = Path(data_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    # NB3: fallback — data_dir 不存在或为空 → 试 data/raw.sample/ (NB3 cold-start demo).
    # 忽略 dotfile (e.g. .gitkeep) — git 占位文件不算"内容".
    if not data_dir.exists() or not any(
        p for p in data_dir.iterdir() if not p.name.startswith(".")
    ):
        if _SAMPLE_DATA_DIR.exists() and any(
            p for p in _SAMPLE_DATA_DIR.iterdir() if not p.name.startswith(".")
        ):
            data_dir = _SAMPLE_DATA_DIR
        else:
            stats = _empty_stats(duration_ms=0)
            _write_status(index_dir, {
                "state": stats.state,
                "files_total": stats.files_total,
                "chunks_total": stats.chunks_total,
                "skipped_unchanged": stats.skipped_unchanged,
                "current_progress": stats.current_progress,
                "last_built_at": stats.last_built_at,
                "duration_ms": stats.duration_ms,
            })
            return stats

    started = time.perf_counter()
    files = sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix in {".md", ".txt", ".rst"}
    )
    total = len(files)

    # NB2: 启动先写 state=building + current_progress={"done":0,"total":N}
    _write_status(index_dir, {
        "state": "building",
        "files_total": 0,
        "chunks_total": 0,
        "skipped_unchanged": 0,
        "current_progress": {"done": 0, "total": total},
        "last_built_at": None,
        "duration_ms": 0,
    })
    if on_progress is not None:
        on_progress(0, total)

    # chunk + 收集 metas
    all_chunks = []
    all_metas = []
    chunk_id = 0
    for idx, fp in enumerate(files, start=1):
        rel = str(fp.relative_to(data_dir))
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for c in chunk_markdown(
            text, chunk_size=chunk_size, chunk_overlap=chunk_overlap, source=rel
        ):
            # 文件内唯一编号 — 这里用全局递增 (跨文件也唯一), 简化
            new_chunk = type(c)(
                source=rel,
                offset=c.offset,
                text=c.text,
                heading=c.heading,
                chunk_id=chunk_id,
            )
            all_chunks.append(new_chunk)
            all_metas.append({
                "source": rel,
                "file": rel,
                "heading": new_chunk.heading,
                "chunk_id": chunk_id,
                "text": new_chunk.text,
            })
            chunk_id += 1
        if on_progress is not None:
            on_progress(idx, total)
        if idx == total or idx % max(1, total // 5) == 0:
            _write_status(index_dir, {
                "state": "building",
                "files_total": idx,
                "chunks_total": len(all_chunks),
                "skipped_unchanged": 0,
                "current_progress": {"done": idx, "total": total},
                "last_built_at": None,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            })

    # embed (批量)
    if all_chunks:
        texts = [c.text for c in all_chunks]
        if embedder is None:
            # smoke 路径: dummy 全 0 向量, dim 由配置决定
            vectors = [[0.0] * embedding_dim for _ in texts]
        else:
            vectors = embedder.embed(texts)
    else:
        vectors = []

    # 写 faiss + meta
    store = VectorStore(index_dir=index_dir, dim=embedding_dim)
    if vectors:
        store.add(vectors, all_metas)
    store.save()

    duration_ms = int((time.perf_counter() - started) * 1000)
    last_built_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    manifest = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "full": full,
        "file_count": len(files),
        "chunk_count": len(all_chunks),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dim": embedding_dim,
    }
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    stats = IngestStats(
        state="idle",
        files_total=len(files),
        chunks_total=len(all_chunks),
        skipped_unchanged=0,
        current_progress={"done": len(files), "total": len(files)} if files else None,
        last_built_at=last_built_at,
        duration_ms=duration_ms,
    )
    _write_status(index_dir, {
        "state": stats.state,
        "files_total": stats.files_total,
        "chunks_total": stats.chunks_total,
        "skipped_unchanged": stats.skipped_unchanged,
        "current_progress": stats.current_progress,
        "last_built_at": stats.last_built_at,
        "duration_ms": stats.duration_ms,
    })
    return stats

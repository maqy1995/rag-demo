"""Ingest: load documents from disk, chunk, and (later) embed.

The current implementation is a stub that walks the data directory,
counts text files, and writes a manifest. Replace the body with a real
loader + chunker + embedder once the user picks a stack.

v1 contract — `docs/dev/design.md` §3.2:
  - extra kwargs `full=True` / `chunk_overlap=80`
  - returns `IngestStats` (single source for /api/index/status)
  - writes `data/index/status.json` alongside `manifest.json` (status 单一信源)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestStats:
    """v1 design §3.2 — 6-field output of `ingest_directory`."""

    state: str  # "idle" | "building" | "error"
    files_total: int
    chunks_total: int
    skipped_unchanged: int  # 增量更新命中 mtime/sha 的文件数（stub 阶段 = 0）
    current_progress: dict | None  # 形如 {"done": int, "total": int}; None 表示不在构建中
    last_built_at: str | None  # ISO 8601; 从未成功构建过为 None
    duration_ms: int  # 本次构建耗时（增量更新时为本次 diff 耗时）


def ingest_directory(
    data_dir: str | Path,
    index_dir: str | Path,
    *,
    full: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> IngestStats:
    """Stub implementation — walk + chunk + write manifest + status.

    Raises:
        ValueError: chunk_overlap >= chunk_size
        FileNotFoundError: data_dir does not exist (stub 不做冷启动 demo 兜底,
            由调用方 —— `__main__.up` / `web` —— 决定如何 fallback)
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
        )

    data_dir = Path(data_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()

    if not data_dir.exists():
        raise FileNotFoundError(f"data dir not found: {data_dir}")

    files = sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix in {".md", ".txt", ".rst"}
    )
    chunks: list[dict] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        # stub chunker: 等长切分, 不做 overlap (v0.3 占位; v1 走 Recursive splitter)
        for i in range(0, len(text), chunk_size):
            chunks.append({
                "source": str(fp.relative_to(data_dir)),
                "offset": i,
                "text": text[i : i + chunk_size],
            })

    duration_ms = int((time.perf_counter() - started) * 1000)
    last_built_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    manifest = {
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "full": full,
        "file_count": len(files),
        "chunk_count": len(chunks),
    }
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    stats = IngestStats(
        state="idle",  # stub 同步跑完即 idle; 后台线程场景由调用方改写 status.json
        files_total=len(files),
        chunks_total=len(chunks),
        skipped_unchanged=0,  # stub 阶段不实现 mtime/sha diff
        current_progress={"done": len(files), "total": len(files)} if files else None,
        last_built_at=last_built_at,
        duration_ms=duration_ms,
    )
    # 同步写 status.json (design §3.2 要点: status 单一信源 = data/index/status.json)
    (index_dir / "status.json").write_text(
        json.dumps(
            {
                "state": stats.state,
                "files_total": stats.files_total,
                "chunks_total": stats.chunks_total,
                "skipped_unchanged": stats.skipped_unchanged,
                "current_progress": stats.current_progress,
                "last_built_at": stats.last_built_at,
                "duration_ms": stats.duration_ms,
            },
            ensure_ascii=False,
        )
    )
    return stats

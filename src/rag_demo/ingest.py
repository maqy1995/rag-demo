"""Ingest: load documents from disk, chunk, and (later) embed.

The current implementation is a stub that walks the data directory,
counts text files, and writes a manifest. Replace the body with a real
loader + chunker + embedder once the user picks a stack.

v1 contract — `docs/dev/design.md` §3.2:
  - extra kwargs `full=True` / `chunk_overlap=80`
  - returns `IngestStats` (single source for /api/index/status)
  - writes `data/index/status.json` alongside `manifest.json` (status 单一信源)
  - 启动先写 status.json (state=building, current_progress={"done":0,"total":N}),
    每 N 个文件调 on_progress 一次, 跑完覆盖写 state=idle
  - data_dir 不存在或为空 → fallback 到 data/raw.sample/ (冷启动 demo 路径,
    design §3.1 F1 + §3.2 要点)
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

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
    skipped_unchanged: int  # 增量更新命中 mtime/sha 的文件数（stub 阶段 = 0）
    current_progress: dict | None  # 形如 {"done": int, "total": int}; None 表示不在构建中
    last_built_at: str | None  # ISO 8601; 从未成功构建过为 None
    duration_ms: int  # 本次构建耗时（增量更新时为本次 diff 耗时）


def _write_status(index_dir: Path, payload: dict) -> None:
    """写 status.json (design §3.2 单一信源)."""
    (index_dir / "status.json").write_text(
        json.dumps(payload, ensure_ascii=False)
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
) -> IngestStats:
    """Stub implementation — walk + chunk + write manifest + status.

    Args:
        data_dir: vault data dir; 不存在或为空时 fallback 到 data/raw.sample/.
        index_dir: index output dir; status.json 写到这.
        full: 全量 / 增量 (stub 阶段 = full only).
        chunk_size: 切分大小 (chars).
        chunk_overlap: 切分重叠; 必须 < chunk_size.
        on_progress: 进度回调 (done, total); None 表示不回调.

    Returns:
        IngestStats 终态 (state="idle").

    Raises:
        ValueError: chunk_overlap >= chunk_size.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
        )

    data_dir = Path(data_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    # NB3: fallback — data_dir 不存在或为空 → 试 data/raw.sample/ (NB3 cold-start demo).
    # 都不存在时返回 idle + 全零 stats, 不抛错.
    if not data_dir.exists() or not any(data_dir.iterdir()):
        if _SAMPLE_DATA_DIR.exists() and any(_SAMPLE_DATA_DIR.iterdir()):
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

    chunks: list[dict] = []
    # stub chunker: 等长切分, 不做 overlap (v0.3 占位; v1 走 Recursive splitter)
    for idx, fp in enumerate(files, start=1):
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for i in range(0, len(text), chunk_size):
            chunks.append({
                "source": str(fp.relative_to(data_dir)),
                "offset": i,
                "text": text[i : i + chunk_size],
            })
        # NB2: 进度回调 + 周期性写 status.json (每 N 个文件, 至少 1 次)
        if on_progress is not None:
            on_progress(idx, total)
        if idx == total or idx % max(1, total // 5) == 0:
            _write_status(index_dir, {
                "state": "building",
                "files_total": idx,
                "chunks_total": len(chunks),
                "skipped_unchanged": 0,
                "current_progress": {"done": idx, "total": total},
                "last_built_at": None,
                "duration_ms": int((time.perf_counter() - started) * 1000),
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
        state="idle",  # 跑完覆盖写 idle (NB2)
        files_total=len(files),
        chunks_total=len(chunks),
        skipped_unchanged=0,  # stub 阶段不实现 mtime/sha diff
        current_progress={"done": len(files), "total": len(files)} if files else None,
        last_built_at=last_built_at,
        duration_ms=duration_ms,
    )
    # 同步写 status.json (design §3.2 要点: status 单一信源 = data/index/status.json)
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

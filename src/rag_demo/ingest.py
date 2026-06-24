"""Ingest: load documents from disk, chunk, and (later) embed.

The current implementation is a stub that just walks the data directory,
counts text files, and writes a manifest. Replace the body with a real
loader + chunker + embedder once the user picks a stack.
"""

from __future__ import annotations

import json
from pathlib import Path


def ingest_directory(data_dir: str | Path, index_dir: str | Path, *, chunk_size: int) -> int:
    data_dir = Path(data_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    if not data_dir.exists():
        raise FileNotFoundError(f"data dir not found: {data_dir}")

    files = sorted(p for p in data_dir.rglob("*") if p.is_file() and p.suffix in {".md", ".txt", ".rst"})
    chunks: list[dict] = []
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for i in range(0, len(text), chunk_size):
            chunks.append({"source": str(fp.relative_to(data_dir)), "offset": i, "text": text[i : i + chunk_size]})

    manifest = {"chunk_size": chunk_size, "file_count": len(files), "chunk_count": len(chunks)}
    (index_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return len(chunks)

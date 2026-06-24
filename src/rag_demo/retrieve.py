"""Retrieve: stub for fetching top-k chunks relevant to a query.

Returns an empty list until a real vector store is wired in.
"""

from __future__ import annotations

from pathlib import Path


def retrieve(query: str, *, index_dir: str | Path, top_k: int) -> list[dict]:
    _ = query, index_dir, top_k  # TODO: replace stub with real retrieval
    return []

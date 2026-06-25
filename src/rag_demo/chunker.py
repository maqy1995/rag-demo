"""Chunker: 标题 + 长度混合切分 (ADR-0002 / MAQ-33).

设计要点 (per design §3.2 + MAQ-33 验收):
1. 标题优先切 — 按 markdown `#` / `##` / `###` 边界分段
2. 段内再按 chunk_size 切 (默认 500 chars)
3. overlap 真实生效 — 下一段开头 80 chars 与上一段末尾重叠
4. heading 字段记录当前所在标题 (原文, 不做 slug 化 — design §3.3)
5. chunk_id 在文件内从 0 起编, 唯一

输出 dataclass:
    Chunk(source: str, offset: int, text: str, heading: str, chunk_id: int)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """单 chunk. `source` 是相对 vault 根路径, `offset` 是 chunk 起始 char 位置."""

    source: str
    offset: int
    text: str
    heading: str
    chunk_id: int


def _split_by_heading(text: str) -> list[tuple[str, str]]:
    """按 markdown 标题切分. 返回 [(heading, body_text), ...].

    第一个 entry 的 heading 是空字符串 (代表文件 preamble, 即第一个标题前的内容).
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]
    sections: list[tuple[str, str]] = []
    # 前言段 (第一个标题前)
    if matches[0].start() > 0:
        sections.append(("", text[: matches[0].start()]))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))
    return sections


def _split_by_length(body: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """按长度切分, 带 overlap. body 是单段 (无标题) 文本."""
    body = body.strip()
    if not body:
        return []
    if len(body) <= chunk_size:
        return [body]
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - chunk_overlap)
    while start < len(body):
        end = min(start + chunk_size, len(body))
        chunk = body[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(body):
            break
        start += step
    return chunks


def chunk_markdown(
    text: str,
    *,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    source: str = "",
) -> list[Chunk]:
    """按标题 + 长度切分 markdown 文本.

    Args:
        text: 完整 markdown 文本.
        chunk_size: 单 chunk 字符上限 (默认 500).
        chunk_overlap: 相邻 chunk 重叠字符数 (默认 80; 必须 < chunk_size).
        source: 相对 vault 根路径 (仅记在 Chunk.source 上).

    Returns:
        list[Chunk], chunk_id 从 0 起连续编号.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
        )
    sections = _split_by_heading(text)
    chunks: list[Chunk] = []
    chunk_id = 0
    cursor = 0  # 当前在原 text 中的位置 (用于 offset)
    for heading, body in sections:
        # 跳过标题本身 (不算入 chunk 文本)
        if not body.strip():
            cursor += len(body)
            continue
        # 段内按长度切
        for piece in _split_by_length(body, chunk_size, chunk_overlap):
            # 计算 piece 在原 text 中的 offset (cursor + piece 在 body 中的位置)
            # 简化: 估算为 cursor + body.find(piece[:40])
            offset = cursor + body.find(piece[:40])
            chunks.append(
                Chunk(
                    source=source,
                    offset=max(0, offset),
                    text=piece,
                    heading=heading,
                    chunk_id=chunk_id,
                )
            )
            chunk_id += 1
        cursor += len(body)
    return chunks

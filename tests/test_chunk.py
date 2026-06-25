"""Tests for src/rag_demo/chunker.py (MAQ-33)."""
from __future__ import annotations

import pytest

from rag_demo.chunker import chunk_markdown


def test_empty_text_returns_empty_list():
    assert chunk_markdown("") == []


def test_no_heading_single_chunk():
    text = "hello world, this is plain text without any heading markers."
    chunks = chunk_markdown(text)
    assert len(chunks) == 1
    assert chunks[0].heading == ""
    assert "plain text" in chunks[0].text


def test_chunk_size_limit_respected():
    long = "a" * 1500
    chunks = chunk_markdown(long, chunk_size=500, chunk_overlap=80)
    # 1500 chars / (500-80) = ~3.6, so should be 4 chunks
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.text) <= 500


def test_overlap_respected():
    long = "abcdefghij" * 100  # 1000 chars
    chunks = chunk_markdown(long, chunk_size=200, chunk_overlap=50)
    # 相邻 chunk 末尾 50 字符应与下一 chunk 开头 50 字符重叠
    if len(chunks) >= 2:
        tail = chunks[0].text[-50:]
        head = chunks[1].text[:50]
        assert tail == head


def test_heading_split():
    text = "# Title 1\nbody1\n\n# Title 2\nbody2\n"
    chunks = chunk_markdown(text)
    headings = [c.heading for c in chunks]
    assert "Title 1" in headings
    assert "Title 2" in headings


def test_heading_hierarchy():
    text = "## H2\nbody\n### H3\nbody\n"
    chunks = chunk_markdown(text)
    headings = [c.heading for c in chunks]
    assert "H2" in headings
    assert "H3" in headings


def test_chunk_id_sequential():
    text = "# A\nbody\n\n# B\nbody\n\n# C\nbody\n"
    chunks = chunk_markdown(text)
    ids = [c.chunk_id for c in chunks]
    assert ids == list(range(len(chunks)))


def test_chunk_overlap_must_be_less_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_markdown("text", chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        chunk_markdown("text", chunk_size=100, chunk_overlap=150)


def test_source_attached_to_all_chunks():
    chunks = chunk_markdown("# A\nbody\n# B\nbody\n", source="notes/foo.md")
    assert len(chunks) >= 2
    for c in chunks:
        assert c.source == "notes/foo.md"


def test_single_long_paragraph_split_correctly():
    para = ("lorem ipsum dolor sit amet " * 30).strip()  # ~450 chars
    chunks = chunk_markdown(para, chunk_size=200, chunk_overlap=40)
    assert len(chunks) >= 2
    # 重叠: 第 2 chunk 开头 40 字符 = 第 1 chunk 末尾 40 字符
    if len(chunks) >= 2:
        assert chunks[0].text[-40:] == chunks[1].text[:40]

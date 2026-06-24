"""Tests for `vault_uri` module (design §7.1 + PRD §7.1 编码规则)."""

from __future__ import annotations

import pytest

from rag_demo.vault_uri import decode, encode

# ── encode / decode 互逆 ────────────────────────────────────


def test_encode_decode_round_trip_ascii() -> None:
    uri = encode("my-notes", "AI/microservice.md", "Service Governance")
    assert uri == "vault://my-notes/AI/microservice.md#Service%20Governance"
    assert decode(uri) == ("my-notes", "AI/microservice.md", "Service Governance")


def test_encode_decode_round_trip_chinese() -> None:
    uri = encode("我的笔记", "AI/微服务治理.md", "服务治理")
    # 中文按 UTF-8 percent-encoding
    vault_decoded = "我的笔记"
    path_decoded = "AI/微服务治理.md"
    assert decode(uri) == (vault_decoded, path_decoded, "服务治理")


def test_encode_decode_empty_anchor() -> None:
    uri = encode("v", "path.md", "")
    # 空 anchor 仍带 # 分隔符
    assert uri.endswith("#")
    assert decode(uri) == ("v", "path.md", "")


# ── 编码规则 ─────────────────────────────────────────────────


def test_encode_space_in_anchor() -> None:
    """空格 -> %20."""
    uri = encode("v", "p.md", "hello world")
    assert "hello%20world" in uri


def test_encode_path_slash_preserved() -> None:
    """path 内部 '/' 不被编码 (作为分隔符)."""
    uri = encode("v", "AI/ML/notes.md", "h")
    assert "AI/ML/notes.md" in uri


def test_encode_chinese_percent() -> None:
    """中文按 UTF-8 percent-encoding."""
    uri = encode("v", "中文.md", "h")
    # UTF-8 of 中 = E4 B8 AD -> %E4%B8%AD
    assert "%E4%B8%AD" in uri


# ── decode 错误路径 ──────────────────────────────────────────


def test_decode_missing_prefix_raises() -> None:
    with pytest.raises(ValueError, match="not a vault"):
        decode("http://example.com/a.md#h")


def test_decode_missing_anchor_raises() -> None:
    with pytest.raises(ValueError, match="missing anchor"):
        decode("vault://my-notes/AI/a.md")  # no #


def test_decode_missing_path_raises() -> None:
    with pytest.raises(ValueError, match="missing path"):
        decode("vault://my-notes#h")  # no / after vault

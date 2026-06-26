"""Tests for `llm/factory.py` (MAQ-51) — 从 AppConfig 构造真 LLM/Embedder."""
from __future__ import annotations

import pytest

from rag_demo.config import AppConfig
from rag_demo.errors import AppError
from rag_demo.llm import build_embedder, build_llm_client
from rag_demo.llm.base import EmbedConfig, LLMConfig


def test_build_llm_client_uses_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_llm_client 把 cfg.{provider,model,base_url,api_key_env} 灌进 LLMConfig."""
    monkeypatch.setenv("MIMAX_API_KEY", "test-minimax-key")
    cfg = AppConfig(
        llm_provider="minimax",
        llm_model="MiniMax-M3",
        llm_base_url="https://api.MiniMax.chat/v1/",
        llm_api_key_env="MIMAX_API_KEY",
        llm_timeout_s=15.0,
        llm_max_retries=1,
    )
    client = build_llm_client(cfg)
    assert client.config == LLMConfig(
        provider="minimax",
        model="MiniMax-M3",
        base_url="https://api.MiniMax.chat/v1/",
        api_key="test-minimax-key",
        timeout_s=15.0,
        max_retries=1,
    )


def test_build_embedder_uses_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_embedder 同理 — 用 cfg.embedding_* 字段构造 EmbedConfig."""
    monkeypatch.setenv("ZHIPU_API_KEY", "test-zhipu-key")
    cfg = AppConfig(
        embedding_provider="zhipu",
        embedding_model="embedding-3",
        embedding_base_url="https://open.bigmodel.cn/api/paas/v4/",
        embedding_api_key_env="ZHIPU_API_KEY",
        embedding_timeout_s=20.0,
        embedding_batch_size=32,
    )
    emb = build_embedder(cfg)
    assert emb.config == EmbedConfig(
        provider="zhipu",
        model="embedding-3",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key="test-zhipu-key",
        timeout_s=20.0,
        batch_size=32,
    )


def test_build_llm_client_raises_on_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """.env 缺 api_key_env 对应变量时抛 AppError(401, GENERATE_LLM_FAIL)."""
    monkeypatch.delenv("MIMAX_API_KEY", raising=False)
    cfg = AppConfig(llm_api_key_env="MIMAX_API_KEY")
    with pytest.raises(AppError) as excinfo:
        build_llm_client(cfg)
    assert excinfo.value.code == "GENERATE_LLM_FAIL"
    assert excinfo.value.http_status == 401
    assert "MIMAX_API_KEY" in excinfo.value.message


def test_build_embedder_raises_on_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 test_build_llm_client_raises_on_missing_key, 但走 embedder 路径."""
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    cfg = AppConfig(embedding_api_key_env="ZHIPU_API_KEY")
    with pytest.raises(AppError) as excinfo:
        build_embedder(cfg)
    assert excinfo.value.code == "GENERATE_LLM_FAIL"
    assert excinfo.value.http_status == 401
    assert "ZHIPU_API_KEY" in excinfo.value.message


def test_build_uses_explicit_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """cfg.llm_api_key_env 显式给非默认 env var, 工厂从那里读 (不读默认)."""
    monkeypatch.setenv("CUSTOM_KEY", "custom-key-value")
    monkeypatch.delenv("MIMAX_API_KEY", raising=False)
    cfg = AppConfig(llm_api_key_env="CUSTOM_KEY")
    client = build_llm_client(cfg)
    assert client.config.api_key == "custom-key-value"

"""Tests for `__main__._cmd_up` 启动期 LLM/embedder 注入 (MAQ-51)."""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(
        host="127.0.0.1",
        port=0,  # 0 = ephemeral, 但实际不跑 uvicorn, 用 patch 拦
        data="./data/raw",
        index="./data/index",
        no_ingest=True,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_cmd_up_injects_llm_and_embedder_before_uvicorn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAQ-51: _cmd_up 在 uvicorn.run() 之前必须把真 client/embedder 注入.

    验证手段: patch uvicorn.run 让它什么都不做, 然后检查模块级单例.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MIMAX_API_KEY", "test-key")
    monkeypatch.setenv("ZHIPU_API_KEY", "test-key")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")  # 阻断 find_dotenv 向上找 .env
    (tmp_path / ".env").write_text("", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "generate:\n"
        "  llm: {provider: minimax, model: MiniMax-M3, "
        "base_url: https://api.MiniMax.chat/v1/, api_key_env: MIMAX_API_KEY}\n"
        "  embedding: {provider: zhipu, model: embedding-3, "
        "base_url: https://open.bigmodel.cn/api/paas/v4/, api_key_env: ZHIPU_API_KEY}\n",
        encoding="utf-8",
    )
    from rag_demo.config import _reset_config_cache
    _reset_config_cache()

    # 重置模块级单例
    from rag_demo.generate import set_llm_client
    from rag_demo.retrieve import set_embedder
    set_llm_client(None)
    set_embedder(None)

    # 拦 uvicorn.run — 阻止它真起 server
    captured: dict = {}

    def fake_uvicorn_run(*args, **kwargs) -> None:
        captured["called"] = True

    with patch("uvicorn.run", side_effect=fake_uvicorn_run):
        from rag_demo.__main__ import _cmd_up
        rc = _cmd_up(_make_args())
    assert rc == 0
    assert captured.get("called") is True

    # 注入必须在 uvicorn.run 之前完成 (单例被填充)
    from rag_demo.generate import get_llm_client
    from rag_demo.retrieve import get_embedder
    assert get_llm_client() is not None
    assert get_embedder() is not None

    # 清理
    set_llm_client(None)
    set_embedder(None)


def test_cmd_up_does_not_crash_when_keys_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAQ-51: 缺 api_key 时 _cmd_up 不抛错 — 打印 warning, uvicorn 仍能起."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")  # 阻断 find_dotenv 向上找 .env
    (tmp_path / ".env").write_text("", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        "generate:\n"
        "  llm: {provider: minimax, model: MiniMax-M3, "
        "base_url: https://api.MiniMax.chat/v1/, api_key_env: MIMAX_API_KEY}\n"
        "  embedding: {provider: zhipu, model: embedding-3, "
        "base_url: https://open.bigmodel.cn/api/paas/v4/, api_key_env: ZHIPU_API_KEY}\n",
        encoding="utf-8",
    )
    from rag_demo.config import _reset_config_cache
    _reset_config_cache()

    from rag_demo.generate import set_llm_client
    from rag_demo.retrieve import set_embedder
    set_llm_client(None)
    set_embedder(None)

    with patch("uvicorn.run") as mock_run:
        from rag_demo.__main__ import _cmd_up
        rc = _cmd_up(_make_args())
    assert rc == 0
    assert mock_run.called

    # 缺 key 时单例留空
    from rag_demo.generate import get_llm_client
    from rag_demo.retrieve import get_embedder
    assert get_llm_client() is None
    assert get_embedder() is None

    set_llm_client(None)
    set_embedder(None)

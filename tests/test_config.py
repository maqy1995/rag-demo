"""Tests for `config` module (design §6.1).

覆盖:
  - 缺 config.yaml -> 内置默认
  - 存在 config.yaml -> 覆盖默认
  - 存在 config.example.yaml 但无 config.yaml -> 用 example
  - yaml 解析失败 -> AppError CONFIG_LOAD_FAIL
  - vault.path 缺省 -> "" (触发冷启动 demo 路径)
  - 显式 path 参数
  - effective() 脱敏 (不含 secret)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_demo.config import AppConfig, load_config
from rag_demo.errors import AppError

# ── 缺 config 文件 -> 默认 ───────────────────────────────────


def test_load_default_when_no_config_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    # 内置默认
    assert cfg.chunk_size == 500
    assert cfg.chunk_overlap == 80
    assert cfg.top_k == 5
    assert cfg.web_port == 8000
    # vault.path 默认空 -> 触发冷启动 demo
    assert cfg.vault_path == ""


# ── 存在 config.yaml -> 覆盖默认 ─────────────────────────────


def test_config_yaml_overrides_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "vault:\n  path: /tmp/my-vault\n  name: prod-notes\n"
        "ingest:\n  chunk_size: 1000\n  chunk_overlap: 100\n"
        "web:\n  port: 9000\n",
        encoding="utf-8",
    )
    cfg = load_config()
    assert cfg.vault_path == "/tmp/my-vault"
    assert cfg.vault_name == "prod-notes"
    assert cfg.chunk_size == 1000
    assert cfg.chunk_overlap == 100
    # 未覆盖的字段保持默认
    assert cfg.top_k == 5
    assert cfg.web_port == 9000


# ── 仅 example -> 用 example ────────────────────────────────


def test_config_example_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.example.yaml").write_text(
        "ingest:\n  chunk_size: 800\n",
        encoding="utf-8",
    )
    cfg = load_config()
    assert cfg.chunk_size == 800


# ── yaml 解析失败 -> AppError ───────────────────────────────


def test_yaml_parse_error_raises_config_load_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "vault:\n  path: [unclosed bracket",
        encoding="utf-8",
    )
    with pytest.raises(AppError) as excinfo:
        load_config()
    assert excinfo.value.code == "CONFIG_LOAD_FAIL"
    assert excinfo.value.http_status == 500


# ── 顶层不是 mapping -> AppError ─────────────────────────────


def test_yaml_top_level_not_mapping_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(AppError) as excinfo:
        load_config()
    assert excinfo.value.code == "CONFIG_LOAD_FAIL"


# ── 显式 path 参数 ─────────────────────────────────────────


def test_explicit_path_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.yaml"
    custom.write_text("ingest:\n  chunk_size: 200\n", encoding="utf-8")
    cfg = load_config(path=custom)
    assert cfg.chunk_size == 200


# ── effective() 脱敏 ───────────────────────────────────────


def test_effective_does_not_contain_secrets() -> None:
    """effective() 是 /api/config 的响应体, 必须不含 API key."""
    cfg = load_config()
    text = json.dumps(cfg.effective(), ensure_ascii=False)
    for forbidden in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_API_KEY", "sk-"):
        assert forbidden not in text, f"effective() leaks {forbidden!r}"


def test_effective_includes_all_sections() -> None:
    cfg = load_config()
    body = cfg.effective()
    for section in ("vault", "ingest", "retrieve", "generate", "web", "usage"):
        assert section in body
    # generate 嵌套 llm / embedding
    assert "llm" in body["generate"]
    assert "embedding" in body["generate"]

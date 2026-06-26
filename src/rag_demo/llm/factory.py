"""LLM / Embedder factory: from `AppConfig` 构造真实 client.

ADR-0003 落地: provider 切换是 config 层面 (api_key_env / base_url / model) 三元组.
本模块负责:
  - `os.environ[cfg.llm_api_key_env]` 取 key, 缺时抛 AppError(401, GENERATE_LLM_FAIL)
  - 用 `LLMConfig` / `EmbedConfig` 构造 `OpenAICompatibleClient` / `OpenAICompatibleEmbedder`
  - 不做 if/else 分支 (per ADR-0001 §"单类多 provider")

CLI / web 启动时调 `build_llm_client(cfg)` / `build_embedder(cfg)` 拿到实例,
再 `generate.set_llm_client(client)` + `retrieve.set_embedder(emb)` 注入到业务模块.
"""
from __future__ import annotations

import os

from ..config import AppConfig
from ..errors import AppError
from .base import BaseEmbedder, BaseLlmClient, EmbedConfig, LLMConfig
from .openai_compat import OpenAICompatibleClient, OpenAICompatibleEmbedder


def _require_env(name: str) -> str:
    """读 .env 注入后的 os.environ, 缺时抛 AppError(401, ...).

    与 base.py::_require_api_key 行为一致: key 缺失 = 401 (per ADR-0003 默认).
    """
    val = os.environ.get(name)
    if not val:
        raise AppError(
            code="GENERATE_LLM_FAIL",
            stage="generate",
            http_status=401,
            message=(
                f"缺少 {name}; 请在 .env 里填入, 或换 config.yaml::generate."
                f"{{llm,embedding}}.provider 到已配 key 的 provider"
            ),
        )
    return val


def build_llm_client(cfg: AppConfig) -> BaseLlmClient:
    """从 AppConfig 构造真 LLM client. 不发请求, 仅做 config 校验 + 实例化."""
    api_key = _require_env(cfg.llm_api_key_env)
    return OpenAICompatibleClient(
        LLMConfig(
            provider=cfg.llm_provider,
            model=cfg.llm_model,
            base_url=cfg.llm_base_url,
            api_key=api_key,
            timeout_s=cfg.llm_timeout_s,
            max_retries=cfg.llm_max_retries,
        )
    )


def build_embedder(cfg: AppConfig) -> BaseEmbedder:
    """从 AppConfig 构造真 Embedder. 不发请求, 仅做 config 校验 + 实例化."""
    api_key = _require_env(cfg.embedding_api_key_env)
    return OpenAICompatibleEmbedder(
        EmbedConfig(
            provider=cfg.embedding_provider,
            model=cfg.embedding_model,
            base_url=cfg.embedding_base_url,
            api_key=api_key,
            timeout_s=cfg.embedding_timeout_s,
            batch_size=cfg.embedding_batch_size,
        )
    )

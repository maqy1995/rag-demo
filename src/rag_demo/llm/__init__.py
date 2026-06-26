"""LLM 抽象与实现 (ADR-0001).

本子包是 L3 → L2 的 LLM 边界:
  - `base`     定义 provider-agnostic 的抽象基类 + 配置 dataclass
  - `openai_compat` 用 OpenAI 兼容 SDK (`openai>=1.30`) 实现的 stub

业务侧只 import 本子包的公开名字, 不直接 import `openai` 包 —
便于单元测试 mock, 也便于未来添加非 OpenAI 兼容 provider 时只增不替换.

公开 API:
  BaseLlmClient, BaseEmbedder, LLMConfig, EmbedConfig, OpenAICompatibleClient,
  OpenAICompatibleEmbedder, VALID_LLM_PROVIDERS
"""

from __future__ import annotations

from .base import (
    VALID_LLM_PROVIDERS,
    BaseEmbedder,
    BaseLlmClient,
    EmbedConfig,
    LLMConfig,
)
from .factory import build_embedder, build_llm_client
from .openai_compat import OpenAICompatibleClient, OpenAICompatibleEmbedder

__all__ = [
    "VALID_LLM_PROVIDERS",
    "BaseEmbedder",
    "BaseLlmClient",
    "EmbedConfig",
    "LLMConfig",
    "OpenAICompatibleClient",
    "OpenAICompatibleEmbedder",
    "build_embedder",
    "build_llm_client",
]

"""LLM / Embedder 抽象基类 (ADR-0001 §"接口签名").

本模块只定义 provider-agnostic 的接口契约 + 参数校验, **不**依赖任何具体
provider SDK. 业务侧 (generate.answer / ingest) 只通过本基类签名调用, 这样:

  1. 单元测试可以 mock `OpenAICompatibleClient.stream` 而不必真发请求;
  2. 未来添加非 OpenAI 兼容 provider (Anthropic / Google 等) 时, 只需
     新增 adapter 实现本基类, 不动业务侧.

新增 provider 须走 ADR-0003 (MAQ-28), 不在本模块里加 if/else 分支.

约束:
  - `BaseLlmClient.stream(...)` 是 iterator 形态, 每个 yield 一个 token 片段
    字符串 (SSE `event: token.data.delta` 帧的 payload);
  - `BaseEmbedder.embed(texts) -> list[list[float]]`, 顺序与 texts 一一对应;
  - `LLMConfig` / `EmbedConfig` 都是 frozen dataclass, 一旦构造不可改;
  - 构造时即校验参数 (fail-fast), 不延迟到调用时.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..retrieve import Hit  # noqa: F401  -- 仅类型, 避免循环 import

# ADR-0001 §"接口签名": 4 家 OpenAI 兼容 provider (锁死, 新增须走 ADR-0003).
# 与 owner 拍板 (MAQ-25 评论 d560c6ca-…) 一致: OpenAI / 智谱 / MiniMax / 小米 Mimo.
VALID_LLM_PROVIDERS: frozenset[str] = frozenset({"openai", "zhipu", "minimax", "mimo"})


# ── 参数校验辅助 (BaseLlmClient / BaseEmbedder 共享) ──────────────


def _require_nonempty_str(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be non-empty str, got {value!r}")


def _require_provider(provider: object) -> None:
    _require_nonempty_str(provider, "provider")
    # type narrow after the check
    assert isinstance(provider, str)
    if provider not in VALID_LLM_PROVIDERS:
        raise ValueError(
            f"unknown provider {provider!r}; valid: {sorted(VALID_LLM_PROVIDERS)}"
        )


def _require_base_url(base_url: object) -> None:
    _require_nonempty_str(base_url, "base_url")
    assert isinstance(base_url, str)
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        raise ValueError(
            f"base_url must start with http:// or https://, got {base_url!r}"
        )


def _require_api_key(api_key: object) -> None:
    _require_nonempty_str(api_key, "api_key")


def _require_positive_number(value: object, field: str) -> None:
    # bool 是 int 的子类, 显式拒绝 bool
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be int/float, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{field} must be > 0, got {value!r}")


def _require_nonnegative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{field} must be >= 0, got {value!r}")


def _require_positive_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be int, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{field} must be > 0, got {value!r}")


# ── 配置 dataclass ───────────────────────────────────────


@dataclass(frozen=True)
class LLMConfig:
    """LLM client configuration.

    Attributes:
        provider: One of `VALID_LLM_PROVIDERS` (ADR-0001 锁定的 4 家).
        model: 模型名, 由 provider 决定 (e.g. "gpt-4o-mini", "glm-4-flash").
        base_url: OpenAI 兼容端点 (e.g. "https://api.openai.com/v1").
        api_key: 来自 .env 注入 (`OPENAI_API_KEY` / `ZHIPU_API_KEY` / ...).
        timeout_s: 单次请求超时秒数; 必须 > 0.
        max_retries: 429 / 5xx 时最大重试次数; 必须 >= 0 (0 = 不重试).
    """

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_s: float = 30.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        _require_provider(self.provider)
        _require_nonempty_str(self.model, "model")
        _require_base_url(self.base_url)
        _require_api_key(self.api_key)
        _require_positive_number(self.timeout_s, "timeout_s")
        _require_nonnegative_int(self.max_retries, "max_retries")


@dataclass(frozen=True)
class EmbedConfig:
    """Embedder configuration. LLM / Embedder provider 解耦 (owner 拍板)."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_s: float = 30.0
    batch_size: int = 64

    def __post_init__(self) -> None:
        _require_provider(self.provider)
        _require_nonempty_str(self.model, "model")
        _require_base_url(self.base_url)
        _require_api_key(self.api_key)
        _require_positive_number(self.timeout_s, "timeout_s")
        _require_positive_int(self.batch_size, "batch_size")


# ── 抽象基类 ────────────────────────────────────────────


class BaseLlmClient:
    """LLM client 抽象基类.

    子类实现 `stream(question, hits)`, 业务侧只通过本类签名调用, 不直接
    持有 provider SDK 句柄 (e.g. `openai.OpenAI`). 便于 stub 注入和未来扩展.
    """

    def __init__(self, config: LLMConfig) -> None:
        if not isinstance(config, LLMConfig):
            raise TypeError(
                f"config must be LLMConfig, got {type(config).__name__}"
            )
        self._config = config

    @property
    def config(self) -> LLMConfig:
        return self._config

    def stream(self, question: str, hits: list[Hit]) -> Iterator[str]:
        """流式生成 — 每段 yield 一个 token 片段 (SSE `event: token.data.delta`)."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement stream(question, hits)"
        )

    def complete(self, question: str, hits: list[Hit]) -> str:
        """便捷方法 — 收集 `stream()` 全部 token 拼成完整字符串.

        不在业务关键路径上 — 主要给单元测试和非流式 CLI 场景用.
        """
        return "".join(self.stream(question, hits))


class BaseEmbedder:
    """Embedder 抽象基类."""

    def __init__(self, config: EmbedConfig) -> None:
        if not isinstance(config, EmbedConfig):
            raise TypeError(
                f"config must be EmbedConfig, got {type(config).__name__}"
            )
        self._config = config

    @property
    def config(self) -> EmbedConfig:
        return self._config

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embed — 返回与 texts 等长的向量列表."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement embed(texts)"
        )

    def embed_one(self, text: str) -> list[float]:
        """单条便捷方法 — 内部转 `embed([text])[0]`."""
        return self.embed([text])[0]

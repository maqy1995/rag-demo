"""OpenAI 兼容 SDK 实现 (ADR-0001 §"openai_compat.py 关键设计").

**单类多 provider**: `OpenAICompatibleClient(LLMConfig)` 构造时
`self._client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)` —
4 家都用 `openai.OpenAI`, 差异**仅在 config**. 这意味着 provider 切换是
config 层面的三元组 (base_url + api_key + model) 切换, 不需要在代码里写
4 套 adapter.

错误映射 (设计 §5 + §6.3 + ADR-0001 §"openai_compat.py 关键设计"):
  - 401 / 403            → AppError GENERATE_LLM_FAIL (http_status=e.status_code)
  - 429 / 5xx            → 默认按 retry 策略重试; 耗尽后 → AppError GENERATE_LLM_FAIL
  - 其他 APIStatusError  → AppError GENERATE_LLM_FAIL (http_status=502)
  - APIConnectionError   → AppError GENERATE_LLM_FAIL (http_status=503)
  - Embedder 错误        → AppError EMBEDDING_FAIL (http_status=e.status_code or 503)

不引入 LangSmith / Langfuse 之类的可观测中间件 (与 design §8.3 一致).

stub 阶段 (`MAX_RETRIES=0` 或没有真实 API key): 单次失败即抛 AppError,
测试用 `unittest.mock.patch("openai.OpenAI")` mock 父 SDK 不真发请求.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import NoReturn

import openai

from ..errors import AppError, raise_error
from ..retrieve import Hit
from .base import BaseEmbedder, BaseLlmClient, EmbedConfig, LLMConfig

# 触发自动重试的 HTTP status. 401/403 不重试 (key 错重试也没用).
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# 退避基数 (秒). 测试场景里会被 monkeypatch 到 0.001, 真实场景默认 0.5s.
_BACKOFF_BASE_S: float = 0.5


def _to_app_error(err: openai.APIStatusError) -> AppError:
    """按 HTTP status 把 openai 异常映射成 AppError. 总是 raise, 不返回."""
    status = int(err.status_code) if err.status_code is not None else 500
    if 400 <= status < 500 and status not in _RETRYABLE_STATUSES:
        # 401/403/4xx — 一次性错误, 透传 status
        return AppError(
            code="GENERATE_LLM_FAIL",
            stage="generate",
            http_status=status,
            message=f"LLM 调用失败 ({status}): {err}",
        )
    # 5xx 或 429 (耗尽重试后) — 透传 status
    if 500 <= status < 600 or status == 429:
        return AppError(
            code="GENERATE_LLM_FAIL",
            stage="generate",
            http_status=status,
            message=f"LLM 调用失败 ({status}): {err}",
        )
    # 其他 status (e.g. 1xx/3xx 不会到这里; 兜底为 502)
    return AppError(
        code="GENERATE_LLM_FAIL",
        stage="generate",
        http_status=502,
        message=f"LLM 调用失败 (unexpected {status}): {err}",
    )


def _sleep_backoff(attempt: int) -> None:
    """线性退避. 测试可 monkeypatch `_BACKOFF_BASE_S = 0` 跳过等待."""
    time.sleep(_BACKOFF_BASE_S * (attempt + 1))


# ── LLM client ──────────────────────────────────────────


class OpenAICompatibleClient(BaseLlmClient):
    """单类覆盖 4 家 provider (openai / zhipu / MiniMax / mimo).

    业务侧只 import 本类, 不直接 import `openai`. 测试通过
    `unittest.mock.patch("openai.OpenAI")` mock 父 SDK.
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        # 懒加载 — 测试 patch("openai.OpenAI") 时, 这里拿到的就是 mock 实例
        self._sdk: openai.OpenAI | None = None

    def _client(self) -> openai.OpenAI:
        if self._sdk is None:
            self._sdk = openai.OpenAI(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                timeout=self._config.timeout_s,
                max_retries=0,  # 我们自己控制 retry 策略
            )
        return self._sdk

    def _build_messages(self, question: str, hits: list[Hit]) -> list[dict]:
        """拼 prompt messages — stub 阶段简单拼接, 不做 prompt engineering.

        不动 design §3.5 决策链 (硬编码早返, 不依赖 LLM 行为).
        真实 prompt 模板待 MAQ-31 真接 provider 时落地.
        """
        ctx_lines = [f"[{i + 1}] {h.snippet}" for i, h in enumerate(hits)]
        system = (
            "You are a knowledge-base QA assistant. "
            "Answer the question based on the given notes. "
            "Cite source numbers in [brackets]."
        )
        user = (
            f"Question: {question}\n\nNotes:\n"
            + ("\n".join(ctx_lines) if ctx_lines else "(no notes)")
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def stream(self, question: str, hits: list[Hit]) -> Iterator[str]:
        """流式生成 — 每段 yield 一个 token 片段 (SSE `event: token.data.delta`).

        重试策略: 429 / 5xx 按 `config.max_retries` 重试 (线性退避);
        401 / 403 / 其他 4xx 不重试, 直接抛 AppError.
        """
        messages = self._build_messages(question, hits)
        max_attempts = self._config.max_retries + 1
        last_err: openai.APIStatusError | None = None

        for attempt in range(max_attempts):
            try:
                chunks = self._client().chat.completions.create(
                    model=self._config.model,
                    messages=messages,
                    stream=True,
                )
                for chunk in chunks:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    piece = getattr(delta, "content", None)
                    if piece:
                        yield piece
                return
            except openai.APIStatusError as e:
                last_err = e
                status = int(e.status_code) if e.status_code is not None else 0
                if status in _RETRYABLE_STATUSES and attempt + 1 < max_attempts:
                    _sleep_backoff(attempt)
                    continue
                raise _to_app_error(e) from e
            except openai.APIConnectionError as e:
                raise AppError(
                    code="GENERATE_LLM_FAIL",
                    stage="generate",
                    http_status=503,
                    message=f"LLM 连接失败: {e}",
                ) from e

        # 走到这里说明重试用尽 + 最后一次是 retryable — 显式抛一次
        assert last_err is not None  # 仅供 type checker
        raise _to_app_error(last_err) from last_err


# ── Embedder ────────────────────────────────────────────


class OpenAICompatibleEmbedder(BaseEmbedder):
    """OpenAI 兼容 embedder — 用 `client.embeddings.create(input=, model=)`."""

    def __init__(self, config: EmbedConfig) -> None:
        super().__init__(config)
        self._sdk: openai.OpenAI | None = None

    def _client(self) -> openai.OpenAI:
        if self._sdk is None:
            self._sdk = openai.OpenAI(
                base_url=self._config.base_url,
                api_key=self._config.api_key,
                timeout=self._config.timeout_s,
                max_retries=0,
            )
        return self._sdk

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embed. texts 为空时返回空 list (不调 SDK).

        当 `len(texts) > config.batch_size` 时按 batch 切分调用, 拼回顺序结果.
        错误映射: 401/403/429/5xx → AppError EMBEDDING_FAIL.
        """
        if not texts:
            return []
        out: list[list[float]] = []
        batch_size = self._config.batch_size
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            try:
                resp = self._client().embeddings.create(
                    model=self._config.model,
                    input=batch,
                )
            except openai.APIStatusError as e:
                status = int(e.status_code) if e.status_code is not None else 503
                raise AppError(
                    code="EMBEDDING_FAIL",
                    stage="ingest",
                    http_status=status if 400 <= status < 600 else 503,
                    message=f"embedding 调用失败 ({status}): {e}",
                ) from e
            except openai.APIConnectionError as e:
                raise AppError(
                    code="EMBEDDING_FAIL",
                    stage="ingest",
                    http_status=503,
                    message=f"embedding 连接失败: {e}",
                ) from e
            # resp.data 顺序与 input 一一对应 — 按 index 排序确保稳定
            data_sorted = sorted(resp.data, key=lambda d: d.index)
            out.extend([list(d.embedding) for d in data_sorted])
        return out


# ── 模块级 raise helpers (供需要 raise_error 的地方复用) ──────


def raise_llm_http_error(status: int) -> NoReturn:
    """外部 (e.g. web 端点) 拿到 HTTP status 后构造 AppError 抛出."""
    raise_error("GENERATE_LLM_FAIL", stage="generate", http_status=status)


def raise_embedding_http_error(status: int) -> NoReturn:
    """外部 (e.g. ingest 端点) 拿到 HTTP status 后构造 AppError 抛出."""
    raise_error("EMBEDDING_FAIL", stage="ingest", http_status=status)

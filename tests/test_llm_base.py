"""Tests for `rag_demo.llm` (ADR-0001).

覆盖 (≥ 5 断言):
  1. 接口契约 — LLMConfig / EmbedConfig 字段 + 4 家 provider 都能构造 client
  2. 参数校验 — provider / api_key / base_url / timeout_s / max_retries 非合法值 → ValueError
  3. stream 行为 — mock `openai.OpenAI`, 验证 chunk.delta.content 顺序 yield
  4. 重试行为 — 429 / 5xx 按 max_retries 重试, 耗尽后抛 AppError
  5. 错误映射 — 401 / 403 / 5xx → AppError(http_status=对应, code=GENERATE_LLM_FAIL)
  6. Embedder — embed_one 委托 embed([text])[0]; empty texts 不调 SDK; batch 切分

约定: 所有 openai 调用都用 `mock.patch("openai.OpenAI")` 拦截, 不真发请求.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest

from rag_demo.errors import AppError
from rag_demo.llm import (
    VALID_LLM_PROVIDERS,
    BaseEmbedder,
    BaseLlmClient,
    EmbedConfig,
    LLMConfig,
    OpenAICompatibleClient,
    OpenAICompatibleEmbedder,
)
from rag_demo.llm import openai_compat as llm_openai_compat
from rag_demo.retrieve import Hit

# ── helpers ──────────────────────────────────────────────


def _hit(snippet: str = "stub snippet") -> Hit:
    return Hit(
        source="vault://x/a.md#h",
        file="a.md",
        heading="h",
        chunk_id=1,
        snippet=snippet,
        score=0.5,
    )


def _delta_chunk(content: str | None) -> Any:
    """构造一个像 openai SDK 返回的 stream chunk."""
    choice = MagicMock()
    choice.delta.content = content
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _api_error(status: int, message: str = "boom") -> openai.APIStatusError:
    """构造 openai APIStatusError — 兼容 openai>=1.30 的 (message, *, response, body) 签名."""
    req = httpx.Request("POST", "https://example.invalid")
    resp = httpx.Response(status, request=req)
    return openai.APIStatusError(message, response=resp, body=None)


def _conn_error() -> openai.APIConnectionError:
    """构造 openai APIConnectionError (request=httpx.Request)."""
    req = httpx.Request("POST", "https://example.invalid")
    return openai.APIConnectionError(request=req)


# ── 1. 接口契约 + 4 provider 构造 ───────────────────────────


def test_llm_config_default_values() -> None:
    """LLMConfig 默认值与 ADR §接口签名一致 (timeout_s=30.0, max_retries=2)."""
    cfg = LLMConfig(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
    )
    assert cfg.timeout_s == 30.0
    assert cfg.max_retries == 2
    assert cfg.provider == "openai"


@pytest.mark.parametrize(
    ("provider", "base_url"),
    [
        ("openai", "https://api.openai.com/v1"),
        ("zhipu", "https://open.bigmodel.cn/api/paas/v4"),
        ("minimax", "https://api.minimax.chat/v1"),
        ("mimo", "https://api.xiaomi.com/mimo/v1"),
    ],
)
def test_4_providers_construct_client_with_correct_base_url(
    provider: str, base_url: str
) -> None:
    """4 家 OpenAI 兼容 provider 都能用对应 base_url 构造 OpenAICompatibleClient."""
    with patch("openai.OpenAI") as mock_openai:
        cfg = LLMConfig(
            provider=provider,
            model="any",
            base_url=base_url,
            api_key="k",
        )
        client = OpenAICompatibleClient(cfg)
        # 触发 _client() 懒加载 — 验证 base_url / api_key 传给 openai.OpenAI
        client._client()  # type: ignore[attr-defined]
    assert mock_openai.call_args.kwargs["base_url"] == base_url
    assert mock_openai.call_args.kwargs["api_key"] == "k"
    assert client.config.provider == provider


def test_valid_providers_frozenset_lists_all_4() -> None:
    """VALID_LLM_PROVIDERS 锁死 4 家 — 不允许业务侧绕过添加."""
    assert VALID_LLM_PROVIDERS == frozenset({"openai", "zhipu", "minimax", "mimo"})


# ── 2. 参数校验 ──────────────────────────────────────────


def test_llm_config_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        LLMConfig(provider="anthropic", model="m", base_url="https://x", api_key="k")


def test_llm_config_rejects_empty_api_key() -> None:
    with pytest.raises(ValueError, match="api_key must be non-empty"):
        LLMConfig(provider="openai", model="m", base_url="https://x", api_key="")


def test_llm_config_rejects_invalid_base_url_scheme() -> None:
    with pytest.raises(ValueError, match="http"):
        LLMConfig(provider="openai", model="m", base_url="ftp://x", api_key="k")


def test_llm_config_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        LLMConfig(
            provider="openai", model="m", base_url="https://x", api_key="k", timeout_s=0
        )


def test_llm_config_rejects_negative_max_retries() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        LLMConfig(
            provider="openai", model="m", base_url="https://x", api_key="k", max_retries=-1
        )


def test_base_llm_client_rejects_non_config() -> None:
    """基类 __init__ 显式拒绝非 LLMConfig (避免子类意外传错)."""
    with pytest.raises(TypeError, match="LLMConfig"):
        BaseLlmClient("not a config")  # type: ignore[arg-type]


# ── 3. stream 行为 ──────────────────────────────────────


def test_stream_yields_delta_content_in_order() -> None:
    """stream() 按 chunk 顺序 yield delta.content; None / 空字符串跳过."""
    chunks = [
        _delta_chunk("你"),
        _delta_chunk("好"),
        _delta_chunk(None),  # 应跳过
        _delta_chunk("，"),
        _delta_chunk(""),
        _delta_chunk("世界"),
    ]
    mock_create = MagicMock(return_value=iter(chunks))

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="gpt-4o-mini",
                base_url="https://api.openai.com/v1", api_key="sk",
                max_retries=0,
            )
        )
        out = list(client.stream("Q?", [_hit()]))

    assert out == ["你", "好", "，", "世界"]
    # 确认调过 SDK, 且传了正确 model + messages + stream=True
    assert mock_create.call_args.kwargs["model"] == "gpt-4o-mini"
    assert mock_create.call_args.kwargs["stream"] is True
    msgs = mock_create.call_args.kwargs["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Q?" in msgs[1]["content"]
    assert "stub snippet" in msgs[1]["content"]


# ── 4. 重试 + 错误映射 ────────────────────────────────────


def test_stream_401_maps_to_app_error_with_401_no_retry() -> None:
    """401 不重试 — 一次性错误直接抛 AppError(http_status=401)."""
    mock_create = MagicMock(side_effect=_api_error(401, "bad key"))

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k",
                max_retries=3,  # 即便设了重试, 401 也不重试
            )
        )
        with pytest.raises(AppError) as ei:
            list(client.stream("Q", [_hit()]))

    err = ei.value
    assert err.code == "GENERATE_LLM_FAIL"
    assert err.stage == "generate"
    assert err.http_status == 401
    # 401 不重试 → 只调 1 次
    assert mock_create.call_count == 1


def test_stream_5xx_maps_to_app_error_with_5xx_no_retry_when_max_retries_0() -> None:
    """5xx 在 max_retries=0 时不重试, 直接抛 AppError(http_status=5xx)."""
    mock_create = MagicMock(side_effect=_api_error(503, "service down"))

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k",
                max_retries=0,
            )
        )
        with pytest.raises(AppError) as ei:
            list(client.stream("Q", [_hit()]))

    assert ei.value.http_status == 503
    assert mock_create.call_count == 1


def test_stream_429_retries_then_raises_app_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 在 max_retries=2 时重试 2 次后抛 AppError(http_status=429).

    第 1 次 → 429 (重试)
    第 2 次 → 429 (重试)
    第 3 次 → 429 (耗尽, 抛 AppError)
    """
    # 跳过 backoff 等待, 加速测试
    monkeypatch.setattr(llm_openai_compat, "_BACKOFF_BASE_S", 0.0)

    mock_create = MagicMock(side_effect=_api_error(429, "rate limited"))

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k",
                max_retries=2,
            )
        )
        with pytest.raises(AppError) as ei:
            list(client.stream("Q", [_hit()]))

    assert ei.value.code == "GENERATE_LLM_FAIL"
    assert ei.value.http_status == 429
    # max_retries=2 → 总尝试 3 次 (1 初次 + 2 重试)
    assert mock_create.call_count == 3


def test_stream_429_recovers_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 一次后恢复 → 不抛错, 正常 yield tokens."""
    monkeypatch.setattr(llm_openai_compat, "_BACKOFF_BASE_S", 0.0)

    side_effects = [
        _api_error(429, "rate limited"),
        iter([_delta_chunk("OK")]),
    ]
    mock_create = MagicMock(side_effect=side_effects)

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k",
                max_retries=2,
            )
        )
        out = list(client.stream("Q", [_hit()]))

    assert out == ["OK"]
    assert mock_create.call_count == 2


def test_stream_connection_error_maps_to_503() -> None:
    """APIConnectionError → AppError(http_status=503)."""
    mock_create = MagicMock(side_effect=_conn_error())

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create = mock_create
        client = OpenAICompatibleClient(
            LLMConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k", max_retries=0,
            )
        )
        with pytest.raises(AppError) as ei:
            list(client.stream("Q", [_hit()]))

    assert ei.value.http_status == 503


# ── 5. Embedder 行为 ─────────────────────────────────────


def test_embed_one_delegates_to_embed_singleton() -> None:
    """embed_one 调用 embed([text])[0] — 单条便捷方法."""
    fake_vec = [0.1, 0.2, 0.3]
    embedder = OpenAICompatibleEmbedder(
        EmbedConfig(
            provider="openai", model="text-embedding-3-small",
            base_url="https://x", api_key="k", batch_size=64,
        )
    )
    # 直接 mock embed() 方法 — 避免 mock 整个 SDK
    with patch.object(embedder, "embed", return_value=[fake_vec]) as mock_embed:
        out = embedder.embed_one("hello")

    assert out == fake_vec
    mock_embed.assert_called_once_with(["hello"])


def test_embed_returns_empty_list_for_empty_input_without_calling_sdk() -> None:
    """空 texts 直接返回 [], 不调 SDK."""
    with patch("openai.OpenAI") as mock_openai:
        embedder = OpenAICompatibleEmbedder(
            EmbedConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k", batch_size=64,
            )
        )
        out = embedder.embed([])

    assert out == []
    # SDK 一次都不该被构造
    mock_openai.assert_not_called()


def test_embed_splits_batches_when_over_batch_size() -> None:
    """texts 超过 batch_size 时按 batch 切分调用, 拼回顺序结果."""
    batch_size = 2
    # 5 条文本 → 3 个 batch (2 + 2 + 1)

    def fake_embed_resp(vectors: list[list[float]]) -> Any:
        resp = MagicMock()
        resp.data = [
            MagicMock(index=i, embedding=v) for i, v in enumerate(vectors)
        ]
        return resp

    resp_seq = [
        fake_embed_resp([[1.0, 1.0], [2.0, 2.0]]),
        fake_embed_resp([[3.0, 3.0], [4.0, 4.0]]),
        fake_embed_resp([[5.0, 5.0]]),
    ]
    mock_create = MagicMock(side_effect=resp_seq)

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.embeddings.create = mock_create
        embedder = OpenAICompatibleEmbedder(
            EmbedConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k", batch_size=batch_size,
            )
        )
        out = embedder.embed(["a", "b", "c", "d", "e"])

    # 顺序与输入一一对应
    assert out == [
        [1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0], [5.0, 5.0],
    ]
    # 3 次调用
    assert mock_create.call_count == 3
    # 每次 input 都是 batch_size 或余数
    assert mock_create.call_args_list[0].kwargs["input"] == ["a", "b"]
    assert mock_create.call_args_list[1].kwargs["input"] == ["c", "d"]
    assert mock_create.call_args_list[2].kwargs["input"] == ["e"]


def test_embed_api_error_maps_to_embedding_fail() -> None:
    """embed 401 → AppError(code=EMBEDDING_FAIL, http_status=401)."""
    mock_create = MagicMock(side_effect=_api_error(401, "bad key"))

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.embeddings.create = mock_create
        embedder = OpenAICompatibleEmbedder(
            EmbedConfig(
                provider="openai", model="m",
                base_url="https://x", api_key="k", batch_size=64,
            )
        )
        with pytest.raises(AppError) as ei:
            embedder.embed(["a", "b"])

    assert ei.value.code == "EMBEDDING_FAIL"
    assert ei.value.stage == "ingest"
    assert ei.value.http_status == 401


# ── 6. 基类默认 raise NotImplementedError ──────────────────


def test_base_llm_client_stream_raises_not_implemented() -> None:
    """基类 BaseLlmClient.stream 默认 raise NotImplementedError."""

    class _Stub(BaseLlmClient):
        pass

    s = _Stub(
        LLMConfig(provider="openai", model="m", base_url="https://x", api_key="k")
    )
    with pytest.raises(NotImplementedError):
        list(s.stream("Q", [_hit()]))


def test_base_embedder_embed_raises_not_implemented() -> None:
    """基类 BaseEmbedder.embed 默认 raise NotImplementedError."""

    class _Stub(BaseEmbedder):
        pass

    s = _Stub(
        EmbedConfig(provider="openai", model="m", base_url="https://x", api_key="k")
    )
    with pytest.raises(NotImplementedError):
        s.embed(["x"])

"""Tests for `generate.answer` decision chain (design §3.5 / §9.2).

三条确定性断言 (设计 §9.2 工程纪律 — 显式 raise 不是隐式表达):
  1. test_us4_empty_hits    — hits=[] → RETRIEVE_EMPTY; LLM **未**被调用.
  2. test_us6_no_definition — defined_checker=False → NOT_DEFINED; LLM **未**被调用.
  3. test_happy_path        — defined_checker=True + LLM mock → GENERATED; LLM 被调一次.

`_call_llm` 是 generate.py 暴露的模块级 LLM 入口 (MAQ-11 引入),
测试用 unittest.mock.patch 拦截, `unreachable_llm` 显式 AssertionError
确保 LLM 一旦被错误调用就测试失败 (不能靠"不写 LLM mock" 隐式表达).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag_demo.generate import answer
from rag_demo.retrieve import Hit


def _hit(snippet: str, heading: str = "any") -> Hit:
    return Hit(
        source="vault://x/a.md#any",
        file="a.md",
        heading=heading,
        chunk_id=1,
        snippet=snippet,
        score=0.5,
    )


# ── US4: empty hits → RETRIEVE_EMPTY, LLM NOT called ───────


def test_us4_empty_hits() -> None:
    """design §3.5 决策 1: hits 为空 → 早返, LLM 不被调用."""
    unreachable_llm = MagicMock(
        side_effect=AssertionError("LLM must not be called on US4 path")
    )
    with patch("rag_demo.generate._call_llm", unreachable_llm):
        result = answer("X", [])

    # 决策字段
    assert result.decision == "RETRIEVE_EMPTY"
    assert result.sources == []
    assert result.answer == "未在笔记中找到相关内容"
    # LLM **未被**调用 — 显式断言 (unreachable_llm.assert_not_called)
    unreachable_llm.assert_not_called()


# ── US6: defined_checker=False → NOT_DEFINED, LLM NOT called ─


def test_us6_no_definition() -> None:
    """design §3.5 决策 2: hits 非空但 defined_checker=False → 早返, LLM 不被调用."""
    hits = [_hit(snippet="这是一些无关的笔记内容")]
    defined_checker = MagicMock(return_value=False)
    unreachable_llm = MagicMock(
        side_effect=AssertionError("LLM must not be called on US6 path")
    )

    with patch("rag_demo.generate._call_llm", unreachable_llm):
        result = answer("微服务治理", hits, defined_checker=defined_checker)

    # 决策字段
    assert result.decision == "NOT_DEFINED"
    assert result.sources == hits
    # answer 文案包含 query + 部分 snippet
    assert "微服务治理" in result.answer
    assert "无关的笔记内容" in result.answer
    # defined_checker 被调用一次, 参数正确
    defined_checker.assert_called_once_with("微服务治理", hits)
    # LLM **未被**调用
    unreachable_llm.assert_not_called()


# ── happy path: GENERATED, LLM called once with prompt ──────


def test_happy_path_llm_called_with_snippet() -> None:
    """design §3.5 决策 3: defined_checker=True → 调 LLM, GENERATED.

    断言 LLM 被调一次, 且 question + hits (含 snippet 头 20 字) 都传入.
    当前 stub 签名 `_call_llm(question, hits)` — hits 已含 snippet, 业务侧
    (未来 ADR-0001 落地后) 在 prompt 模板里拼入. 这里的测试重点是 LLM 收到了
    snippet 上下文 (通过 hits 间接验证).
    """
    snippet = "微服务治理是分布式系统的协调机制, 包括服务注册与发现等"
    hits = [
        _hit(snippet=snippet),
        _hit(snippet="服务治理涉及流量控制、熔断降级等模式"),
    ]
    defined_checker = MagicMock(return_value=True)
    mock_llm = MagicMock(return_value="根据你的笔记, 微服务治理主要包括...")

    with patch("rag_demo.generate._call_llm", mock_llm):
        result = answer("什么是微服务治理", hits, defined_checker=defined_checker)

    # 决策字段
    assert result.decision == "GENERATED"
    assert result.sources == hits
    assert "微服务治理" in result.answer
    # LLM 被调一次
    assert mock_llm.call_count == 1
    # 调用参数: question + hits (snippet 头 20 字经 hits 传入 LLM)
    call_args = mock_llm.call_args
    assert call_args.args[0] == "什么是微服务治理"
    passed_hits = call_args.args[1]
    assert passed_hits == hits
    assert passed_hits[0].snippet[:20] == snippet[:20]
    # 进一步: 真实 LLM 入口在 prompt 模板里会拼入 snippet;
    # 当前 stub 直接返回字符串, 业务侧契约 (snippet 进 LLM) 由 hits 传递保证.


def test_happy_path_uses_injected_defined_checker() -> None:
    """当 defined_checker=True (注入) 时, 默认 is_defined_in_hits 不参与判定."""
    # hits 不含定义短语 (默认 is_defined_in_hits 会判 False), 但注入的 mock 返回 True
    # 验证: 注入的 checker 优先于默认实现
    hits = [_hit(snippet="一些内容, 不含任何定义短语")]
    mock_llm = MagicMock(return_value="ok")
    forced_true = MagicMock(return_value=True)

    with patch("rag_demo.generate._call_llm", mock_llm):
        result = answer("X", hits, defined_checker=forced_true)

    assert result.decision == "GENERATED"
    forced_true.assert_called_once_with("X", hits)


# ── defined_checker 异常路径 (额外覆盖) ─────────────────────


def test_defined_checker_exception_propagates() -> None:
    """如果注入的 defined_checker 抛异常, answer 不应吞 — 调用方负责处理."""
    broken_checker = MagicMock(side_effect=RuntimeError("checker boom"))
    with pytest.raises(RuntimeError, match="checker boom"):
        answer("X", [_hit("snippet")], defined_checker=broken_checker)

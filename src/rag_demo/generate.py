"""Generate: answer stage with US4 / US6 / happy-path decision chain + 真 LLM.

v1 contract — `docs/dev/design.md` §3.5:
  1. `hits` empty -> decision=RETRIEVE_EMPTY (LLM NOT called)
  2. `defined_checker(q, hits) == False` -> decision=NOT_DEFINED (LLM NOT called)
  3. otherwise -> call _call_llm(q, hits) -> decision=GENERATED

MAQ-36 落地:
  - `_call_llm` 替换为 `BaseLlmClient.stream(question, hits)` 流式调用
  - 保持模块级, 测试用 `unittest.mock.patch("rag_demo.generate._call_llm")`
  - 保持 `_call_llm` 签名 `(question: str, hits: list[Hit]) -> str` — 调用方用 `.join()` 拼流
  - 默认 _call_llm 是 None, 通过 `set_llm_client(client)` 注入 (模块级单例)
"""
from __future__ import annotations

from dataclasses import dataclass

from .llm import BaseLlmClient
from .retrieve import Hit
from .validate import DefinedCheck, is_defined_in_hits

# 模块级 LLM client 单例 — 由 web/__main__/ingest 启动时 set_llm_client() 注入
_llm_client: BaseLlmClient | None = None


def set_llm_client(client: BaseLlmClient | None) -> None:
    """注入 LLM client (None 表示 stub 模式, _call_llm 返拼接字符串)."""
    global _llm_client
    _llm_client = client


def get_llm_client() -> BaseLlmClient | None:
    return _llm_client


@dataclass(frozen=True)
class AnswerResult:
    """v1 design §3.5 — answer stage output."""

    answer: str
    sources: list[Hit]
    decision: str  # "RETRIEVE_EMPTY" | "NOT_DEFINED" | "GENERATED"


def _call_llm(question: str, hits: list[Hit]) -> str:
    """调 LLM. 有 client 时 stream + join; 无 client 时返 stub 拼接字符串.

    模块级函数 — 测试用 `unittest.mock.patch("rag_demo.generate._call_llm")` mock.
    """
    if _llm_client is None:
        # stub 模式 (per v1 design §3.5 旧行为): 返拼接字符串, 不发请求
        ctx = "\n\n".join(h.snippet for h in hits)
        return f"[stub-llm] answer for: {question!r}\n\nContext:\n{ctx}"
    # 真 LLM stream → join 成完整答案
    return "".join(_llm_client.stream(question, hits))


def answer(
    question: str,
    hits: list[Hit],
    *,
    defined_checker: DefinedCheck = is_defined_in_hits,
) -> AnswerResult:
    """决策链 (design §3.5)."""
    # 决策 1: hits 为空 -> RETRIEVE_EMPTY (LLM 不被调)
    if not hits:
        return AnswerResult(
            answer="未在笔记中找到相关内容",
            sources=[],
            decision="RETRIEVE_EMPTY",
        )
    # 决策 2: defined_checker 返回 False -> NOT_DEFINED (LLM 不被调)
    if not defined_checker(question, hits):
        snippets = "\n".join(f"- {h.snippet}" for h in hits)
        return AnswerResult(
            answer=(
                f"你的笔记里没找到 {question} 的明确定义，"
                f"仅有的相关片段是：\n{snippets}"
            ),
            sources=hits,
            decision="NOT_DEFINED",
        )
    # 决策 3: GENERATED
    text = _call_llm(question, hits)
    return AnswerResult(answer=text, sources=hits, decision="GENERATED")

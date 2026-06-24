"""Generate: answer stage with US4 / US6 / happy-path decision chain.

v1 contract — `docs/dev/design.md` §3.5:
  1. `hits` empty -> decision=RETRIEVE_EMPTY (LLM NOT called)
  2. `defined_checker(q, hits) == False` -> decision=NOT_DEFINED (LLM NOT called)
  3. otherwise -> call _call_llm(q, hits) -> decision=GENERATED

`_call_llm` is exposed at module level so tests can patch it via
`unittest.mock.patch("rag_demo.generate._call_llm", mock)`. This is the
injection point described in design §9.2 (assertion strength discipline):
US4 / US6 tests pass `unreachable_llm = MagicMock(side_effect=AssertionError(...))`
to ensure the LLM is never silently called on the early-return paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .retrieve import Hit


# MAQ-11 stub default: always returns True (preserves old _cmd_ask behavior —
# LLM is called for any non-empty hits). MAQ-12 (validate.py) replaces this
# default with `is_defined_in_hits`. The placeholder keeps this module
# importable in isolation, before `validate.py` lands.
_DEFAULT_DEFINED_CHECKER: Callable[[str, list[Hit]], bool] = lambda q, h: True


# 设计 §3.5: 可注入的判定函数签名 (与 validate.DefinedCheck 兼容)
DefinedCheck = Callable[[str, list[Hit]], bool]


@dataclass(frozen=True)
class AnswerResult:
    """v1 design §3.5 — answer stage output."""

    answer: str
    sources: list[Hit]
    decision: str  # "RETRIEVE_EMPTY" | "NOT_DEFINED" | "GENERATED"


def _call_llm(question: str, hits: list[Hit]) -> str:
    """Stub LLM call. Replace with real provider once ADR-0001 / ADR-0003 land.

    Module-level so tests can patch it (design §9.2).
    """
    ctx = "\n\n".join(h.snippet for h in hits)
    return f"[stub-llm] answer for: {question!r}\n\nContext:\n{ctx}"


def answer(
    question: str,
    hits: list[Hit],
    *,
    defined_checker: DefinedCheck = _DEFAULT_DEFINED_CHECKER,
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

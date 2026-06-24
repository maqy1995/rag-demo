"""Tests for `is_defined_in_hits` — US6 早返判定 (design §3.4 / §9.2).

判定规则按 handoff §2 收紧:
  - ✅ 保留: 是 / 为 / 指 (动词) + ：/ = / : (标点)
  - ❌ 去掉: -  (与无序列表项冲突, 存在误判风险)

纯函数: 无副作用, 无 LLM 调用. 每个用例直接 assert 返回值.
"""

from __future__ import annotations

from rag_demo.retrieve import Hit
from rag_demo.validate import DefinedCheck, is_defined_in_hits


def _hit(snippet: str, heading: str = "any") -> Hit:
    return Hit(
        source="vault://x/a.md#any",
        file="a.md",
        heading=heading,
        chunk_id=1,
        snippet=snippet,
        score=0.5,
    )


# ─────────────────────────────────────────────────────────────
# 正例 (是 / 为 / 指 / ：/ = / :)
# ─────────────────────────────────────────────────────────────


def test_positive_shi_verb() -> None:
    """是 — query 后接 是 ... (中文动词)."""
    hits = [_hit("微服务治理是分布式系统的协调机制")]
    assert is_defined_in_hits("微服务治理", hits) is True


def test_positive_wei_verb() -> None:
    """为 — query 后接 为 ... (中文动词)."""
    hits = [_hit("RAG 为检索增强生成的缩写")]
    assert is_defined_in_hits("RAG", hits) is True


def test_positive_zhi_verb() -> None:
    """指 — query 后接 指 ... (中文动词, 自然中文定义模式)."""
    hits = [_hit("服务治理 指在分布式系统中协调各服务的方法")]
    assert is_defined_in_hits("服务治理", hits) is True


def test_positive_chinese_colon_marker() -> None:
    """：— query 后接中文冒号."""
    hits = [_hit("微服务治理：分布式系统的协调机制")]
    assert is_defined_in_hits("微服务治理", hits) is True


def test_positive_equals_marker() -> None:
    """= — query 后接等号."""
    hits = [_hit("RAG = Retrieval-Augmented Generation")]
    assert is_defined_in_hits("RAG", hits) is True


def test_positive_ascii_colon_marker() -> None:
    """: — query 后接 ASCII 冒号."""
    hits = [_hit("RAG: Retrieval-Augmented Generation")]
    assert is_defined_in_hits("RAG", hits) is True


# ─────────────────────────────────────────────────────────────
# 大小写 + heading 命中
# ─────────────────────────────────────────────────────────────


def test_positive_case_insensitive() -> None:
    """design §3.4: query 与 snippet 都 .lower() 再匹配."""
    hits = [_hit("microservice 是分布式系统的协调机制")]
    assert is_defined_in_hits("MicroService", hits) is True


def test_positive_match_in_heading() -> None:
    """design §3.4: heading 也参与匹配."""
    hits = [_hit(snippet="无关内容", heading="X 是什么")]
    assert is_defined_in_hits("X", hits) is True


# ─────────────────────────────────────────────────────────────
# 反例
# ─────────────────────────────────────────────────────────────


def test_negative_no_definition_pattern() -> None:
    """无 是/为/指/：/=/: 紧跟 query → 走 US6 兜底."""
    hits = [_hit("X 相关内容, 但没有定义短语紧跟")]
    assert is_defined_in_hits("X", hits) is False


def test_negative_appears_only_in_unrelated_context() -> None:
    """query 出现但不在定义位置 → False."""
    hits = [_hit("讨论了一些 X 相关内容, 但没有正式定义")]
    assert is_defined_in_hits("X", hits) is False


def test_negative_empty_hits() -> None:
    """空 hits → False (虽然 generate.answer 在 hits 为空时先走 RETRIEVE_EMPTY,
    本函数自身仍安全返回 False)."""
    assert is_defined_in_hits("X", []) is False


def test_negative_no_marker_in_list_items() -> None:
    """无序列表项 '- item' 不再误判为定义 (handoff §2 收紧后).

    旧 v0.3 正则若把 '- ' 当 marker, 会把任何 'X - 任意内容' 视为定义.
    收紧后只有 'X 是/为/指/：/=/:...' 紧跟才算定义. 这里 'X' 不在 snippet
    中出现, 自然不命中.
    """
    hits = [_hit("- 列表项 1\n- 列表项 2\n- 列表项 3")]
    assert is_defined_in_hits("X", hits) is False


def test_negative_query_not_in_hits_at_all() -> None:
    hits = [_hit("完全不相关的内容")]
    assert is_defined_in_hits("微服务治理", hits) is False


# ─────────────────────────────────────────────────────────────
# 至少一个 hit 命中即 True (不需要全部)
# ─────────────────────────────────────────────────────────────


def test_any_hit_matches_returns_true() -> None:
    """3 个 hit 中只要 1 个命中定义短语即 True."""
    hits = [
        _hit("无关内容 1"),
        _hit("无关内容 2"),
        _hit("X 是分布式系统模式"),  # 这个命中
    ]
    assert is_defined_in_hits("X", hits) is True


# ─────────────────────────────────────────────────────────────
# DefinedCheck 类型别名可被任意 Callable[[str, list[Hit]], bool] 满足
# ─────────────────────────────────────────────────────────────


def _custom_checker(_q: str, _hits: list[Hit]) -> bool:
    return True


def test_defined_check_is_callable_type() -> None:
    """ensure the type alias is importable and structurally Callable."""
    custom: DefinedCheck = _custom_checker
    assert custom("anything", []) is True

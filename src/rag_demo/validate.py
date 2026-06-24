"""Validate: pure function for US6 'no definition found' early-return path.

v1 contract — `docs/dev/design.md` §3.4:
  - `is_defined_in_hits(query, hits) -> bool` 是纯函数
  - 无副作用、无 LLM 调用、无全局状态 (pytest 直接断言)
  - 可注入: `generate.answer(..., defined_checker=is_defined_in_hits)`
  - 判定规则按 handoff `2026-06-24-from-reviewer-to-dev-design-v1.1.md` §2 收紧:
      ✅ 保留: "是 / 为 / 指" (动词) + "：" / "=" / ":" (标点)
      ❌ 去掉: "- " (与无序列表项 - item 冲突, 存在误判风险)

判定模式: 任一 hit 的 snippet 或 heading 包含 `query` 后接
          可选空白 + 一个定义短语 (是/为/指/：/=/:)
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .retrieve import Hit

# 设计 §3.5: 可注入的判定函数签名
DefinedCheck = Callable[[str, list[Hit]], bool]

# 收紧后的定义短语 (handoff §2: 去掉 "- ")
_DEFINITION_MARKERS: tuple[str, ...] = ("是", "为", "指", "：", "=", ":")


def _build_pattern(query: str) -> re.Pattern[str]:
    """构造 query 后接定义短语的 regex. 大小写不敏感."""
    escaped_query = re.escape(query.lower())
    markers_alt = "|".join(re.escape(m) for m in _DEFINITION_MARKERS)
    return re.compile(rf"{escaped_query}\s*(?:{markers_alt})")


def is_defined_in_hits(query: str, hits: list[Hit]) -> bool:
    """判定 query 在 hits 中是否被明确定义.

    Args:
        query: 用户问题中的核心概念 (例如 "微服务治理").
        hits: retrieve() 返回的 Top-K 命中片段.

    Returns:
        True  if 任一 hit 的 snippet 或 heading 包含 `query` 后接
              定义短语 (是/为/指/：/=/:).
        False otherwise — 调用方应走 US6 兜底 (NOT_DEFINED 决策).

    Notes:
        - 大小写不敏感: query 与 hit 文本都 .lower() 再匹配.
        - 空 hits 直接 False (generate.answer 在 hits 为空时**先**走
          RETRIEVE_EMPTY 早返, 根本不会调本函数; 这里仍安全返回 False).
    """
    if not hits:
        return False
    pattern = _build_pattern(query)
    for hit in hits:
        if pattern.search(hit.snippet.lower()):
            return True
        if pattern.search(hit.heading.lower()):
            return True
    return False

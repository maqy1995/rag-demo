"""Generate: stub that concatenates retrieved chunks as 'context'.

Replace with a real LLM call once the user confirms provider + key.
"""

from __future__ import annotations


def answer(question: str, hits: list[dict]) -> str:
    if not hits:
        return f"[stub] no retrievers wired in yet — got: {question!r}"
    ctx = "\n\n".join(h.get("text", "") for h in hits)
    return f"[stub] answer for: {question!r}\n\nContext:\n{ctx}"

"""vault:// 协议编解码 (design §7.1 + PRD §7.1 编码规则).

格式: vault://<vault-name>/<relative-path>#<anchor>

编码规则 (PRD §7.1):
  - <vault-name>: RFC 3986 unreserved + percent-encoding (中文 UTF-8 percent)
  - <relative-path>: URL path 段编码 (空格 -> %20, / 保留; 中文 percent)
  - <anchor>: 不做 slug 化, 直接是 heading 原文的 percent-encoding

Python: urllib.parse.quote(..., safe='/')
前端: decodeURIComponent 反解.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

_PREFIX = "vault://"


def encode(vault: str, path: str, anchor: str) -> str:
    """编码 vault/path/anchor 为 vault:// URI.

    Args:
        vault: vault 名称 (用于 {vault} 占位).
        path: 相对 vault 根的相对路径, 内部 '/' 作为分隔符保留.
        anchor: heading 原文 (不做 slug 化).
    """
    enc_vault = quote(vault, safe="")
    enc_path = quote(path, safe="/")
    enc_anchor = quote(anchor, safe="")
    return f"{_PREFIX}{enc_vault}/{enc_path}#{enc_anchor}"


def decode(uri: str) -> tuple[str, str, str]:
    """解码 vault:// URI 为 (vault, path, anchor).

    Raises:
        ValueError: uri 不以 'vault://' 开头, 或缺 # 分隔符, 或缺 path 段.
    """
    if not uri.startswith(_PREFIX):
        raise ValueError(f"not a vault:// URI: {uri!r}")
    body = uri[len(_PREFIX):]
    if "#" not in body:
        raise ValueError(f"missing anchor separator '#': {uri!r}")
    path_part, _, anchor = body.partition("#")
    if "/" not in path_part:
        raise ValueError(f"missing path separator '/': {uri!r}")
    vault, _, path = path_part.partition("/")
    return (unquote(vault), unquote(path), unquote(anchor))

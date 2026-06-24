"""Config: AppConfig + load_config() (design §6.1).

加载顺序: ./config.yaml -> ./config.example.yaml -> 内置默认
.env 注入: 仅用于敏感字段 (API key / base URL), 不进 AppConfig, 走 os.environ.
缺 vault.path: 返回空字符串 (触发冷启动 demo 路径, design §3.1 F1 + §3.2 要点).

L4 横切层 — 不 import L2 / L3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .errors import AppError

# ── 内置默认值 (设计 §6.1) ──────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "vault": {"path": "", "name": "my-notes", "include_extensions": [".md"]},
    "ingest": {"chunk_size": 500, "chunk_overlap": 80, "full": True},
    "retrieve": {"top_k": 5, "filters": {}},
    "generate": {
        "llm": {"provider": "ollama", "model": "qwen2.5", "base_url": "http://localhost:11434"},
        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
        "defined_check_pattern": "",
    },
    "web": {"host": "127.0.0.1", "port": 8000, "index_dir": "./data/index"},
    "usage": {"enabled": True, "dir": "./data/usage"},
}


# ── Dataclass 形态 (扁平) ────────────────────────────────────


@dataclass(frozen=True)
class AppConfig:
    # vault
    vault_path: str = ""
    vault_name: str = "my-notes"
    include_extensions: tuple[str, ...] = (".md",)
    # ingest
    chunk_size: int = 500
    chunk_overlap: int = 80
    ingest_full: bool = True
    # retrieve
    top_k: int = 5
    filters: dict = field(default_factory=dict)
    # generate - llm
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5"
    llm_base_url: str = "http://localhost:11434"
    # generate - embedding
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    defined_check_pattern: str = ""
    # web
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    index_dir: str = "./data/index"
    # usage
    usage_enabled: bool = True
    usage_dir: str = "./data/usage"

    def effective(self) -> dict[str, Any]:
        """脱敏的 dict 形态 (不含 secret), 供 GET /api/config 返回."""
        return {
            "vault": {
                "path": self.vault_path,
                "name": self.vault_name,
                "include_extensions": list(self.include_extensions),
            },
            "ingest": {
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap,
                "full": self.ingest_full,
            },
            "retrieve": {"top_k": self.top_k, "filters": dict(self.filters)},
            "generate": {
                "llm": {
                    "provider": self.llm_provider,
                    "model": self.llm_model,
                    "base_url": self.llm_base_url,
                },
                "embedding": {
                    "provider": self.embedding_provider,
                    "model": self.embedding_model,
                },
                "defined_check_pattern": self.defined_check_pattern,
            },
            "web": {
                "host": self.web_host,
                "port": self.web_port,
                "index_dir": self.index_dir,
            },
            "usage": {"enabled": self.usage_enabled, "dir": self.usage_dir},
        }


# ── 加载流程 ─────────────────────────────────────────────────


def _deep_merge(base: dict, override: dict) -> dict:
    """deep-merge override into base; nested dicts merged recursively."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise AppError(code="CONFIG_LOAD_FAIL", message=f"config 解析失败 {path}: {e}") from e
    if not isinstance(data, dict):
        raise AppError(code="CONFIG_LOAD_FAIL", message=f"config 顶层必须是 mapping: {path}")
    return data


def _flatten(merged: dict) -> AppConfig:
    """merged dict -> AppConfig (扁平化)."""
    v = merged["vault"]
    i = merged["ingest"]
    r = merged["retrieve"]
    g = merged["generate"]
    w = merged["web"]
    u = merged["usage"]
    llm = g["llm"]
    em = g["embedding"]
    return AppConfig(
        vault_path=str(v.get("path", "")),
        vault_name=str(v.get("name", "my-notes")),
        include_extensions=tuple(v.get("include_extensions", [".md"])),
        chunk_size=int(i.get("chunk_size", 500)),
        chunk_overlap=int(i.get("chunk_overlap", 80)),
        ingest_full=bool(i.get("full", True)),
        top_k=int(r.get("top_k", 5)),
        filters=dict(r.get("filters", {}) or {}),
        llm_provider=str(llm.get("provider", "ollama")),
        llm_model=str(llm.get("model", "qwen2.5")),
        llm_base_url=str(llm.get("base_url", "http://localhost:11434")),
        embedding_provider=str(em.get("provider", "ollama")),
        embedding_model=str(em.get("model", "nomic-embed-text")),
        defined_check_pattern=str(g.get("defined_check_pattern", "")),
        web_host=str(w.get("host", "127.0.0.1")),
        web_port=int(w.get("port", 8000)),
        index_dir=str(w.get("index_dir", "./data/index")),
        usage_enabled=bool(u.get("enabled", True)),
        usage_dir=str(u.get("dir", "./data/usage")),
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    """加载 config. 优先级: 显式 path > ./config.yaml > ./config.example.yaml > 内置默认.

    .env 通过 python-dotenv 注入, 仅影响 os.environ (不进 AppConfig).
    """
    load_dotenv()  # 设计 §6.1 强制 .env 注入
    if path is not None:
        return _flatten(_deep_merge(_DEFAULTS, _load_yaml_file(Path(path))))
    cfg = Path("./config.yaml")
    raw = _load_yaml_file(cfg) if cfg.exists() else _load_yaml_file(Path("./config.example.yaml"))
    return _flatten(_deep_merge(_DEFAULTS, raw))

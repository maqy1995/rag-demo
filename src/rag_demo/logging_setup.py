"""Logging: 一行 JSON 格式 (design §6.2 + PRD §5).

格式: {"ts": ISO8601-with-ms-Z, "level": INFO, "stage": retrieve,
       "cost_ms": 120, "msg": "top_k=5 hits=3"}

stage 取值: ingest / retrieve / generate / infra / web
cost_ms 默认 0, stage 默认 "infra" (业务侧建议显式传 extra).
snippet 等大 payload 仅 DEBUG 级 (这里只输出 msg, 不传 payload).
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

_STAGE_DEFAULT = "infra"


@dataclass(frozen=True)
class JsonLogRecord:
    """typed 包装 — 业务侧可选构造, 也可直接用 logger.info(extra=...)."""

    msg: str
    level: str = "INFO"
    stage: str = _STAGE_DEFAULT
    cost_ms: int = 0


class JsonFormatter(logging.Formatter):
    """一行 JSON formatter (design §6.2)."""

    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created, tz=UTC)
        ts = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z"
        payload = {
            "ts": ts,
            "level": record.levelname,
            "stage": getattr(record, "stage", _STAGE_DEFAULT),
            "cost_ms": int(getattr(record, "cost_ms", 0)),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_json_logging(level: str = "INFO") -> None:
    """初始化 root logger + 单 StreamHandler."""
    root = logging.getLogger()
    # 避免重复 handler (测试中反复 setup)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())

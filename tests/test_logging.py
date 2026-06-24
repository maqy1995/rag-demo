"""Tests for `logging_setup` module (design §6.2)."""

from __future__ import annotations

import json
import logging

from rag_demo.logging_setup import (
    _STAGE_DEFAULT,
    JsonFormatter,
    JsonLogRecord,
    setup_json_logging,
)

# ── JsonFormatter 格式 ──────────────────────────────────────


def _format(record: logging.LogRecord) -> str:
    return JsonFormatter().format(record)


def test_json_formatter_basic_fields() -> None:
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    line = _format(rec)
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["msg"] == "hello world"
    assert payload["stage"] == _STAGE_DEFAULT
    assert payload["cost_ms"] == 0
    assert "ts" in payload
    assert payload["ts"].endswith("Z")  # UTC


def test_json_formatter_stage_and_cost_from_extra() -> None:
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="top_k=5 hits=3", args=(), exc_info=None,
    )
    rec.stage = "retrieve"
    rec.cost_ms = 120
    payload = json.loads(_format(rec))
    assert payload["stage"] == "retrieve"
    assert payload["cost_ms"] == 120


def test_json_formatter_chinese_msg() -> None:
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="微服务治理检索完成", args=(), exc_info=None,
    )
    payload = json.loads(_format(rec))
    assert payload["msg"] == "微服务治理检索完成"


# ── setup_json_logging 流程 ────────────────────────────────


def test_setup_json_logging_writes_to_stderr() -> None:
    setup_json_logging(level="INFO")
    handler = logging.getLogger().handlers[-1]
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname="x", lineno=1,
        msg="setup-test", args=(), exc_info=None,
    )
    rec.stage = "infra"
    formatted = handler.formatter.format(rec)
    payload = json.loads(formatted)
    assert payload["msg"] == "setup-test"
    assert payload["stage"] == "infra"


def test_setup_json_logging_idempotent() -> None:
    """重复 setup 不会加多个 handler (避免重复日志)."""
    setup_json_logging()
    n1 = len(logging.getLogger().handlers)
    setup_json_logging()
    n2 = len(logging.getLogger().handlers)
    assert n1 == n2


# ── JsonLogRecord typed 包装 ───────────────────────────────


def test_json_log_record_defaults() -> None:
    rec = JsonLogRecord(msg="hi")
    assert rec.msg == "hi"
    assert rec.level == "INFO"
    assert rec.stage == _STAGE_DEFAULT
    assert rec.cost_ms == 0


def test_json_log_record_custom() -> None:
    rec = JsonLogRecord(msg="x", level="WARN", stage="generate", cost_ms=500)
    assert rec.level == "WARN"
    assert rec.stage == "generate"
    assert rec.cost_ms == 500

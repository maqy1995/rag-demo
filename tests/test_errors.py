"""Tests for `errors` module (design §5 / §6.3)."""

from __future__ import annotations

import pytest

from rag_demo.errors import ERROR_CODES, AppError, raise_error

# ── ERROR_CODES 字典完整性 ──────────────────────────────────


def test_error_codes_has_all_required_keys() -> None:
    """design §5 状态码/决策码字典必须覆盖 PRD 全部 code."""
    required = {
        "INGEST_INVALID_CONFIG", "INGEST_BUILD_FAIL",
        "RETRIEVE_EMPTY", "RETRIEVE_INDEX_MISSING",
        "NOT_DEFINED", "GENERATE_LLM_FAIL", "GENERATE_INVALID_QUESTION",
        "CONFIG_LOAD_FAIL", "USAGE_LOG_FAIL",
    }
    assert required.issubset(ERROR_CODES.keys())


def test_error_codes_have_required_fields() -> None:
    """每个 code 必须含 http_status / stage / message."""
    for code, spec in ERROR_CODES.items():
        assert "http_status" in spec, f"{code} missing http_status"
        assert "stage" in spec, f"{code} missing stage"
        assert "message" in spec, f"{code} missing message"
        assert isinstance(spec["http_status"], int)
        assert spec["stage"] in {"ingest", "retrieve", "generate", "infra", "web"}


def test_decision_codes_marked() -> None:
    """RETRIEVE_EMPTY / NOT_DEFINED 是决策码 (200, is_decision=True)."""
    for code in ("RETRIEVE_EMPTY", "NOT_DEFINED"):
        spec = ERROR_CODES[code]
        assert spec["http_status"] == 200
        assert spec.get("is_decision") is True


# ── AppError 构造 ───────────────────────────────────────────


def test_app_error_default_message_from_dict() -> None:
    err = AppError(code="GENERATE_LLM_FAIL")
    assert err.code == "GENERATE_LLM_FAIL"
    assert err.message == "LLM 调用失败"
    assert err.stage == "generate"
    assert err.http_status == 503
    assert err.is_decision is False


def test_app_error_override_message() -> None:
    err = AppError(code="GENERATE_LLM_FAIL", message="custom")
    assert err.message == "custom"
    # http_status / stage 仍走默认
    assert err.http_status == 503
    assert err.stage == "generate"


def test_app_error_unknown_code_falls_back() -> None:
    err = AppError(code="UNKNOWN_CODE")
    assert err.code == "UNKNOWN_CODE"
    assert err.message == "UNKNOWN_CODE"  # fallback to code
    assert err.http_status == 500
    assert err.stage == "infra"


def test_app_error_inherits_exception() -> None:
    """AppError 是 Exception 子类, 可被 except Exception 捕获."""
    err = AppError(code="RETRIEVE_INDEX_MISSING")
    assert isinstance(err, Exception)


# ── raise_error() ───────────────────────────────────────────


def test_raise_error_raises() -> None:
    with pytest.raises(AppError) as excinfo:
        raise_error("INGEST_INVALID_CONFIG")
    assert excinfo.value.code == "INGEST_INVALID_CONFIG"
    assert excinfo.value.http_status == 400


def test_raise_error_message_template() -> None:
    """{query} 占位符应被 kwargs 替换."""
    with pytest.raises(AppError) as excinfo:
        raise_error("NOT_DEFINED", query="微服务治理")
    assert excinfo.value.message == "你的笔记里没找到 微服务治理 的明确定义"


def test_raise_error_unknown_code() -> None:
    with pytest.raises(AppError) as excinfo:
        raise_error("MYSTERY")
    assert excinfo.value.code == "MYSTERY"

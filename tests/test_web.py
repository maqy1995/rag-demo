"""Tests for `web/main.py` FastAPI 端点 (design §3.6 / §6.3).

覆盖 (10+ 用例):
  - /api/health → 200
  - /api/search 空检索 → 200 + {hits: []}
  - /api/chat US4 决策 → decision=RETRIEVE_EMPTY (200)
  - /api/chat US6 决策 → decision=NOT_DEFINED (200)
  - /api/chat happy path → decision=GENERATED (200)
  - /api/chat/stream SSE 帧 → 含 event: meta + decision
  - /api/chat/stream 早返路径 → 1 个 token + sources + meta
  - /api/config → 不含 secret
  - /api/index/status 无 index 目录 → state=idle
  - /api/ingest → IngestStats 序列化
  - /api/usage → 写 jsonl
  - /api/usage/query → 今日事件数
  - L3 → L2 边界: AppError → JSONResponse(e.http_status, {error: {...}})
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rag_demo.errors import AppError
from rag_demo.retrieve import Hit
from rag_demo.web.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient + 隔离 tmp_path (config 用 ./data/...)."""
    monkeypatch.chdir(tmp_path)
    return TestClient(app)


@pytest.fixture
def stub_retrieve() -> Any:
    """stub retrieve 始终返回空 list (US4 路径)."""
    with patch("rag_demo.web.main.retrieve", return_value=[]) as m:
        yield m


@pytest.fixture
def stub_retrieve_with_hits() -> Any:
    """stub retrieve 返回 1 个 hit (US6 / happy path)."""
    hit = Hit(
        source="vault://x/a.md#h",
        file="a.md",
        heading="h",
        chunk_id=1,
        snippet="微服务治理是分布式系统的协调机制",
        score=0.5,
    )
    with patch("rag_demo.web.main.retrieve", return_value=[hit]) as m:
        yield m, hit


# ── /api/health ─────────────────────────────────────────────


def test_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


# ── /api/config ─────────────────────────────────────────────


def test_config_no_secret(client: TestClient) -> None:
    """GET /api/config 响应体不含 API key / secret."""
    res = client.get("/api/config")
    assert res.status_code == 200
    body = res.text
    for forbidden in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "sk-"):
        assert forbidden not in body, f"/api/config leaks {forbidden!r}"
    # 必备 section
    for section in ("vault", "ingest", "retrieve", "generate", "web", "usage"):
        assert section in res.json()


# ── /api/index/status ───────────────────────────────────────


def test_index_status_idle_when_no_index(client: TestClient) -> None:
    """无 index 目录 → state=idle + 其他字段 None/0."""
    res = client.get("/api/index/status")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "idle"
    assert body["files_total"] == 0
    assert body["chunks_total"] == 0
    assert body["last_built_at"] is None
    assert body["current_progress"] is None


# ── /api/search ─────────────────────────────────────────────


def test_search_empty(client: TestClient, stub_retrieve: Any) -> None:
    res = client.post("/api/search", json={"query": "X", "top_k": 5})
    assert res.status_code == 200
    assert res.json() == {"hits": []}
    stub_retrieve.assert_called_once()


def test_search_with_hits(client: TestClient, stub_retrieve_with_hits: Any) -> None:
    _, hit = stub_retrieve_with_hits
    res = client.post("/api/search", json={"query": "微服务治理", "top_k": 5})
    assert res.status_code == 200
    body = res.json()
    assert len(body["hits"]) == 1
    h = body["hits"][0]
    assert h["source"] == hit.source
    assert h["snippet"] == hit.snippet


# ── /api/chat ──────────────────────────────────────────────


def test_chat_us4_empty_hits(client: TestClient, stub_retrieve: Any) -> None:
    """hits=[] → decision=RETRIEVE_EMPTY, 200, 不走 error 壳."""
    res = client.post("/api/chat", json={"question": "X"})
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "RETRIEVE_EMPTY"
    assert body["answer"] == "未在笔记中找到相关内容"
    assert body["sources"] == []
    assert "error" not in body  # 决策码不走 error 壳


def test_chat_us6_no_definition(
    client: TestClient, stub_retrieve_with_hits: Any
) -> None:
    """hits 非空但 is_defined_in_hits=False → decision=NOT_DEFINED.

    默认 is_defined_in_hits 对不含定义短语的 snippet 返 False.
    """
    res = client.post("/api/chat", json={"question": "X"})
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "NOT_DEFINED"
    assert "X" in body["answer"]
    assert "明确定义" in body["answer"]
    assert len(body["sources"]) == 1


def test_chat_happy_path(
    client: TestClient, stub_retrieve_with_hits: Any
) -> None:
    """hits snippet 含定义短语 (是 ...) → decision=GENERATED."""
    # stub_retrieve_with_hits 的 snippet 已经是 "微服务治理是..." — 默认 is_defined_in_hits 返 True
    res = client.post("/api/chat", json={"question": "微服务治理"})
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] == "GENERATED"
    assert "微服务治理" in body["answer"]


def test_chat_invalid_question_too_long(client: TestClient) -> None:
    """Pydantic Field max_length=2000 校验."""
    res = client.post("/api/chat", json={"question": "x" * 2001})
    # FastAPI 默认 422 校验错误; 我们接受 4xx 即可
    assert 400 <= res.status_code < 500


# ── /api/chat/stream (SSE) ─────────────────────────────────


def test_chat_stream_sse_frame_format(
    client: TestClient, stub_retrieve: Any
) -> None:
    """SSE 协议: US4 早返路径应发 1 token + sources + meta."""
    res = client.post("/api/chat/stream", json={"question": "X"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    text = res.text
    # 必须含 event: meta + decision
    assert "event: meta" in text
    assert "RETRIEVE_EMPTY" in text
    # 早返: 只发 1 个 token (decision 文案)
    assert text.count("event: token") == 1
    assert "未在笔记中找到相关内容" in text
    assert "event: sources" in text


def test_chat_stream_happy_path(
    client: TestClient, stub_retrieve_with_hits: Any
) -> None:
    res = client.post("/api/chat/stream", json={"question": "微服务治理"})
    assert res.status_code == 200
    text = res.text
    assert "event: meta" in text
    assert "GENERATED" in text
    # 至少发 1 个 token (stub 阶段一次性发完整 answer, 仍走 token 事件)
    assert "event: token" in text


# ── /api/ingest ─────────────────────────────────────────────


def test_ingest_endpoint_writes_status(
    client: TestClient, tmp_path: Path
) -> None:
    """POST /api/ingest 触发全量重建, 写 data/index/status.json."""
    data = tmp_path / "raw"
    data.mkdir()
    (data / "a.md").write_text("hello world " * 50, encoding="utf-8")
    index = tmp_path / "index"
    res = client.post("/api/ingest", json={"full": True, "data": str(data), "index": str(index)})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["stats"]["files_total"] == 1
    assert body["stats"]["chunks_total"] >= 1
    # status.json 落盘
    assert (index / "status.json").exists()


def test_ingest_invalid_data_dir(
    client: TestClient, tmp_path: Path
) -> None:
    """data dir 不存在 → 400 + INGEST_INVALID_CONFIG."""
    res = client.post("/api/ingest", json={"full": True, "data": str(tmp_path / "nonexistent")})
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "INGEST_INVALID_CONFIG"
    assert body["error"]["stage"] == "ingest"


# ── /api/usage ──────────────────────────────────────────────


def test_usage_post_writes_jsonl(
    client: TestClient, tmp_path: Path
) -> None:
    res = client.post("/api/usage", json={"event": "chat", "payload": {"q": "x"}})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    # jsonl 文件被创建
    cfg_dir = tmp_path / "data" / "usage"
    assert cfg_dir.exists()
    files = list(cfg_dir.glob("local-*.jsonl"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip()
    ev = json.loads(line)
    assert ev["event"] == "chat"
    assert ev["payload"] == {"q": "x"}


def test_usage_query_counts_today(
    client: TestClient
) -> None:
    # 写 2 条
    client.post("/api/usage", json={"event": "chat"})
    client.post("/api/usage", json={"event": "cold_start_abandoned"})
    res = client.post("/api/usage/query", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["events_today"] == 2
    assert body["abandoned_cold_starts"] == 1


# ── L3 → L2 边界: AppError 转 JSONResponse ─────────────────


def test_apperror_returns_json_response(client: TestClient) -> None:
    """业务函数抛 AppError → 端点应捕获并转 {error: {code, message, stage}}."""
    fake_exc = AppError(code="GENERATE_LLM_FAIL", message="LLM 调用失败")
    with patch("rag_demo.web.main.answer", side_effect=fake_exc):
        res = client.post("/api/chat", json={"question": "X"})
    assert res.status_code == 503
    body = res.json()
    assert body["error"]["code"] == "GENERATE_LLM_FAIL"
    assert body["error"]["message"] == "LLM 调用失败"
    assert body["error"]["stage"] == "generate"

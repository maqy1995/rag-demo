"""FastAPI app — 8 端点 + 1 选做 (design §3.6 / §6.3).

薄壳 (≤ 280 行 per design §3.1):
  - L3 → L2 边界固定 try / except AppError as e: JSONResponse(...)
  - 决策码 (RETRIEVE_EMPTY / NOT_DEFINED) 走 200 + decision, 不走 error 壳
  - SSE 协议: token / sources / meta / error 4 事件
  - 静态文件: src/rag_demo/web/static/ 挂在 /
"""

from __future__ import annotations

import json
import time  # noqa: F401 - 保留: 后续 SSE cost_ms 计时
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import load_config
from ..errors import AppError
from ..generate import answer
from ..ingest import ingest_directory
from ..retrieve import retrieve

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="rag-demo",
    version="0.1.0",
    description="本地知识库问答 — Knowledge-Base QA (design §3.6)",
)


# ── Pydantic 请求体 ─────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict | None = None
    selected_sources: list[str] | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    filters: dict | None = None


class IngestRequest(BaseModel):
    full: bool = True
    data: str | None = None
    index: str | None = None


class UsageEvent(BaseModel):
    event: str
    payload: dict | None = None


# ── 错误壳: L3 → L2 边界 (design §6.3) ──────────────────────


def _error_response(exc: AppError) -> JSONResponse:
    """AppError → JSONResponse. 决策码 (is_decision=True) 不走此路径 —
    决策码在端点里手动返回 {decision: ...}, 200."""
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message, "stage": exc.stage}},
    )


def _hit_dict(h: Any) -> dict[str, Any]:
    """Hit dataclass / dict 统一转 dict (设计 §7.3 响应体格式)."""
    if isinstance(h, dict):
        return h
    return {
        "source": h.source,
        "file": h.file,
        "heading": h.heading,
        "chunk_id": h.chunk_id,
        "snippet": h.snippet,
        "score": h.score,
    }


# ── /api/health ─────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


# ── /api/config ─────────────────────────────────────────────


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    """脱敏 config — effective() 不含 secret (PRD §7.2)."""
    return load_config().effective()


# ── /api/index/status ───────────────────────────────────────


@app.get("/api/index/status")
def index_status() -> Any:
    """读 data/index/status.json (design §3.2 单一信源)."""
    cfg = load_config()
    status_path = Path(cfg.index_dir) / "status.json"
    if not status_path.exists():
        return {
            "state": "idle",
            "files_total": 0,
            "chunks_total": 0,
            "skipped_unchanged": 0,
            "current_progress": None,
            "last_built_at": None,
            "duration_ms": 0,
        }
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=503,
            content={"error": {
                "code": "RETRIEVE_INDEX_MISSING",
                "message": "status.json 损坏",
                "stage": "infra",
            }},
        )


# ── /api/search ─────────────────────────────────────────────


@app.post("/api/search")
def search(req: SearchRequest) -> dict[str, Any]:
    """纯检索, 不调 LLM (F4 左栏, design §3.6)."""
    cfg = load_config()
    try:
        hits = retrieve(
            req.query, index_dir=cfg.index_dir,
            top_k=req.top_k, filters=req.filters,
        )
    except AppError as e:
        return _error_response(e)
    return {"hits": [_hit_dict(h) for h in hits]}


# ── /api/chat (非流式) ─────────────────────────────────────


@app.post("/api/chat")
def chat(req: ChatRequest) -> Any:
    """非流式问答 (设计 §3.6)."""
    cfg = load_config()
    t0 = time.perf_counter()
    try:
        hits = retrieve(
            req.question, index_dir=cfg.index_dir,
            top_k=req.top_k, filters=req.filters,
        )
        result = answer(req.question, hits)
    except AppError as e:
        return _error_response(e)
    return {
        "answer": result.answer,
        "sources": [_hit_dict(h) for h in result.sources],
        "decision": result.decision,
        "cost_ms": int((time.perf_counter() - t0) * 1000),
    }


# ── /api/chat/stream (SSE) ─────────────────────────────────


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """SSE 流式问答 — 决策 1/2 早返只发 1 个 token + sources + meta."""

    def _generate() -> AsyncIterator[str]:
        t0 = time.perf_counter()
        try:
            hits = retrieve(
                req.question, index_dir=load_config().index_dir,
                top_k=req.top_k, filters=req.filters,
            )
            result = answer(req.question, hits)
        except AppError as e:
            yield _sse_event("error", {
                "error": {"code": e.code, "message": e.message, "stage": e.stage},
            })
            return

        sources_payload = [_hit_dict(h) for h in result.sources]
        if result.decision in ("RETRIEVE_EMPTY", "NOT_DEFINED"):
            yield _sse_event("token", {"delta": result.answer})
            yield _sse_event("sources", {"sources": sources_payload})
            yield _sse_event("meta", {
                "retrieved": len(hits),
                "decision": result.decision,
                "cost_ms": {"retrieve": int((time.perf_counter() - t0) * 1000), "generate": 0},
            })
            return

        # 决策 3 GENERATED: stub 一次性发完整 answer; 真实 LLM 接 ADR-0001 后逐 token yield
        text = result.answer
        for i in range(0, len(text), 16):
            yield _sse_event("token", {"delta": text[i : i + 16]})
        yield _sse_event("sources", {"sources": sources_payload})
        yield _sse_event("meta", {
            "retrieved": len(hits),
            "decision": result.decision,
            "cost_ms": {
                "retrieve": int((time.perf_counter() - t0) * 1000),
                "generate": int((time.perf_counter() - t0) * 1000),
            },
        })

    return StreamingResponse(_generate(), media_type="text/event-stream")


# ── /api/ingest ─────────────────────────────────────────────


@app.post("/api/ingest")
def ingest(req: IngestRequest) -> Any:
    """触发全量/增量重建 (等价 CLI ingest, design §3.6)."""
    cfg = load_config()
    data = req.data or cfg.vault_path or "./data/raw"
    index = req.index or cfg.index_dir
    try:
        stats = ingest_directory(data, index, full=req.full)
    except AppError as e:
        return _error_response(e)
    except (FileNotFoundError, ValueError) as e:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "code": "INGEST_INVALID_CONFIG",
                "message": str(e),
                "stage": "ingest",
            }},
        )
    return {"ok": True, "stats": _stats_dict(stats)}


def _stats_dict(s: Any) -> dict[str, Any]:
    if isinstance(s, dict):
        return s
    return {
        "state": s.state,
        "files_total": s.files_total,
        "chunks_total": s.chunks_total,
        "skipped_unchanged": s.skipped_unchanged,
        "current_progress": s.current_progress,
        "last_built_at": s.last_built_at,
        "duration_ms": s.duration_ms,
    }


# ── /api/usage ──────────────────────────────────────────────


def _today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


@app.post("/api/usage")
def usage_log(req: UsageEvent) -> Any:
    """埋点写入 data/usage/local-{date}.jsonl (design §3.6 / §8.4)."""
    cfg = load_config()
    if not cfg.usage_enabled:
        return {"ok": True, "skipped": True}
    usage_dir = Path(cfg.usage_dir)
    try:
        usage_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(UTC).isoformat(),
            "event": req.event,
            "payload": req.payload or {},
        }, ensure_ascii=False)
        log_path = usage_dir / f"local-{_today_str()}.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "USAGE_LOG_FAIL", "message": str(e), "stage": "infra"}},
        )
    return {"ok": True}


@app.post("/api/usage/query")
def usage_query() -> dict[str, Any]:
    """自检: 统计今日事件数 (设计 §3.6 选做)."""
    cfg = load_config()
    log_path = Path(cfg.usage_dir) / f"local-{_today_str()}.jsonl"
    if not log_path.exists():
        return {"events_today": 0, "abandoned_cold_starts": 0}
    n = 0
    abandoned = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        n += 1
        if ev.get("event") == "cold_start_abandoned":
            abandoned += 1
    return {"events_today": n, "abandoned_cold_starts": abandoned}


# ── 静态文件 ────────────────────────────────────────────────

_STATIC_DIR.mkdir(parents=True, exist_ok=True)
_STATIC_INDEX = _STATIC_DIR / "index.html"
if not _STATIC_INDEX.exists():
    _STATIC_INDEX.write_text(
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>rag-demo</title></head><body>"
        "<h1>rag-demo</h1>"
        "<p>API available at <code>/api/health</code> etc.</p>"
        "<p>Static index placeholder — see MAQ-18 for full cold-start UI.</p>"
        "</body></html>",
        encoding="utf-8",
    )

app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

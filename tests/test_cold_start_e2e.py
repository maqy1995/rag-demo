"""End-to-end cold-start 30s test (MAQ-42).

跑 pytest 时默认跳过 (需 `pytest -m e2e`)。

测试步骤:
1. 起 uvicorn 子进程 (`rag_demo.web.main:app`) 在临时端口
2. 等服务 bind 端口 (≤ 5s)
3. 拉 `/` (index.html) — 断言 HTML 字节收到 (≤ 30s cold-start)
4. 调 `/api/index/status` — 断言 state 字段存在
5. 调 `/api/chat` mock LLM 路径 (RETRIEVE_EMPTY 早返) — 断言 200 + JSON 结构
6. 子进程 SIGTERM — 断言 5s 内退出

验收:
- pytest -m e2e 跑通
- 145 + 4 = ≥ 149 测试全绿 (普通 pytest 不算 e2e, 默认跳过)
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    """找一个空闲端口."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 10.0) -> bool:
    """等服务起来 (poll /api/health)."""
    start = time.perf_counter()
    while time.perf_counter() - start < timeout:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=1.0)
            if r.status_code == 200 and r.json().get("ok") is True:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.2)
    return False


@pytest.fixture
def uvicorn_proc(tmp_path):
    """起 uvicorn 子进程, 结束 yield 后 SIGTERM."""
    port = _free_port()
    index_dir = tmp_path / "data" / "index"
    index_dir.mkdir(parents=True)
    # 写空 status.json, 走空 index 路径 (US4)
    (index_dir / "status.json").write_text(
        json.dumps({
            "state": "idle",
            "files_total": 0,
            "chunks_total": 0,
            "skipped_unchanged": 0,
            "current_progress": None,
            "last_built_at": None,
            "duration_ms": 0,
        }),
        encoding="utf-8",
    )
    env_overrides = {
        "RAG_DEMO_WEB_INDEX_DIR": str(index_dir),
        "RAG_DEMO_DATA_DIR": str(tmp_path / "data" / "raw"),
    }
    import os
    env = {**os.environ, **env_overrides}
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "rag_demo.web.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent,
    )
    # 等服务 ready
    ready = _wait_ready(port, timeout=10.0)
    if not ready:
        proc.terminate()
        proc.wait(timeout=5.0)
        stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        pytest.fail(f"uvicorn 未在 10s 内 ready\nstderr:\n{stderr}")
    yield port, proc
    # cleanup: SIGTERM + 等 5s 内退出
    t0 = time.perf_counter()
    proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)
        pytest.fail(f"uvicorn SIGTERM 后未在 5s 内退出 (实际 {time.perf_counter() - t0:.1f}s)")


def test_cold_start_index_html_responds_within_30s(uvicorn_proc):
    """PRD §3.1 F8 + §8.2: index.html 首字节 ≤ 30s 收到."""
    port, _ = uvicorn_proc
    t0 = time.perf_counter()
    r = requests.get(f"http://127.0.0.1:{port}/", timeout=30.0)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200
    assert "知识库问答" in r.text  # 真 UI 含这个标题
    assert elapsed < 30.0, f"cold-start 首字节 {elapsed:.1f}s 超 30s 阈值"


def test_api_index_status_returns_state_field(uvicorn_proc):
    """/api/index/status 返回 {state: ...} 结构."""
    port, _ = uvicorn_proc
    r = requests.get(f"http://127.0.0.1:{port}/api/index/status", timeout=5.0)
    assert r.status_code == 200
    body = r.json()
    assert "state" in body
    assert body["state"] in {"idle", "building", "error"}


def test_api_chat_returns_decision_when_no_index(uvicorn_proc):
    """空 index → /api/chat 走 RETRIEVE_EMPTY 决策码 (US4 早返路径)."""
    port, _ = uvicorn_proc
    r = requests.post(
        f"http://127.0.0.1:{port}/api/chat",
        json={"question": "test query", "top_k": 5},
        timeout=5.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert "decision" in body
    # 空 index → retrieve 返 [] → RETRIEVE_EMPTY
    assert body["decision"] == "RETRIEVE_EMPTY"
    assert body["answer"] == "未在笔记中找到相关内容"


def test_api_health_returns_ok(uvicorn_proc):
    """/api/health 返 200 + {ok: True}."""
    port, _ = uvicorn_proc
    r = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json() == {"ok": True}

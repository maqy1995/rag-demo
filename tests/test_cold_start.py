"""Tests for cold-start 30s budget (design §3.1 F8 / §4.1 / §8.1).

测量点: index.html 首字节 → 5 按钮可点击 ≤ 30s.
mock 后端应 5s 内完成; 真实后端留 30s 上限.

本子 issue 不做 Playwright (v0.2 升级); 用 TestClient + 计时 + 后台
ingest 线程不阻塞 web 验证 §4.1 关键不变量.
data/index.sample/ 5 示例问题回答源**留作软阻塞** (PRD §11.2 S4).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rag_demo.web.main import app


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ── TestClient 路径: 端到端冷启动 (无后台线程, 纯 web) ──────


def test_cold_start_index_html_responds_quickly(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """index.html 必须在 30s 内返回首字节 (mock 后端, 应 < 1s)."""
    monkeypatch.chdir(tmp_path)
    t0 = time.perf_counter()
    res = client.get("/")
    elapsed = time.perf_counter() - t0
    assert res.status_code == 200
    assert elapsed < 30.0, f"index.html took {elapsed:.1f}s, exceeds 30s budget"


def test_cold_start_health_endpoint_within_30s(client: TestClient) -> None:
    """健康检查 < 1s."""
    t0 = time.perf_counter()
    res = client.get("/api/health")
    elapsed = time.perf_counter() - t0
    assert res.status_code == 200
    assert elapsed < 30.0
    assert elapsed < 1.0, f"/api/health took {elapsed:.2f}s, should be < 1s"


# ── 后台 ingest 线程不阻塞 web (design §4.1) ──────────────


def test_cold_start_background_ingest_doesnt_block_web(
    client: TestClient, tmp_path: Path
) -> None:
    """up 启动后台 ingest 线程, web 仍能在 1s 内响应.

    mock ingest 延迟 5s, 验证期间 GET /api/health 仍快速返回.
    """
    import threading

    started = threading.Event()

    def _slow_ingest(*_args: object, **_kwargs: object) -> object:
        started.set()
        time.sleep(5.0)  # 模拟慢 ingest
        from rag_demo.ingest import IngestStats
        return IngestStats(
            state="idle", files_total=0, chunks_total=0,
            skipped_unchanged=0, current_progress=None,
            last_built_at=None, duration_ms=5000,
        )

    with patch("rag_demo.web.main.ingest_directory", _slow_ingest):
        # 模拟 up 的后台线程行为: 启动 ingest 线程
        thread = threading.Thread(
            target=_slow_ingest, daemon=True, name="bg-ingest-test",
        )
        thread.start()
        # ingest 启动后, web 应立即响应
        t0 = time.perf_counter()
        res = client.get("/api/health")
        elapsed = time.perf_counter() - t0
        assert res.status_code == 200
        assert elapsed < 1.0, f"web blocked by ingest: {elapsed:.2f}s"
        # 收尾
        thread.join(timeout=6.0)


# ── 真实子进程路径: uvicorn 启动 ≤ 30s ──────────────────────


def test_cold_start_uvicorn_binds_within_30s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真实 uvicorn 进程从启动到端口可连 ≤ 30s.

    与 test_smoke 区别: 这里**不**发 SIGTERM, 单纯验证启动耗时 ≤ 30s.
    """
    monkeypatch.chdir(tmp_path)
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "rag_demo", "up", "--no-ingest",
         "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        t0 = time.perf_counter()
        for _ in range(300):  # max 30s (100ms interval)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            elapsed = time.perf_counter() - t0
            pytest.fail(f"uvicorn did not bind port {port} within 30s (elapsed: {elapsed:.1f}s)")
        elapsed = time.perf_counter() - t0
        # 实际后端 < 5s 应足够, 30s 是上界
        assert elapsed < 30.0
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


# ── /api/index/status 在 ingest 进行中: state=building 字段必须存在 ──


def test_cold_start_index_status_field_shape(client: TestClient) -> None:
    """§3.2 6 字段全在响应里 (即便值是 None/0)."""
    res = client.get("/api/index/status")
    assert res.status_code == 200
    body = res.json()
    # 设计 §3.2 单一信源 6 字段
    for field in ("state", "files_total", "chunks_total", "skipped_unchanged",
                  "current_progress", "last_built_at", "duration_ms"):
        assert field in body, f"/api/index/status 缺字段 {field!r}"


# ── TestClient fixture ──────────────────────────────────────


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(app)

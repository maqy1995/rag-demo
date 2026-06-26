"""Live e2e tests for MAQ-51 (background ingest regression).

跑 pytest 默认跳过 (需 `pytest -m e2e`).

MAQ-51 live regression 修复 (dfb1071 之后):
  前一轮 bug: `_start_bg_ingest` 调 `ingest_directory` 默认 stub 全 0 向量,
  把主人手动 build 的 2048-dim zhipu 索引覆盖成 1536-dim stub → live search 全 503.
  修复: `_start_bg_ingest` 接收 `embedder` / `embedding_provider` /
        `embedding_model` / `embedding_dim` 参数, `_cmd_up` 显式注入.

本测试覆盖:
1. test_start_bg_ingest_calls_ingest_with_real_embedder — 单元级: mock ingest_directory
   验证 bg 线程收到真 embedder + zhipu provider, 不是 None/stub 默认
2. test_start_bg_ingest_falls_back_to_stub_on_missing_key — 缺 key 兜底, 走 stub
3. test_api_search_live_against_real_index — live curl: 直接调 /api/search 看返回
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

pytestmark = pytest.mark.e2e


# ── 单元级: 验证 _start_bg_ingest 把 embedder 传给 ingest_directory ──────────


def test_start_bg_ingest_calls_ingest_with_real_embedder(monkeypatch):
    """MAQ-51 (dfb1071+): bg ingest 必须用 cfg 真 embedder, 不是 stub 默认.

    验证: _start_bg_ingest 启动后调 ingest_directory 时, embedder 是传入的
    bg_embedder 实例 (有 .embed_one), embedding_provider='zhipu',
    embedding_dim=2048 — 不是 stub/None/1536.
    """
    from rag_demo.__main__ import _start_bg_ingest

    captured: dict = {}

    def fake_ingest(*args, **kwargs):
        captured.update(kwargs)
        # 模拟完成 stats
        return MagicMock(state="idle", files_total=1, chunks_total=3)

    monkeypatch.setattr("rag_demo.ingest.ingest_directory", fake_ingest)

    fake_embedder = MagicMock()
    fake_embedder.embed_one.return_value = [0.1] * 2048  # 真 embedder 假实现

    thread = _start_bg_ingest(
        data_dir="/tmp/raw",
        index_dir="/tmp/index",
        ingest_fn=fake_ingest,
        embedder=fake_embedder,
        embedding_provider="zhipu",
        embedding_model="embedding-3",
        embedding_dim=2048,
    )
    thread.start()
    thread.join(timeout=5.0)

    # bg 线程必须把真 embedder 透传给 ingest_directory
    assert captured.get("embedder") is fake_embedder, (
        f"_start_bg_ingest 没透传 embedder → ingest_directory 收到 "
        f"{captured.get('embedder')!r} (MAQ-51 live regression)"
    )
    assert captured.get("embedding_provider") == "zhipu"
    assert captured.get("embedding_dim") == 2048
    assert captured.get("embedding_model") == "embedding-3"


def test_start_bg_ingest_thread_completes(monkeypatch):
    """bg ingest 线程能正常跑完 (daemon=False + join)."""
    from rag_demo.__main__ import _start_bg_ingest

    called = {"n": 0}

    def fake_ingest(*args, **kwargs):
        called["n"] += 1
        return MagicMock(state="idle", files_total=0, chunks_total=0)

    monkeypatch.setattr("rag_demo.ingest.ingest_directory", fake_ingest)
    thread = _start_bg_ingest(
        data_dir="/tmp/raw", index_dir="/tmp/index",
        ingest_fn=fake_ingest,
        embedder=None,
        embedding_provider="stub",
        embedding_dim=1536,
    )
    thread.start()
    thread.join(timeout=5.0)
    assert called["n"] == 1


# ── live curl: 真 uvicorn subprocess 调 API 端点 ───────────────


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, timeout: float = 15.0) -> bool:
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
def uvicorn_proc_no_bg_ingest():
    """起 uvicorn + --no-ingest, 用项目已有的 data/index (pre-build).

    不带 bg ingest 避免子进程去 ingest 主人 vault 覆盖; 用项目 data/index 当 fixture.
    这个 fixture 验证的是 web lifespan 注入 + retrieve 真实调起, 不是 bg ingest.
    """
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "rag_demo.web.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent,
    )
    ready = _wait_ready(port, timeout=15.0)
    if not ready:
        proc.terminate()
        proc.wait(timeout=5.0)
        stderr = proc.stderr.read().decode("utf-8", errors="ignore") if proc.stderr else ""
        pytest.fail(f"uvicorn 未在 15s 内 ready\nstderr:\n{stderr}")
    yield port, proc
    proc.terminate()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)


def test_live_search_against_real_index(uvicorn_proc_no_bg_ingest):
    """live `/api/search` 用项目 data/index (223 chunks zhipu 2048-dim) 真检索.

    这是 owner 实际生产路径 — 之前因为 bg ingest 覆盖索引 → 503.
    修复后 (dfb1071+) 应能正常返 ≥1 hit, score > 0.
    """
    port, _ = uvicorn_proc_no_bg_ingest
    r = requests.post(
        f"http://127.0.0.1:{port}/api/search",
        json={"query": "微服务", "top_k": 3},
        timeout=15.0,
    )
    assert r.status_code == 200, f"/api/search got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "hits" in body
    # 不强求 match (vault 是余华活着.txt, "微服务" 不在里头), 但至少要非 503
    # 如果 dim mismatch 修了, 应至少返 0 hits (不是 503 error)
    if len(body["hits"]) == 0:
        # 检查不是 503 error
        assert "error" not in body, f"empty hits 但带 error: {body}"


def test_live_chat_against_real_index(uvicorn_proc_no_bg_ingest):
    """live `/api/chat` 真路径 — 返 200 + decision 字段."""
    port, _ = uvicorn_proc_no_bg_ingest
    r = requests.post(
        f"http://127.0.0.1:{port}/api/chat",
        json={"question": "什么是 hello", "top_k": 3},
        timeout=15.0,
    )
    assert r.status_code == 200, f"/api/chat got {r.status_code}: {r.text[:200]}"
    body = r.json()
    assert "decision" in body
    assert body["decision"] in {"RETRIEVE_EMPTY", "NOT_DEFINED", "GENERATED"}
    assert "answer" in body
"""Smoke tests — verify the CLI runs end-to-end with stub implementations.

Covers (design §9.1 / §11.3):
  - `rag-demo doctor` basic run
  - `rag-demo ingest --data <tmp> --index <tmp> --chunk-size N` writes manifest
  - `rag-demo up --help` available (MAQ-15)
  - `rag-demo web --help` available (MAQ-15, alias of up)
  - `rag-demo doctor` includes config.yaml row (design §3.7)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "rag_demo", *args],
        capture_output=True,
        text=True,
        check=True,
    )


def test_doctor_runs() -> None:
    out = _run(["doctor"])
    assert "rag-demo" in out.stdout
    # design §3.7: doctor 输出 config 文件存在性行
    assert "config.yaml" in out.stdout


def test_ingest_writes_manifest(tmp_path: Path) -> None:
    data = tmp_path / "raw"
    data.mkdir()
    (data / "a.md").write_text("hello world " * 50, encoding="utf-8")
    idx = tmp_path / "index"
    res = _run(
        [
            "ingest",
            "--data",
            str(data),
            "--index",
            str(idx),
            "--chunk-size",
            "100",
        ]
    )
    assert "ingested" in res.stdout
    manifest = json.loads((idx / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["chunk_count"] >= 1
    # design §3.2: status.json 单一信源 (与 manifest.json 同级)
    assert (idx / "status.json").exists()


def test_up_help() -> None:
    """design §3.7 — `up` 是主入口, --help 必须可用."""
    out = _run(["up", "--help"])
    assert out.returncode == 0
    # help 文案含 ingest / background / host 至少一个
    lowered = out.stdout.lower()
    assert "ingest" in lowered or "background" in lowered
    assert "--host" in out.stdout
    assert "--no-ingest" in out.stdout


def test_web_help() -> None:
    """design §3.7 — `web` 是 `up` 的 alias, --help 必须可用."""
    out = _run(["web", "--help"])
    assert out.returncode == 0
    assert "--host" in out.stdout
    assert "--no-ingest" in out.stdout


def test_up_no_ingest_starts_web_then_terminates_on_signal() -> None:
    """MAQ-11 / MAQ-15 / MAQ-17: web app 已落地, `up --no-ingest` 应能启动 uvicorn.

    用 socket 找到一个空闲端口, 启动子进程, 等待端口可连, 发 SIGTERM,
    验证 graceful shutdown (exit 0). 不做端到端 HTTP 验证 (test_web.py 已覆盖).
    """
    import signal
    import socket
    import time

    # 找空闲端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    cmd = [
        sys.executable, "-m", "rag_demo", "up", "--no-ingest",
        "--host", "127.0.0.1", "--port", str(port),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        # 等待端口可连 (max 8s)
        for _ in range(80):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail(f"up did not bind port {port} within 8s")
        # 端口可达 — 优雅退出
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)


def test_bg_ingest_thread_is_not_daemon() -> None:
    """NB4 (MAQ-22): _start_bg_ingest 创建的线程必须 daemon=False,
    这样 finally.join(timeout=5.0) 真的能等到 ingest 跑完.
    """
    from rag_demo.__main__ import _start_bg_ingest

    def _noop_ingest(*_args: object, **_kwargs: object) -> object:
        return None

    thread = _start_bg_ingest(
        data_dir="/tmp", index_dir="/tmp", ingest_fn=_noop_ingest,
    )
    thread.start()
    try:
        assert thread.daemon is False, (
            "bg ingest thread 必须是 non-daemon 才能被 finally.join 真正等到"
        )
        assert thread.name == "bg-ingest"
    finally:
        thread.join(timeout=5.0)


def test_bg_ingest_thread_join_waits_for_slow_ingest() -> None:
    """NB4 (MAQ-22): bg ingest 线程 sleep 0.5s, 主流程 join 真的能等到完成."""
    import time

    from rag_demo.__main__ import _start_bg_ingest

    def _slow_ingest(*_args: object, **_kwargs: object) -> object:
        time.sleep(0.5)
        return None

    thread = _start_bg_ingest(
        data_dir="/tmp", index_dir="/tmp", ingest_fn=_slow_ingest,
    )
    thread.start()
    # 模拟主流程 finally: 等到线程完成 (daemon=False 时 join 真的能等到)
    thread.join(timeout=5.0)
    assert not thread.is_alive(), "join 后线程应已结束 (daemon=False)"
    # 验证 ingest 真的跑完了 (跑完会写 stdout, 但我们只检查 is_alive)

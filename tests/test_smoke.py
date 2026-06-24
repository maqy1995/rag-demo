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


def test_up_no_ingest_fallback_when_web_missing() -> None:
    """MAQ-11 / MAQ-15: web app 未落地时, --no-ingest 优雅降级.

    不接真实 LLM / 真实 web server, 仅验证 import 失败不导致 crash.
    """
    res = subprocess.run(
        [sys.executable, "-m", "rag_demo", "up", "--no-ingest"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    # graceful fallback 应 exit 0; web.main:app ImportError 已被 except ImportError 吞掉
    assert res.returncode == 0
    assert "web module not yet implemented" in res.stdout

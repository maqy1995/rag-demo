"""Smoke tests — verify the CLI runs end-to-end with stub implementations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_doctor_runs() -> None:
    out = subprocess.run([sys.executable, "-m", "rag_demo", "doctor"], capture_output=True, text=True, check=True)
    assert "rag-demo" in out.stdout


def test_ingest_writes_manifest(tmp_path: Path) -> None:
    data = tmp_path / "raw"
    data.mkdir()
    (data / "a.md").write_text("hello world " * 50, encoding="utf-8")
    idx = tmp_path / "index"
    res = subprocess.run(
        [sys.executable, "-m", "rag_demo", "ingest", "--data", str(data), "--index", str(idx), "--chunk-size", "100"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ingested" in res.stdout
    manifest = json.loads((idx / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert manifest["chunk_count"] >= 1

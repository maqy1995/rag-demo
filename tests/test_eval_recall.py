"""Tests for scripts/eval_recall.py (MAQ-40)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_eval_recall_smoke_runs():
    """跑默认 5 条样例, 不崩."""
    result = subprocess.run(
        [sys.executable, "scripts/eval_recall.py", "--json"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    assert result.returncode in (0, 1)  # 0 hits 时 exit 1
    report = json.loads(result.stdout)
    assert "total" in report
    assert "hits" in report
    assert "recall_at_k" in report
    assert report["total"] == 5


def test_eval_recall_custom_dataset(tmp_path):
    """自定义 dataset path."""
    ds_file = tmp_path / "ds.json"
    ds_file.write_text(json.dumps([
        {"question": "微服务治理", "expected": "微服务"},
        {"question": "冷启动", "expected": "冷启动"},
    ], ensure_ascii=False))
    result = subprocess.run(
        [sys.executable, "scripts/eval_recall.py", "--json", "--dataset", str(ds_file)],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    report = json.loads(result.stdout)
    assert report["total"] == 2
    assert "details" in report


def test_eval_recall_human_readable_output():
    result = subprocess.run(
        [sys.executable, "scripts/eval_recall.py"],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent,
    )
    assert "Recall@5" in result.stdout
    assert "Q:" in result.stdout
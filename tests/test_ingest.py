"""Tests for `ingest_directory` (design §3.2).

覆盖 (设计 §3.2 + MAQ-22 review 阻塞项):
  - test_ingest_basic — 1 文件 → 1+ chunk + manifest + status.json
  - test_ingest_state_flips_building_then_idle (NB2) — on_progress 回调验证 building→idle
  - test_ingest_status_written_while_building (NB2) — 跑完后 status.json 落盘
  - test_ingest_chunk_overlap_too_large — ValueError
  - test_ingest_falls_back_to_sample (NB3) — data_dir 不存在 → data/raw.sample/
  - test_ingest_empty_data_dir_falls_back (NB3) — data_dir 存在但空 → data/raw.sample/
  - test_ingest_missing_sample_returns_idle_zero (NB3) — 都缺 → idle + 全零
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_demo.ingest import _SAMPLE_DATA_DIR, ingest_directory


def test_ingest_basic(tmp_path: Path) -> None:
    """1 文件 → 1+ chunk + manifest + status.json 落盘."""
    data = tmp_path / "raw"
    data.mkdir()
    (data / "a.md").write_text("hello world " * 50, encoding="utf-8")
    index = tmp_path / "index"
    stats = ingest_directory(data, index)
    assert stats.files_total == 1
    assert stats.chunks_total >= 1
    assert stats.state == "idle"
    assert (index / "manifest.json").exists()
    assert (index / "status.json").exists()
    status = json.loads((index / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "idle"
    assert status["files_total"] == 1


def test_ingest_state_flips_building_then_idle(tmp_path: Path) -> None:
    """NB2 (MAQ-22): on_progress 回调能观察到 building → idle 的翻转."""
    data = tmp_path / "raw"
    data.mkdir()
    for i in range(3):
        (data / f"f{i}.md").write_text("content " * 20, encoding="utf-8")

    seen_states: list[str] = []

    def _track(done: int, total: int) -> None:
        # 跑 ingest 过程中, 读 status.json 看 state 字段
        idx_path = tmp_path / "index"
        status_path = idx_path / "status.json"
        if status_path.exists():
            seen_states.append(
                json.loads(status_path.read_text(encoding="utf-8"))["state"]
            )

    stats = ingest_directory(
        data, tmp_path / "index", on_progress=_track,
    )
    # 至少看到一次 "building" (中途读)
    assert "building" in seen_states, f"never observed building: {seen_states}"
    # 终态是 idle
    assert stats.state == "idle"
    # 终态 status.json 也是 idle
    final = json.loads((tmp_path / "index" / "status.json").read_text(encoding="utf-8"))
    assert final["state"] == "idle"


def test_ingest_status_written_while_building(tmp_path: Path) -> None:
    """NB2 (MAQ-22): 启动后 status.json 立刻可读, current_progress.done 从 0 起步."""
    data = tmp_path / "raw"
    data.mkdir()
    for i in range(5):
        (data / f"f{i}.md").write_text("x" * 100, encoding="utf-8")

    # 用一个慢回调让我们能读中间态
    import time

    def _slow_progress(done: int, total: int) -> None:
        if done == 1:
            # 第一个文件处理完, 应该能看到 state=building + current_progress.done=1
            status_path = tmp_path / "index" / "status.json"
            if status_path.exists():
                payload = json.loads(status_path.read_text(encoding="utf-8"))
                assert payload["state"] == "building"
                assert payload["current_progress"]["total"] == 5
            time.sleep(0.01)  # 让 race condition 不再 race

    stats = ingest_directory(
        data, tmp_path / "index", on_progress=_slow_progress,
    )
    assert stats.state == "idle"


def test_ingest_chunk_overlap_too_large(tmp_path: Path) -> None:
    """chunk_overlap >= chunk_size → ValueError."""
    data = tmp_path / "raw"
    data.mkdir()
    (data / "a.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="chunk_overlap"):
        ingest_directory(
            data, tmp_path / "index",
            chunk_size=100, chunk_overlap=100,
        )


def test_ingest_falls_back_to_sample(tmp_path: Path) -> None:
    """NB3 (MAQ-22): data_dir 不存在 → 自动 fallback 到 data/raw.sample/."""
    if not _SAMPLE_DATA_DIR.exists() or not any(_SAMPLE_DATA_DIR.iterdir()):
        pytest.skip("data/raw.sample not provisioned")
    missing = tmp_path / "nope_does_not_exist"
    stats = ingest_directory(missing, tmp_path / "index")
    # fallback 后应该跑通, 不抛错, 且 files_total > 0
    assert stats.state == "idle"
    assert stats.files_total >= 1
    assert stats.chunks_total >= 1


def test_ingest_empty_data_dir_falls_back(tmp_path: Path) -> None:
    """NB3 (MAQ-22): data_dir 存在但空 → 自动 fallback 到 data/raw.sample/."""
    if not _SAMPLE_DATA_DIR.exists() or not any(_SAMPLE_DATA_DIR.iterdir()):
        pytest.skip("data/raw.sample not provisioned")
    empty = tmp_path / "empty"
    empty.mkdir()
    stats = ingest_directory(empty, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total >= 1


def test_ingest_dir_with_only_dotfiles_falls_back(tmp_path: Path) -> None:
    """MAQ-46: data_dir 只有 .gitkeep 这种 dotfile 占位 → 也走 fallback.

    之前的 `any(data_dir.iterdir())` 会被 .gitkeep 挡住, 误判为"非空"
    然后继续 scan 拿到 0 个可 ingest 文件, files_total=0 chunks_total=0.
    修复: iterdir 时过滤掉 dotfile.
    """
    if not _SAMPLE_DATA_DIR.exists() or not any(_SAMPLE_DATA_DIR.iterdir()):
        pytest.skip("data/raw.sample not provisioned")
    data = tmp_path / "raw_with_gitkeep"
    data.mkdir()
    (data / ".gitkeep").write_text("", encoding="utf-8")
    stats = ingest_directory(data, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total >= 1, (
        f"expected fallback to raw.sample, got files_total={stats.files_total}"
    )


def test_ingest_dir_with_real_files_and_dotfile_does_not_fall_back(tmp_path: Path) -> None:
    """回归 (MAQ-46 follow-up): 真实 .md + dotfile 共存 → 走 ingest，不走 fallback."""
    data = tmp_path / "raw"
    data.mkdir()
    (data / "real.md").write_text("hello world " * 30, encoding="utf-8")
    (data / ".gitkeep").write_text("", encoding="utf-8")
    stats = ingest_directory(data, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total == 1
    assert stats.chunks_total >= 1


def test_ingest_missing_sample_returns_idle_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NB3 (MAQ-22): data_dir 缺 + sample 也缺 → idle + 全零 stats, 不抛错."""
    # 让 _SAMPLE_DATA_DIR 指向一个空目录
    fake_sample = tmp_path / "fake_sample"
    fake_sample.mkdir()
    monkeypatch.setattr("rag_demo.ingest._SAMPLE_DATA_DIR", fake_sample)
    missing = tmp_path / "nope"
    stats = ingest_directory(missing, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total == 0
    assert stats.chunks_total == 0
    assert stats.last_built_at is None

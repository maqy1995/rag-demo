"""Build data/index.sample/ — 预 embed 示例索引 (MAQ-39).

用法:
    uv run python scripts/build_sample_index.py

不带任何参数:
- 读 data/raw.sample/ (5 篇示例)
- 写 data/index.sample/{faiss.index, faiss_meta.json, manifest.json, status.json}
- 用 dummy 全 0 向量 (embedding_dim=4, smoke 用)

带真 API key:
- 编辑本脚本, 把 embedding_dim 改成 1536, 注入真 OpenAICompatibleEmbedder
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让脚本从仓库根运行也能 import src/rag_demo
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from rag_demo.ingest import ingest_directory  # noqa: E402


def main() -> int:
    data_dir = _ROOT / "data" / "raw.sample"
    index_dir = _ROOT / "data" / "index.sample"
    if not data_dir.exists() or not any(data_dir.iterdir()):
        print(f"❌ data_dir missing or empty: {data_dir}")
        return 1
    # smoke 模式: embedding_dim=4, dummy 向量 (无 API key)
    # 真接时改成 1536 + 注入 OpenAICompatibleEmbedder
    stats = ingest_directory(
        data_dir=data_dir,
        index_dir=index_dir,
        full=True,
        chunk_size=500,
        chunk_overlap=80,
        embedding_dim=4,
        embedding_provider="stub",
        embedding_model="stub-dim4",
    )
    print(
        f"✅ sample index built: "
        f"state={stats.state} files={stats.files_total} "
        f"chunks={stats.chunks_total} duration_ms={stats.duration_ms}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

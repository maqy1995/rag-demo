"""Recall@K evaluator (MAQ-40, MAQ-51 update).

用法:
    uv run python scripts/eval_recall.py                 # 默认: sample index + 4-dim stub
    uv run python scripts/eval_recall.py --k 5 --json
    uv run python scripts/eval_recall.py --real-embed    # 走真 embedder (MAQ-51)
    uv run python scripts/eval_recall.py --index-dir data/index

不带参数: 跑硬编码 5 条样例 (基于现有 data/raw.sample 5 篇);
输出 JSON 报告到 stdout.

接受 --dataset 路径 (JSON 格式: [(question, expected_source_substring_or_heading), ...])
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from rag_demo.retrieve import retrieve, set_embedder  # noqa: E402

# 硬编码 5 条样例 (基于现有 data/raw.sample 5 篇)
# 期待: 任一 hit 的 file / source / heading 包含 expected_substring 即命中
DEFAULT_DATASET: list[tuple[str, str]] = [
    ("微服务治理是怎么定义的？", "微服务治理"),
    ("服务发现是什么？", "服务注册"),
    ("怎么切换 LLM provider？", "LLM Provider"),
    ("冷启动 demo 是怎么做的？", "冷启动"),
    ("怎么评估检索质量？", "Recall"),
]


def evaluate(
    dataset: list[tuple[str, str]],
    *,
    index_dir: str | Path,
    k: int = 5,
    real_embed: bool = False,
) -> dict:
    """跑一遍 dataset, 返回 {total, hits, recall_at_k, details}.

    Args:
        real_embed: True 时从 AppConfig 构造真 embedder 并注入 retrieve 单例;
                    dim 从 index 自身读 (读 manifest.json), 不是 hardcode 4.
                    失败 (e.g. API key 缺) 时降级到 stub.
    """
    if not dataset:
        return {"total": 0, "hits": 0, "recall_at_k": 0.0, "details": []}

    # MAQ-51: 真 embedder 模式 — 构造真 client 注入 retrieve 模块级单例
    embedder_obj = None
    index_dim = 4
    if real_embed:
        try:
            from rag_demo.config import load_config
            from rag_demo.llm import build_embedder
            from rag_demo.vector import VectorStore

            cfg = load_config()
            embedder_obj = build_embedder(cfg)
            set_embedder(embedder_obj)
            # 读 manifest.json 的 embedding_dim, 与 index 一致
            manifest_p = Path(index_dir) / "manifest.json"
            if manifest_p.exists():
                index_dim = int(json.loads(manifest_p.read_text())["embedding_dim"])
        except Exception as e:  # noqa: BLE001 - 顶层 CLI 兜底
            print(f"[eval-recall] 真 embedder 模式失败, 降级到 stub: {e}")
            embedder_obj = None
            set_embedder(None)

    details = []
    hits = 0
    for question, expected in dataset:
        results = retrieve(
            question,
            index_dir=index_dir,
            top_k=k,
            embedder=embedder_obj,  # 显式传 (走真) 或 None (走 stub)
            dim=index_dim,
        )
        # 任一 hit 的 file/heading/snippet 包含 expected 即命中
        matched = any(
            expected.lower() in (h.file + h.heading + h.snippet).lower()
            for h in results
        )
        if matched:
            hits += 1
        details.append({
            "question": question,
            "expected": expected,
            "matched": matched,
            "top_k_files": [h.file for h in results[:k]],
            "top_scores": [h.score for h in results[:k]],
        })
    return {
        "total": len(dataset),
        "hits": hits,
        "recall_at_k": round(hits / len(dataset), 4),
        "k": k,
        "mode": "real_embed" if (real_embed and embedder_obj) else "stub",
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recall@K evaluator (MAQ-40 / MAQ-51)")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--index-dir", default=str(_ROOT / "data" / "index.sample"))
    parser.add_argument("--dataset", help="JSON 路径: [(q, expected), ...]")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    parser.add_argument(
        "--real-embed", action="store_true",
        help="MAQ-51: 用真实 embedder (从 .env + config.yaml 构造) 而非 stub 全 0 向量",
    )
    args = parser.parse_args(argv)

    if args.dataset:
        ds_raw = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
        dataset = [(item["question"], item["expected"]) for item in ds_raw]
    else:
        dataset = DEFAULT_DATASET

    report = evaluate(
        dataset, index_dir=args.index_dir, k=args.k, real_embed=args.real_embed,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Recall@{args.k} [{report['mode']}]: "
            f"{report['recall_at_k']:.2%} ({report['hits']}/{report['total']})"
        )
        for d in report["details"]:
            mark = "✅" if d["matched"] else "❌"
            scores = ",".join(f"{s:.3f}" for s in d["top_scores"][:3])
            print(f"  {mark} Q: {d['question'][:40]}... → top: {d['top_k_files'][:2]} scores=[{scores}]")

    # 0 hits → exit 1 (CI fail-fast)
    return 0 if report["hits"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

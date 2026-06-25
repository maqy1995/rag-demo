"""Recall@K evaluator (MAQ-40).

用法:
    uv run python scripts/eval_recall.py
    uv run python scripts/eval_recall.py --k 5 --json

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

from rag_demo.retrieve import retrieve  # noqa: E402

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
) -> dict:
    """跑一遍 dataset, 返回 {total, hits, recall_at_k, details}."""
    if not dataset:
        return {"total": 0, "hits": 0, "recall_at_k": 0.0, "details": []}
    details = []
    hits = 0
    for question, expected in dataset:
        results = retrieve(
            question,
            index_dir=index_dir,
            top_k=k,
            embedder=None,  # smoke 模式: 全 0 向量, dummy 检索
            dim=4,
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
        })
    return {
        "total": len(dataset),
        "hits": hits,
        "recall_at_k": round(hits / len(dataset), 4),
        "k": k,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recall@K evaluator (MAQ-40)")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--index-dir", default=str(_ROOT / "data" / "index.sample"))
    parser.add_argument("--dataset", help="JSON 路径: [(q, expected), ...]")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args(argv)

    if args.dataset:
        ds_raw = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
        dataset = [(item["question"], item["expected"]) for item in ds_raw]
    else:
        dataset = DEFAULT_DATASET

    report = evaluate(dataset, index_dir=args.index_dir, k=args.k)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Recall@{args.k}: {report['recall_at_k']:.2%} ({report['hits']}/{report['total']})")
        for d in report["details"]:
            mark = "✅" if d["matched"] else "❌"
            print(f"  {mark} Q: {d['question'][:40]}... → top: {d['top_k_files'][:2]}")

    # 0 hits → exit 1 (CI fail-fast)
    return 0 if report["hits"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
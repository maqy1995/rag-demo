"""Tests for src/rag_demo/vector/__init__.py (MAQ-34 VectorStore/FAISS)."""
from __future__ import annotations

import json

import pytest

from rag_demo.errors import AppError
from rag_demo.vector import VectorStore


def _vec(values: list[float]) -> list[float]:
    """构造任意向量 (不归一化, 库内部会归一化)."""
    return values


def test_empty_store_search_returns_empty(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=4)
    store.load()
    hits = store.search([0.1, 0.2, 0.3, 0.4], top_k=5)
    assert hits == []


def test_add_and_search_basic(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=4)
    vecs = [
        _vec([1.0, 0.0, 0.0, 0.0]),
        _vec([0.0, 1.0, 0.0, 0.0]),
        _vec([0.0, 0.0, 1.0, 0.0]),
    ]
    metas = [{"file": f"doc{i}.md", "chunk_id": i} for i in range(3)]
    store.add(vecs, metas)
    assert store.ntotal == 3
    hits = store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
    assert len(hits) == 2
    # 第一名应该是 doc0 (与查询同向)
    assert hits[0][1]["file"] == "doc0.md"
    assert hits[0][0] > hits[1][0]  # score 降序


def test_search_returns_score_descending(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=3)
    store.add(
        [_vec([1, 0, 0]), _vec([0.7, 0.7, 0]), _vec([0, 1, 0])],
        [{"i": 0}, {"i": 1}, {"i": 2}],
    )
    hits = store.search([1, 0, 0], top_k=3)
    scores = [h[0] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_save_and_load_roundtrip(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=4)
    vecs = [_vec([1, 0, 0, 0]), _vec([0, 1, 0, 0])]
    metas = [{"file": "a.md"}, {"file": "b.md"}]
    store.add(vecs, metas)
    store.save()

    store2 = VectorStore(index_dir=tmp_path, dim=4).load()
    assert store2.ntotal == 2
    hits = store2.search([1, 0, 0, 0], top_k=1)
    assert hits[0][1]["file"] == "a.md"


def test_top_k_caps_at_ntotal(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=2)
    store.add([_vec([1, 0])], [{"i": 0}])
    hits = store.search([1, 0], top_k=10)
    assert len(hits) == 1


def test_search_empty_query_returns_empty(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=2)
    store.add([_vec([1, 0])], [{"i": 0}])
    hits = store.search([1, 0], top_k=0)
    assert hits == []


def test_dim_mismatch_raises(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=4)
    store.add([_vec([1, 0, 0, 0])], [{"i": 0}])  # 让 store 非空
    with pytest.raises(AppError):
        store.search([1, 0, 0], top_k=1)  # dim=3 vs configured=4


def test_vectors_metas_length_mismatch_raises(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=2)
    with pytest.raises(ValueError):
        store.add([_vec([1, 0])], [])  # 1 vec, 0 metas


def test_load_returns_empty_when_no_files(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=2).load()
    assert store.is_empty()


def test_persisted_meta_is_valid_json(tmp_path):
    store = VectorStore(index_dir=tmp_path, dim=2)
    store.add([_vec([1, 0])], [{"file": "f.md", "heading": "H"}])
    store.save()
    raw = (tmp_path / "faiss_meta.json").read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed[0]["heading"] == "H"

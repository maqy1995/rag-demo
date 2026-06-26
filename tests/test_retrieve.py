"""Tests for src/rag_demo/retrieve.py 真向量检索 (MAQ-35)."""
from __future__ import annotations

from pathlib import Path

from rag_demo.llm import EmbedConfig, OpenAICompatibleEmbedder
from rag_demo.retrieve import retrieve
from rag_demo.vector import VectorStore


def _make_index(index_dir: Path) -> None:
    """构造测试用 FAISS index: 3 docs × 1 chunk each, dim=4."""
    store = VectorStore(index_dir=index_dir, dim=4)
    vectors = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.7, 0.7, 0.0, 0.0],
    ]
    metas = [
        {"source": "a.md", "file": "a.md", "heading": "A", "chunk_id": 0, "text": "alpha note"},
        {"source": "b.md", "file": "b.md", "heading": "B", "chunk_id": 0, "text": "beta note"},
        {"source": "c.md", "file": "c.md", "heading": "C", "chunk_id": 0, "text": "gamma note"},
    ]
    store.add(vectors, metas)
    store.save()


def test_retrieve_empty_index_returns_empty(tmp_path):
    """US4: index 为空 → 返 [] (RETRIEVE_EMPTY 路径)."""
    (tmp_path / "faiss.index").parent.mkdir(parents=True, exist_ok=True)
    hits = retrieve("query", index_dir=tmp_path, embedder=None, dim=4)
    assert hits == []


def test_retrieve_basic_returns_hits(tmp_path):
    """基本检索: 1 doc 命中."""
    _make_index(tmp_path)
    # embedder = None 时用 dummy 0 向量, 但本测试用真 embedder
    # 用 fake embedder: 总是返 [1, 0, 0, 0] (即匹配 a.md)
    class FakeEmbedder:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []
        def embed(self, texts):
            self.calls.append(texts)
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, text):
            self.calls.append([text])
            return [1.0, 0.0, 0.0, 0.0]
    fe = FakeEmbedder()
    hits = retrieve("any query", index_dir=tmp_path, top_k=2, embedder=fe, dim=4)
    assert len(hits) == 2
    assert hits[0].file == "a.md"
    assert hits[0].score > hits[1].score


def test_retrieve_snippet_truncated_at_200_chars(tmp_path):
    long_text = "x" * 500
    store = VectorStore(index_dir=tmp_path, dim=2)
    store.add(
        [[1.0, 0.0]],
        [{"source": "f.md", "file": "f.md", "heading": "H", "chunk_id": 0, "text": long_text}],
    )
    store.save()
    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]
        def embed_one(self, text):
            return [1.0, 0.0]
    hits = retrieve("q", index_dir=tmp_path, embedder=FakeEmbedder(), dim=2)
    assert len(hits[0].snippet) <= 200


def test_retrieve_source_uses_vault_uri(tmp_path):
    """Hit.source 是 vault:// URI."""
    _make_index(tmp_path)
    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, text):
            return [1.0, 0.0, 0.0, 0.0]
    hits = retrieve("q", index_dir=tmp_path, embedder=FakeEmbedder(), dim=4, vault_name="my-vault")
    assert hits[0].source.startswith("vault://my-vault/")


def test_retrieve_top_k_zero_returns_empty(tmp_path):
    _make_index(tmp_path)
    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, text):
            return [1.0, 0.0, 0.0, 0.0]
    hits = retrieve("q", index_dir=tmp_path, top_k=0, embedder=FakeEmbedder(), dim=4)
    assert hits == []


def test_retrieve_filters_kwarg_accepted(tmp_path):
    """filters kwarg 透传, 不强制实现 (v1 design §3.3)."""
    _make_index(tmp_path)
    class FakeEmbedder:
        def embed(self, texts):
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, text):
            return [1.0, 0.0, 0.0, 0.0]
    # 不应抛错
    hits = retrieve(
        "q", index_dir=tmp_path, embedder=FakeEmbedder(), dim=4,
        filters={"folder": "AI/"},
    )
    assert len(hits) >= 1


def test_retrieve_real_embedder_integration(tmp_path):
    """真 OpenAICompatibleEmbedder (mock SDK) 与 FAISS 端到端."""
    _make_index(tmp_path)
    # mock openai.OpenAI 让 embedder 不发真请求
    from unittest.mock import MagicMock, patch
    fake_resp = MagicMock()
    fake_resp.data = [
        MagicMock(embedding=[1.0, 0.0, 0.0, 0.0], index=0),
    ]
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = fake_resp
    with patch("openai.OpenAI", return_value=fake_client):
        cfg = EmbedConfig(
            provider="openai", model="text-embedding-3-small",
            base_url="https://api.openai.com/v1", api_key="test-key",
        )
        emb = OpenAICompatibleEmbedder(cfg)
        hits = retrieve("alpha", index_dir=tmp_path, top_k=1, embedder=emb, dim=4)
    assert len(hits) == 1
    assert hits[0].file == "a.md"


def test_retrieve_uses_module_level_embedder_when_not_passed(tmp_path):
    """MAQ-51: retrieve() 不传 embedder 时回落模块级单例 (set_embedder 注入的).

    之前 default embedder=None → 全 0 向量 → 0 分. 修复后: 启动期 set_embedder
    把真 embedder 注入, retrieve() 不传参时也能用它, 分数不再 0.
    """
    from rag_demo.retrieve import set_embedder, get_embedder

    _make_index(tmp_path)

    class _FakeEmb:
        def __init__(self) -> None:
            self.calls: list[str] = []
        def embed(self, texts):
            self.calls.extend(texts)
            return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, text):
            self.calls.append(text)
            return [1.0, 0.0, 0.0, 0.0]

    fake = _FakeEmb()
    set_embedder(fake)
    try:
        # 不传 embedder — 应该回落模块级单例
        hits = retrieve("anything", index_dir=tmp_path, top_k=2, dim=4)
        assert len(hits) == 2
        assert hits[0].file == "a.md"
        assert hits[0].score > hits[1].score
        # 确认 fake embedder 真的被调了 (不是全 0 向量路径)
        assert fake.calls == ["anything"]
    finally:
        set_embedder(None)  # 不污染后续测试
    assert get_embedder() is None


def test_retrieve_explicit_embedder_overrides_module_level(tmp_path):
    """MAQ-51: 显式 embedder 优先于模块级单例 (业务可临时覆盖)."""
    from rag_demo.retrieve import set_embedder

    _make_index(tmp_path)

    class _Global:
        def embed(self, texts): return [[0.0, 1.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, t): return [0.0, 1.0, 0.0, 0.0]

    class _Local:
        def embed(self, texts): return [[1.0, 0.0, 0.0, 0.0] for _ in texts]
        def embed_one(self, t): return [1.0, 0.0, 0.0, 0.0]

    set_embedder(_Global())
    try:
        # 显式传 _Local — 应该用 _Local (a.md), 不是 _Global (b.md)
        hits = retrieve("q", index_dir=tmp_path, top_k=1, embedder=_Local(), dim=4)
        assert hits[0].file == "a.md"
    finally:
        set_embedder(None)

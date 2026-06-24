# 当前设计

> multica-issue: MAQ-6
> 维护者：开发
> 状态：草稿

## 三段式 pipeline

```
            ┌──────────┐    ┌───────────┐    ┌──────────┐
   docs ──▶ │  ingest  │ ─▶ │ retrieve  │ ─▶ │ generate │ ─▶ answer
            └──────────┘    └───────────┘    └──────────┘
              load+chunk     embed+ANN          LLM call
```

- **ingest** (`src/rag_demo/ingest.py`) — 加载 `data/raw/` 下的 md/txt/rst，
  按 `--chunk-size` 切片，写到 `data/index/manifest.json`。
- **retrieve** (`src/rag_demo/retrieve.py`) — 当前是 stub，
  返回空列表。等 LLM 选型确定后替换。
- **generate** (`src/rag_demo/generate.py`) — 当前是 stub，
  把 retrieve 拿到的 chunks 拼起来。等 LLM 选型确定后替换。

## 待决项（→ adr/）

| 决策点 | 候选 | 状态 |
|--------|------|------|
| LLM 框架 | LangChain / LlamaIndex / 直裸调 SDK | 等产品开 issue |
| 向量库 | FAISS（CPU）/ Chroma / BM25 | 等产品开 issue |
| Embedding | OpenAI / 本地 bge-m3 / sentence-transformers | 等产品开 issue |
| 知识库来源 | 内部 markdown / 抓站 / 上传 PDF | 等产品开 issue |

每个决策落地前需要在 `docs/adr/NNNN-<slug>.md` 写一张 ADR。
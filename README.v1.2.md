# v1.2 Release Notes — 4 provider + 真 LLM/Embedding/Vector

> 日期：2026-06-25
> multica-issue: [MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
> 关联 ADR: [0001](mention://file/docs/adr/0001-llm-framework.md) / [0002](mention://file/docs/adr/0002-vector-store.md) / [0003](mention://file/docs/adr/0003-llm-embedding-source.md) / [0004](mention://file/docs/adr/0004-web-framework.md) / [0005](mention://file/docs/adr/0005-frontend-shape.md)

## 一句话总结

后端从 stub 状态变成真实可用：`retrieve` 走 FAISS + 真 Embedder，`generate` 调真 LLM（4 家 OpenAI 兼容 provider 任选），`ingest` 真 chunk + 真 embed + 写盘。

## 新增

- **5 条 ADR**（`docs/adr/0001~0005*.md`）— LLM 框架 / 向量库 / 4-provider 解耦 / Web / 前端 选型决议
- **`src/rag_demo/llm/`**（base.py + openai_compat.py + __init__.py）— `BaseLlmClient` / `BaseEmbedder` 抽象 + `OpenAICompatibleClient` / `OpenAICompatibleEmbedder` 单类覆盖 4 家
- **`src/rag_demo/chunker.py`** — 标题+长度混合切分，chunk_size=500 / overlap=80
- **`src/rag_demo/vector/__init__.py`** — FAISS IndexFlatIP + JSON metadata 持久化
- **`scripts/build_sample_index.py`** — 一键生成 `data/index.sample/`（预 embed 示例索引，给冷启动 demo 用）
- **`scripts/eval_recall.py`** — Recall@K 评估脚本（接受 `[(q, expected)]` 列表 → 输出 JSON 报告）
- **`tests/test_chunk.py` + `tests/test_vector.py` + `tests/test_retrieve.py` + `tests/test_eval_recall.py`** — 30+ 新断言
- **`data/raw.sample/` 扩到 5 篇** — 04-llm-providers.md + 05-cold-start-demo.md 加上
- **`static/index.html` 245 行真实 UI** — Vue 3 CDN + marked.js，Search+Ask 双面板 + 5 示例按钮 + 索引状态条
- **`pyproject.toml` 新增 extras** — `llm = [openai>=1.30]` + `vector = [faiss-cpu>=1.8]`

## 修改

- **`src/rag_demo/retrieve.py`** — 切真：加载 FAISS + embed query + search + 转 Hit
- **`src/rag_demo/generate.py`** — 切真：`_call_llm` 走 `BaseLlmClient.stream()` 流式；模块级 `set_llm_client()` 注入
- **`src/rag_demo/ingest.py`** — 切真：chunker + embedder + FAISS 写盘；保留 NB2 building 中间态 + NB3 fallback
- **`src/rag_demo/errors.py`** — 加 `EMBEDDING_FAIL` 错误码（LLM 复用 `GENERATE_LLM_FAIL`）
- **`.env.example`** — 加 4 个 `*_API_KEY` 字段（分别命名）
- **测试** — 80 → **145 passed**（净增 65 断言）

## 4 家 provider 清单（v1 必支持）

| Provider | base_url | LLM model | Embedding model | API key env |
|---|---|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` | `OPENAI_API_KEY` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4-flash` | `embedding-2` | `ZHIPU_API_KEY` |
| MiniMax | `https://api.MiniMax.chat/v1/` | `abab-7-chat` | `embo-01` | `MIMAX_API_KEY` |
| 小米 Mimo | `https://api.mimo.xiaomi.com/v1/` | `mimo-7b` | `mimo-embedding` | `MIMO_API_KEY` |

**关键约束（owner 拍板）**：
- **embedding 与 LLM provider 解耦**（可独立选）
- **不考虑本地 Ollama**（不再有 fallback）

## Quick start

```bash
git clone https://github.com/maqy1995/rag-demo
cd rag-demo
uv sync --extra llm --extra vector --extra web --extra dev
cp .env.example .env
# 编辑 .env 填 1-4 个 *API_KEY
cp config.example.yaml config.yaml
# 编辑 config.yaml 设 vault.path / 选 LLM provider / 选 Embedding provider

# 启动 (主入口)
uv run rag-demo up
# 浏览器开 http://127.0.0.1:8000/
```

## 不再需要本地 Ollama

- ❌ `ollama` 不再是默认 provider
- ❌ 没有 Ollama fallback
- ✅ 直接走 OpenAI 兼容远程 API
- ⚠️ 首次启动需在 `.env` 设至少 1 个 `*_API_KEY`，否则 `AppError(401)` fast-fail

## 下一轮

- MAQ-42: 端到端 cold-start 30s 计时测试（uvicorn subprocess）
- MAQ-43: 最终代码 review（dev 自审 + Reviewer 通看）
- MAQ-44: README 重写（v1.2 完整版合并入主 README.md）

## 测试统计

```
$ uv run pytest -q
145 passed, 1 warning in 8.76s

$ uv run ruff check src tests
All checks passed!
```

## GitHub commits（v1.2）

- `dd21b10` — feat(MAQ-26): ADR-0001 落地 + LLM 模块（Reviewer 提前实现）
- `275f0f5` — feat(MAQ-33~37): 真接入 Chunker / VectorStore / retrieve / generate / ingest
- `486f998` — docs(MAQ-27~30): ADR-0002/0003/0004/0005
- (pending) — feat(MAQ-38~41): sample data + sample index + eval_recall + UI
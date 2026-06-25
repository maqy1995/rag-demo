# rag-demo · 本地知识库问答

> **一句话**：把一堆 Markdown 笔记喂给本地向量索引，问中文问题，从你的笔记里找答案 —— 后端用 **4 家 OpenAI 兼容远程 LLM** 任选其一，**完全本地数据**（笔记 / 索引 / 日志都在你机器的 `data/` 目录）。
>
> **GitHub**：[maqy1995/rag-demo](https://github.com/maqy1995/rag-demo)
> **Multica 项目**：`知识库问答`
> **当前版本**：v1.2（4 provider + 真 LLM / Embedding / Vector）

---

## 目录

- [它是做什么的](#它是做什么的)
- [特性一览](#特性一览)
- [快速上手（5 分钟）](#快速上手5-分钟)
- [Provider 切换](#provider-切换)
- [Embedding / LLM 解耦](#embedding--llm-解耦)
- [性能预期](#性能预期)
- [常见问题（FAQ）](#常见问题faq)
- [部署指南](#部署指南)
- [使用说明](#使用说明)
- [HTTP API 参考](#http-api-参考)
- [配置项](#配置项)
- [目录结构](#目录结构)
- [故障排查](#故障排查)
- [开发协作（Multica + 4 角色）](#开发协作multica--4-角色)

---

## 它是做什么的

`rag-demo` 是一个**本地数据 / 远程 LLM** 的知识库问答（Knowledge-Base QA）原型：

1. 你把 Markdown / TXT 笔记放进 `data/raw/`（你的 "vault"）。
2. 启动后，后台会扫描 vault → 切分文本 → 调 Embedding API → 写 FAISS 索引 (`data/index/`)。
3. 你打开浏览器问"微服务治理是什么？" → 系统 embed 你的问题 → FAISS 召回相关片段 → 喂给远程 LLM → 拿到中文回答 + 来源引用。

### v1.2 与 v0.x 的区别

| 维度 | v0.x（v1.1） | v1.2 |
|------|-------------|------|
| retrieve | 永远返回空（stub） | **真** FAISS IndexFlatIP + 真 Embedder |
| generate | 固定前缀字符串 | **真** 流式调远程 LLM（4 家任选） |
| ingest | 空壳 | **真** chunker + 真 embed + 持久化 |
| LLM provider | ollama（本地） | 4 家 OpenAI 兼容远程 API（owner 拍板不再走本地） |
| Embedding provider | ollama（与 LLM 绑定） | 与 LLM **解耦**，可独立选 |
| 前端 | 占位 HTML | **真** Vue 3 双面板 UI + 5 示例问题 + 索引状态条 |
| 测试 | 80 passed | **145 passed** + Recall@K 评估脚本 |

> 📌 **数据隐私**：vault 原文、FAISS 索引、使用日志全部落在你机器的 `data/` 目录，**不**上传云端。
> 调用 LLM / Embedding 时**仅**把相关片段（不含原始 vault 路径以外的元数据）发给远程 API。

> ⚠️ **首次启动需 API key**：v1.2 起不再有本地 Ollama fallback。第一次跑必须先在 `.env` 填至少 1 个 `*_API_KEY`，否则 `AppError(401)` fast-fail。

---

## 特性一览

| 能力 | 状态 | 说明 |
|------|------|------|
| 4 家 OpenAI 兼容 LLM | ✅ | OpenAI / 智谱 GLM / MiniMax / 小米 Mimo（MAQ-28 ADR-0003 拍板） |
| LLM / Embedding 解耦 | ✅ | `generate.llm.provider` 与 `generate.embedding.provider` 独立 |
| 真 FAISS 检索 | ✅ | IndexFlatIP + 余弦相似度 + JSON metadata 持久化 |
| 真 Embedder | ✅ | `BaseEmbedder.embed(texts) -> list[list[float]]` |
| 真流式 LLM | ✅ | `BaseLlmClient.stream(...)` 逐 token yield → SSE `event: token` |
| FastAPI 9 端点 | ✅ | health / config / search / chat (非流式 + SSE) / ingest / usage |
| 后台 ingest | ✅ | 服务启动时**后台线程**跑全量索引，API 立刻可用 |
| 冷启动 demo | ✅ | `data/raw.sample/` 5 篇 + `data/index.sample/` 预 embed 索引，30s 内前端可见 5 示例按钮 |
| Recall@K 评估 | ✅ | `scripts/eval_recall.py` 接受 `[(q, expected)]` → 输出 JSON 报告 |
| 真实前端 UI | ✅ | `static/index.html` Vue 3 CDN + marked.js，Search + Ask 双面板 + 5 示例按钮 |
| 决策码 | ✅ | `RETRIEVE_EMPTY` / `NOT_DEFINED` / `GENERATED` 三态，HTTP 200 自描述 |
| 配置脱敏 | ✅ | `GET /api/config` 只回显非敏感字段，API key 走 `.env` 不入配置 |

---

## 快速上手（5 分钟）

> 假设你是 macOS 用户，已经装了 [Homebrew](https://brew.sh) 和 [uv](https://docs.astral.sh/uv/)。
> 没有 uv 的话：`brew install uv`（30 秒）。

```bash
# 0) 拉代码
git clone https://github.com/maqy1995/rag-demo.git
cd rag-demo

# 1) 装依赖：LLM/Embedding SDK + FAISS 向量库 + Web 入口 + 开发套件
uv sync --extra llm --extra vector --extra web --extra dev

# 2) 准备 .env 并填 1-4 个 *API_KEY（填你打算用的那几家）
cp .env.example .env
$EDITOR .env
# 例：只用 OpenAI 就填 OPENAI_API_KEY=sk-...；其它三家留空

# 3) 准备 config.yaml（cold-start 不改也能跑）
cp config.example.yaml config.yaml

# 4) 健康检查：确认 Python / git / uv / 配置 都就位
uv run rag-demo doctor

# 5) 启动服务（默认 http://127.0.0.1:8000，后台自动 ingest）
uv run rag-demo up

# 6) 打开浏览器
open http://127.0.0.1:8000
```

你会看到 5 篇样例笔记（欢迎 / 微服务治理 / 常见问题 / LLM Provider / 冷启动 demo）已经加载，5 条示例问题在界面上等着。试着问：

```
微服务治理是怎么定义的？
怎么切换 LLM provider？
冷启动 demo 是怎么做的？
```

> 想跑自己的笔记？把 `.md` 文件丢进 `data/raw/`，再 `uv run rag-demo ingest --data ./data/raw --index ./data/index`，重启 `up` 即可。

### extras 说明

| extra | 装什么 | 什么时候需要 |
|-------|--------|--------------|
| `llm` | `openai` SDK（4 家都用它） | **必装** —— 没有它 `BaseLlmClient` 没法实例化 |
| `vector` | `faiss-cpu` | **必装** —— 真检索走 FAISS IndexFlatIP |
| `web` | (空 alias) | 可选 —— FastAPI / uvicorn 已在默认 deps，这里只是语义化 alias |
| `dev` | `pytest` / `ruff` / `mypy` | 改代码 / 跑测试时 |
| `faiss` / `chroma` | 同 `vector`（细粒度版本） | 想要 Chroma 时用 `--extra chroma` 替 `vector` |
| `langchain` / `llamaindex` | 框架 SDK | **不需要** —— v1.2 直裸 OpenAI SDK，不依赖框架 |
| `anthropic` | Anthropic SDK | **不需要** —— v1.2 锁 4 家 OpenAI 兼容，不含 Anthropic |

---

## Provider 切换

v1.2 支持 **4 家 OpenAI 兼容**远程 LLM / Embedding provider，在 `config.yaml` 改 `generate.llm.provider` 与 `generate.embedding.provider` 即可。

> ⚠️ **不再支持本地 Ollama**（owner 拍板，MAQ-25 评论）。新增 provider 必须先写 [ADR-0003](docs/adr/0003-llm-embedding-source.md) 决议。

### 4 家 provider 速查表

| Provider | base_url | LLM model（推荐入门） | Embedding model | API key env |
|----------|----------|----------------------|-----------------|-------------|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` | `OPENAI_API_KEY` |
| **智谱 GLM** | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4-flash` | `embedding-2` | `ZHIPU_API_KEY` |
| **MiniMax** | `https://api.MiniMax.chat/v1/` | `abab-7-chat` | `embo-01` | `MIMAX_API_KEY` |
| **小米 Mimo** | `https://api.mimo.xiaomi.com/v1/` | `mimo-7b` | `mimo-embedding` | `MIMO_API_KEY` |

### 配置示例

#### 1. 全 OpenAI（最省心）

```yaml
generate:
  llm:
    provider: openai
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
  embedding:
    provider: openai
    model: text-embedding-3-small
```

`.env` 只需 `OPENAI_API_KEY=sk-...`。

#### 2. 智谱 GLM 全栈（国内直连，无需代理）

```yaml
generate:
  llm:
    provider: zhipu
    model: glm-4-flash
    base_url: https://open.bigmodel.cn/api/paas/v4/
  embedding:
    provider: zhipu
    model: embedding-2
```

`.env` 只需 `ZHIPU_API_KEY=...`。

#### 3. MiniMax

```yaml
generate:
  llm:
    provider: minimax
    model: abab-7-chat
    base_url: https://api.MiniMax.chat/v1/
  embedding:
    provider: minimax
    model: embo-01
```

`.env` 只需 `MIMAX_API_KEY=...`。

#### 4. 小米 Mimo

```yaml
generate:
  llm:
    provider: mimo
    model: mimo-7b
    base_url: https://api.mimo.xiaomi.com/v1/
  embedding:
    provider: mimo
    model: mimo-embedding
```

`.env` 只需 `MIMO_API_KEY=...`。

切换 provider **不需要改代码** —— `OpenAICompatibleClient(LLMConfig)` 构造时把 `base_url` / `api_key` 喂给 `openai.OpenAI(...)`，差异只在 config。

---

## Embedding / LLM 解耦

v1.2 的一大设计：**LLM provider 和 Embedding provider 是两个独立字段**，可以混搭。

### 为什么要解耦？

- **成本**：Embedding 调用量（每个 chunk 1 次）远大于 LLM（每次提问 1 次），用便宜 + 快的 Embedding + 强 LLM 是常见模式。
- **质量**：不同 provider 的 Embedding 维度不同（OpenAI 1536 / 智谱 1024 / Mimo 自定），混搭时要保证 FAISS 索引的 dim 与 Embedder 一致。
- **可用性**：某家 Embedding 挂了，临时换另一家不用动 LLM。

### 混搭示例

#### OpenAI LLM + 智谱 Embedding（最常见的省钱组合）

```yaml
generate:
  llm:
    provider: openai
    model: gpt-4o-mini
  embedding:
    provider: zhipu
    model: embedding-2      # ⚠️ 1024 维
```

`.env` 需**同时**设置 `OPENAI_API_KEY` 与 `ZHIPU_API_KEY`。

#### 智谱 LLM + OpenAI Embedding

```yaml
generate:
  llm:
    provider: zhipu
    model: glm-4-flash
  embedding:
    provider: openai
    model: text-embedding-3-small   # 1536 维
```

### 约束：维度必须匹配

FAISS 索引在首次 ingest 时**锁死维度**（来自第一个 Embedder 的输出）。换 Embedding provider 后必须**全量重建索引**：

```bash
rm -rf data/index
uv run rag-demo ingest --full
```

否则 `IndexFlatIP` 会抛 `RuntimeError: dim mismatch`。

---

## 性能预期

> 数字基于 macOS M2 / 默认 FAISS IndexFlatIP / 网络 50 Mbps 的粗略估算。
> 真实数字受 Embedding API RTT / chunk 大小 / 并发数影响 ±50%。

| 笔记规模 | 冷启动 ingest | 检索 P50 | 端到端问答 P50 |
|----------|--------------|----------|----------------|
| **100 篇**（≈ 5000 chunks） | 5-15 min | < 100 ms | 1-3 s（含 LLM 流式首 token） |
| **500 篇**（≈ 25000 chunks） | 25-60 min | < 200 ms | 1-3 s |
| **1000 篇**（≈ 50000 chunks） | 30-90 min | < 500 ms | 1-3 s |
| **5000+ 篇** | 不推荐 | 500 ms-2 s | 1-3 s（**先换 HNSW 或切换 Chroma**） |

### 关键瓶颈

- **Ingest 阶段**：Embedding API 是网络密集型 —— 1000 篇 × 50 chunks = 50,000 次 Embedding 调用。
  - OpenAI tier 1：~3-5 QPS → **5-10 hours**（开 --extra 并发可拉到 30+ QPS）
  - 智谱 GLM：~10-20 QPS → **1-2 hours**
  - **强烈建议**：用智谱 / Mimo 做 Embedding（便宜 + 高 QPS），用 OpenAI 做 LLM（质量高）。
- **检索阶段**：FAISS IndexFlatIP 是暴力搜索，10k 级别无压力，100k+ chunks 考虑迁移到 HNSW。
- **生成阶段**：LLM 流式首 token 取决于 provider 内部 latency，通常 200-800 ms。

### 提速技巧

```bash
# 1. 临时跳过 ingest（调试 UI 用）
uv run rag-demo up --no-ingest

# 2. 增量 ingest（只处理新增 / 修改的文件）
uv run rag-demo ingest  # 默认 full=false, 只 diff

# 3. 调小 chunk_size 减少总 chunk 数（牺牲召回换速度）
# config.yaml:
#   ingest:
#     chunk_size: 300
#     chunk_overlap: 50
```

---

## 常见问题（FAQ）

### Q1: 我只有 OpenAI 一个 key，能跑吗？

**能**。`.env` 只填 `OPENAI_API_KEY=sk-...` 即可，其它三家留空。`config.yaml` 默认就是 OpenAI + OpenAI Embedding。

### Q2: 怎么切换到另一家 provider？

三步：
1. `.env` 填对应的 `*_API_KEY`（如 `ZHIPU_API_KEY=...`）。
2. `config.yaml` 改 `generate.llm.provider` / `generate.embedding.provider`。
3. **重建索引**（如果换 Embedding provider）：
   ```bash
   rm -rf data/index && uv run rag-demo ingest --full
   ```
4. 重启 `uv run rag-demo up`。

### Q3: 我不想用 OpenAI 兼容的，能接 Anthropic / Gemini / Ollama 吗？

**v1.2 不支持**。owner 拍板锁死 4 家 OpenAI 兼容（MAQ-25 评论）。新增 provider 必须先在 [docs/adr/](docs/adr/) 写 ADR 决议，Accepted 后再加 adapter —— 当前 `BaseLlmClient` 抽象已经留好扩展点。

### Q4: 冷启动 30 秒是什么？

PRD 约束：从前端 `index.html` 首字节起到"前端看到 5 条示例按钮可点击"，阈值 30 秒（mock 后端 5 秒）。
v1.2 实现：
- 后台线程跑全量 ingest，**不阻塞** API 启动。
- 前端拿到 `data/index.sample/`（预 embed 的 5 篇示例索引）先跑端到端。
- 用户 vault 索引完成后 SSE / 轮询通知前端解锁"问你的笔记"。

超时记入 `data/usage/local-{date}.jsonl` 的 `cold_start_abandoned` 事件。

### Q5: 我加了笔记，怎么增量更新索引？

```bash
# 默认 full=false, 走增量（diff mtime + hash）
uv run rag-demo ingest
# 或全量重建
uv run rag-demo ingest --full
```

也可以通过 API：`curl -X POST http://127.0.0.1:8000/api/ingest -d '{"full": false}'`。

### Q6: 怎么调试 retrieve / generate 的中间结果？

```bash
# 1. 查索引状态
curl http://127.0.0.1:8000/api/index/status | jq .

# 2. 纯检索（不调 LLM）
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"微服务治理","top_k":5}' | jq .

# 3. 看决策码（RETRIEVE_EMPTY / NOT_DEFINED / GENERATED）
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"微服务治理是什么？"}' | jq .decision

# 4. Recall@K 评估
uv run python scripts/eval_recall.py --queries '[("Q1", "expected source 1"), ...]'
```

更深的调试（log level / 抓网络包 / 看 Embedding 真实返回值）见 [§ 故障排查](#故障排查)。

---

## 部署指南

### 1. 环境要求

| 项 | 要求 | 备注 |
|----|------|------|
| OS | macOS / Linux | Windows 通过 WSL2 也可，尚未官方验证 |
| Python | 3.12.x | **必须**用 uv 装，不建议用系统 Python |
| 磁盘 | ≥ 500 MB + 索引空间 | 1000 篇 ≈ 200 MB FAISS 索引 |
| 内存 | ≥ 1 GB | IndexFlatIP 10k chunks 约占 200 MB |
| 网络 | 持续联网 | 每次 embed / chat 都要打远程 API |

### 2. 安装 Python 3.12（一次性）

```bash
uv python install 3.12
```

### 3. 安装项目依赖

```bash
cd ~/Code/rag-demo
uv sync --extra llm --extra vector --extra web --extra dev
```

> 默认会装：`fastapi` / `uvicorn` / `pydantic` / `httpx` / `pyyaml` / `python-dotenv` + `openai`（LLM SDK）+ `faiss-cpu`（向量库）+ 开发套件 `pytest` / `ruff` / `mypy`。
>
> 想要 Chroma 替 FAISS：`uv sync --extra llm --extra chroma --extra web --extra dev`

### 4. 准备数据 & 配置

```bash
# 4.1 准备 .env（敏感字段）
cp .env.example .env
# 编辑 .env，填 1-4 个 *API_KEY

# 4.2 准备 config.yaml（非敏感字段）
cp config.example.yaml config.yaml
# 编辑 config.yaml，设 vault.path / 选 LLM provider / 选 Embedding provider

# 4.3 准备 vault（你的笔记）
mkdir -p data/raw
cp -r ~/Documents/my-notes/*.md data/raw/
```

不准备也行 —— cold-start 模式自动 fallback 到 `data/raw.sample/` 5 篇样例笔记。

### 5. 启动服务

#### 选项 A：FastAPI + 后台 ingest（推荐）

```bash
uv run rag-demo up --host 127.0.0.1 --port 8000
```

服务会做 5 件事：

1. 加载 `config.yaml`（不存在则 fallback 到 `config.example.yaml` → 内置默认）
2. **后台线程**启动全量 ingest（不阻塞 API 启动）
3. `uvicorn` 启动 FastAPI，监听 `--host: --port`
4. 收到 `SIGINT` / `SIGTERM` 后等 ingest 跑完再优雅退出
5. `--no-ingest` 可跳过 ingest（仅用于调试 UI）

#### 选项 B：先手动 ingest，再起服务

```bash
uv run rag-demo ingest --data ./data/raw --index ./data/index
uv run rag-demo up --no-ingest
```

> `web` 是 `up` 的别名，习惯用 IDE / docker-compose 的同学可以继续打 `web`。

### 6. 验证服务跑起来了

```bash
# 健康检查
curl http://127.0.0.1:8000/api/health
# → {"ok": true}

# 看当前生效的配置（脱敏，不含 API key）
curl http://127.0.0.1:8000/api/config | jq .

# 看索引状态
curl http://127.0.0.1:8000/api/index/status | jq .
```

---

## 使用说明

### 浏览器（推荐）

打开 `http://127.0.0.1:8000`，看到 Vue 3 双面板 UI：

- **左侧 Search**：纯检索（不调 LLM），看 FAISS 召回的 top-K 片段。
- **右侧 Ask**：端到端问答（检索 + LLM 流式生成）。
- **顶部状态条**：当前索引状态 / chunk 数 / 上次构建时间。
- **5 条示例按钮**：cold-start demo 入口，点击直接发问。

### 命令行

```bash
# 一次性问一个问题（不走 HTTP，直接调 retrieve + answer）
uv run rag-demo ask "微服务治理是什么？"

# 跑 Recall@K 评估
uv run python scripts/eval_recall.py --queries eval/sample.json
```

### HTTP API（详见下一节）

```bash
# 流式问答（SSE）
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"微服务治理是什么？","top_k":5}'
```

---

## HTTP API 参考

> 完整字段约定见 `docs/dev/design.md` §3.6 / §6.3。错误壳：L3 抛 `AppError` → `JSONResponse(400/500/503)`，body 为 `{"error": {"code": ..., "message": ..., "stage": ...}}`。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET`  | `/api/health`           | 健康检查，返回 `{"ok": true}` |
| `GET`  | `/api/config`           | 脱敏后的生效配置（不含 API key / secret） |
| `GET`  | `/api/index/status`     | 读 `data/index/status.json`：`state` / `files_total` / `chunks_total` / `last_built_at` 等 |
| `POST` | `/api/search`           | 纯检索，不调 LLM；body `{query, top_k, filters?}`；返回 `{hits: [...]}` |
| `POST` | `/api/chat`             | 非流式问答；body `{question, top_k, filters?, selected_sources?}`；返回 `{answer, sources, decision, cost_ms}` |
| `POST` | `/api/chat/stream`      | SSE 流式问答；事件：`token` / `sources` / `meta` / `error` |
| `POST` | `/api/ingest`           | 触发全量/增量重建；body `{full, data?, index?}`；返回 `{ok, stats}` |
| `POST` | `/api/usage`            | 埋点日志，写到 `data/usage/local-YYYY-MM-DD.jsonl` |
| `GET`  | `/api/usage/query`      | 自检：今日事件数 + cold-start 放弃数 |
| `GET`  | `/`                     | 静态 `index.html`（Vue 3 UI） |

### 决策码

`/api/chat` 和 `/api/chat/stream` 的 `decision` 字段三态：

| 值 | 含义 | LLM 是否被调 |
|----|------|--------------|
| `RETRIEVE_EMPTY`  | FAISS 召回为空（vault 里没相关内容） | ❌ 不调 |
| `NOT_DEFINED`     | 召回到了片段但没有"明确定义"（如 query 后没接"是 / 为 / 指"等定义短语） | ❌ 不调 |
| `GENERATED`       | 命中且定义充分，走 LLM 生成 | ✅ 调 |

`RETRIEVE_EMPTY` / `NOT_DEFINED` 走 200 + `decision` 字段，**不**走错误壳 —— 这是设计上的有意决定，让前端能用统一结构处理兜底文案。

### SSE 事件格式

```
event: token
data: {"delta": "微服务"}

event: token
data: {"delta": "治理是..."}

event: sources
data: {"sources": [{"source": "vault://...", "file": "02-microservices.md", ...}]}

event: meta
data: {"retrieved": 5, "decision": "GENERATED", "cost_ms": {"retrieve": 12, "generate": 340}}
```

---

## 配置项

### 配置文件加载顺序

`load_config()` 优先级：

1. `config.yaml`（项目根，**不进 git**）
2. `config.example.yaml`（项目根，**进 git**，作为示例）
3. 内置默认值（`src/rag_demo/config.py` 的 `_DEFAULTS`）

`.env` 通过 `python-dotenv` 注入到 `os.environ`，**仅**用于敏感字段（API key / base URL），不进 `AppConfig`。

### 完整配置项（默认值）

```yaml
vault:
  path: ""                 # 你的笔记根目录；空 → cold-start 走 data/raw.sample/
  name: "my-notes"         # vault 名称（用于 vault:// URI）
  include_extensions: [".md", ".txt"]  # 扫描哪些后缀

ingest:
  chunk_size: 500          # 切分大小（字符）
  chunk_overlap: 80        # 切分重叠（必须 < chunk_size）
  full: true               # 全量 / 增量

retrieve:
  top_k: 5                 # 默认返回前 K 个片段
  filters: {}              # 预留：按 metadata 过滤

generate:
  llm:
    provider: "openai"     # openai | zhipu | minimax | mimo
    model: "gpt-4o-mini"
    base_url: "https://api.openai.com/v1"
  embedding:
    provider: "openai"     # 与 llm.provider 独立，可不同
    model: "text-embedding-3-small"
  defined_check_pattern: ""  # 预留：自定义"明确定义"判定正则

web:
  host: "127.0.0.1"
  port: 8000
  index_dir: "./data/index"

usage:
  enabled: true            # 是否写 usage 日志
  dir: "./data/usage"
```

### 环境变量（敏感字段）

```bash
# .env 示例 — 填你打算用的那几家
OPENAI_API_KEY=sk-...
ZHIPU_API_KEY=...
MIMAX_API_KEY=...
MIMO_API_KEY=...

# Multica runtime（仅在 demo 调用 multica API 时需要，可选）
MULTICA_TOKEN=
MULTICA_BASE_URL=https://api.multica.ai
```

`.env` 在 `.gitignore` 里，**永远不会**被 commit。

---

## 目录结构

```
rag-demo/
├── README.md                # 你正在读的文件（v1.2 重写）
├── README.v1.2.md           # v1.2 发布说明草稿（已迁 docs/release-notes/v1.2.md）
├── docs/
│   ├── release-notes/
│   │   └── v1.2.md          # v1.2 发布说明（含 19 子 issue 摘要）
│   ├── adr/                 # 跨角色架构决策记录（0001~0005）
│   ├── product/             # 产品：backlog + spec
│   ├── dev/                 # 开发：design + runbooks
│   ├── review/              # 审查员：checklists + reports
│   ├── envops/              # 环境准备与部署：environments + deployment + runbook
│   ├── handoffs/            # 跨角色交接单
│   └── templates/           # 空白模板
├── pyproject.toml           # uv-managed；extras: llm / vector / web / dev / faiss / chroma
├── .python-version          # 3.12
├── .env.example             # 复制为 .env 并填入 4 家 *API_KEY
├── config.example.yaml      # 配置示例（不进真实 key）
│
├── src/rag_demo/            # 三段式 pipeline + 配置 + 错误壳
│   ├── __main__.py          # CLI: ingest / ask / doctor / up / web
│   ├── chunker.py           # 标题+长度混合切分
│   ├── retrieve.py          # FAISS 检索
│   ├── generate.py          # 决策链 + BaseLlmClient 注入
│   ├── ingest.py            # 扫描 + 切分 + embed + 写索引
│   ├── validate.py          # "明确定义"判定（纯函数）
│   ├── config.py            # AppConfig + load_config
│   ├── errors.py            # AppError + ERROR_CODES
│   ├── vault_uri.py         # vault:// 协议编解码
│   ├── logging_setup.py     # 日志
│   ├── llm/                 # v1.2 新增：BaseLlmClient + OpenAICompatibleClient
│   ├── vector/              # v1.2 新增：FAISS 封装 + 持久化
│   └── web/
│       ├── main.py          # FastAPI 9 端点
│       └── static/          # Vue 3 UI + 5 示例按钮 + 索引状态条
│
├── static/                  # 顶层 static 目录（如有 init_static.py 产物）
├── tests/                   # pytest：145 passed + eval_recall + e2e cold-start 30s
├── data/
│   ├── raw/                 # 你的笔记（git ignore，自己放）
│   ├── raw.sample/          # 5 篇 demo 笔记（git 跟踪，冷启动 fallback 用）
│   ├── index/               # 索引输出（git ignore）
│   ├── index.sample/        # 预 embed 索引（git 跟踪，冷启动 demo 用）
│   └── usage/               # 本地埋点日志（git ignore）
│
├── scripts/
│   ├── doctor.sh            # 包装 rag-demo doctor
│   ├── init_static.py       # 一次性生成占位 index.html（dev-time）
│   ├── build_sample_index.py  # 重建 data/index.sample/ 预 embed 索引
│   └── eval_recall.py       # Recall@K 评估
│
└── docs/                    # 4 角色协作通道（同上）
```

---

## 故障排查

### 端口被占用

```bash
# 换个端口
uv run rag-demo up --port 8765
```

### `uv sync` 第一次跑失败：`host unreachable`

`uv` 没读 git 的 `http.proxy`，直连 PyPI 被防火墙拦。修复（一次性）：

```bash
mkdir -p ~/.config/uv
cat > ~/.config/uv/uv.toml <<EOF
http-proxy = "http://127.0.0.1:7897"
https-proxy = "http://127.0.0.1:7897"
EOF
```

> 详见 `docs/envops/runbook.md` 第一条记录（MAQ-6）。

### 服务起不来：`AppError(401, GENERATE_LLM_FAIL)`

`.env` 没填对应 provider 的 `*API_KEY`，或 key 失效。修复：

```bash
# 1. 确认 .env 存在
ls -la .env
# 2. 确认 key 设置了（输出非空）
grep -E '^[A-Z]+_API_KEY=.+$' .env
# 3. 如果只配了 OpenAI，确保 config.yaml 里 provider=openai
grep -E '^    provider:' config.yaml
```

### 服务起不来：`IndexFlatIP: dim mismatch`

换 Embedding provider 后没重建索引。修复：

```bash
rm -rf data/index
uv run rag-demo ingest --full
uv run rag-demo up
```

### 索引卡在 `state=building`

```bash
# 看进度
curl http://127.0.0.1:8000/api/index/status | jq .
# → current_progress = { "done": 3, "total": 12 }  说明还在跑
# → state=idle  说明跑完了
```

如果一直卡住，看 `data/index/status.json` 的 `last_built_at` 字段是不是很久以前的 —— 很可能是后台 ingest 线程崩了，重启服务即可。

### `/api/chat` 一直返回 `RETRIEVE_EMPTY`

```bash
# 1. ingest 跑通了吗
curl http://127.0.0.1:8000/api/index/status | jq .state
# 应该看到 "idle"

# 2. 索引里到底有没有相关片段
curl -X POST http://127.0.0.1:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"微服务治理","top_k":5}' | jq .

# 3. 跑 Recall@K 评估，看召回质量
uv run python scripts/eval_recall.py --queries eval/sample.json
```

### 怎么加我自己的笔记

```bash
# 1. 复制进去
cp ~/my-note.md data/raw/

# 2. 重建索引（增量即可）
uv run rag-demo ingest

# 3. 重启服务
# Ctrl+C 停掉 up，再跑一次 uv run rag-demo up
```

### IDE 找不到解释器

VS Code / Cursor / PyCharm 请把 interpreter 指向：

```
~/Code/rag-demo/.venv/bin/python
```

**不要**用 `/usr/bin/python3` 或 `miniconda3/bin/python3`，会污染你其他 Python 工程。

---

## 开发协作（Multica + 4 角色）

> 这一节是给**接手的开发者 / agent** 看的，普通用户可以跳过。

本项目用 **Multica + Claude Code + Codex** 多 agent 协作流开发，分为 4 个角色：

| 角色 | 写 | 读 | 主要入口 |
|------|----|----|---------|
| 产品 | `docs/product/` | `docs/adr/` | [`docs/product/README.md`](docs/product/README.md) |
| 开发 | 代码 + `docs/dev/` | spec + ADR | [`docs/dev/README.md`](docs/dev/README.md) |
| 审查员 | `docs/review/reports/` | 全部 PR | [`docs/review/README.md`](docs/review/README.md) |
| 环境准备与部署 | `docs/envops/` + handoff | 全部 | [`docs/envops/README.md`](docs/envops/README.md) |

跨角色交接走 `docs/handoffs/<date>-from-A-to-B-<slug>.md` 模板。
架构分歧先在 `docs/adr/NNNN-<slug>.md` 写 ADR 决议，Accepted 后全员遵循。

### v1.2 关键 ADR

- [ADR-0001 LLM 框架](docs/adr/0001-llm-framework.md) — 直裸 OpenAI 兼容 SDK + 极薄抽象
- [ADR-0002 向量库](docs/adr/0002-vector-store.md) — FAISS IndexFlatIP + JSON metadata
- [ADR-0003 LLM/Embedding 数据源](docs/adr/0003-llm-embedding-source.md) — 4 家 OpenAI 兼容远程 API，锁死
- [ADR-0004 Web 框架](docs/adr/0004-web-framework.md) — FastAPI + uvicorn
- [ADR-0005 前端形态](docs/adr/0005-frontend-shape.md) — Vue 3 CDN + marked.js，**不**用框架

### Multi-agent 工具链

- **Claude Code** 在 multica workspace 跑，负责计划 / 审查 / 协调。
- **Codex CLI** 在同仓库执行实现：`codex exec "<task>"`。
- **Multica** 是 durable record，本仓库已通过 `multica project resource add` 绑到 `知识库问答` 项目下。

### 推到 GitHub

```bash
gh auth login                              # 一次性
gh repo create maqy1995/rag-demo --public --source=. --remote=origin --push
```

详细步骤见 [`docs/github-setup.md`](docs/github-setup.md)。

---

## License

MIT © maqy

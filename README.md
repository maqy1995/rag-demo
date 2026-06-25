# rag-demo · 本地知识库问答

> **一句话**：把一堆 Markdown 笔记喂给本地向量索引，问中文问题，从你的笔记里找答案——完全本地，零云端依赖。
>
> **GitHub**：[maqy1995/rag-demo](https://github.com/maqy1995/rag-demo)
> **Multica 项目**：`知识库问答`

---

## 目录

- [它是做什么的](#它是做什么的)
- [特性一览](#特性一览)
- [快速上手（5 分钟）](#快速上手5-分钟)
- [部署指南](#部署指南)
- [使用说明](#使用说明)
- [HTTP API 参考](#http-api-参考)
- [配置项](#配置项)
- [目录结构](#目录结构)
- [故障排查](#故障排查)
- [开发协作（Multica + 4 角色）](#开发协作multica--4-角色)

---

## 它是做什么的

`rag-demo` 是一个**本地运行**的知识库问答（Knowledge-Base QA）原型：

1. 你把 Markdown / TXT 笔记放进 `data/raw/`（你的 "vault"）。
2. 启动后，后台会扫描 vault → 切分文本 → 写入本地索引 (`data/index/`)。
3. 你打开浏览器问"微服务治理是什么？" → 系统从索引里挑出相关片段 → 喂给 LLM → 拿到中文回答 + 来源引用。

> 📌 **数据隐私**：vault 原文、索引、使用日志全部落在你机器的 `data/` 目录，**不**上传任何云端。默认 LLM 是本地 ollama (`qwen2.5`)，断网也能跑。

> ⚠️ **当前阶段**：这是 v0.1 原型，retrieval 与 generation 都还是**桩（stub）**实现——索引写入是空壳、检索永远返回空、LLM 返回固定前缀。函数签名、HTTP 契约、配置项已经稳定，后续接入真实向量库 / LLM 时**不会**改外部接口。详见 [§ 故障排查 · 为什么我搜不到东西](#为什么我搜不到东西)。

---

## 特性一览

| 能力 | 状态 | 说明 |
|------|------|------|
| 启动即用（cold-start） | ✅ | vault 为空时自动 fallback 到 `data/raw.sample/` 跑通 3 篇样例笔记 |
| FastAPI 9 端点 | ✅ | health / config / search / chat (非流式 + SSE) / ingest / usage |
| 后台 ingest | ✅ | 服务启动时**后台线程**跑全量索引，API 立刻可用 |
| 配置脱敏 | ✅ | `GET /api/config` 只回显非敏感字段，API key 走 `.env` 不入配置 |
| 决策码 | ✅ | `RETRIEVE_EMPTY` / `NOT_DEFINED` / `GENERATED` 三态，HTTP 200 自描述 |
| 真实向量库 | 🔜 | 接口已定（`retrieve(query, index_dir, top_k, filters)`），等 ADR 落 FAISS/Chroma |
| 真实 LLM | 🔜 | 接口已定（`_call_llm` 可注入），等 ADR 落 OpenAI/Anthropic/Ollama |

---

## 快速上手（5 分钟）

> 假设你是 macOS 用户，已经装了 [Homebrew](https://brew.sh) 和 [uv](https://docs.astral.sh/uv/)。
> 没有 uv 的话：`brew install uv`（30 秒）。

```bash
# 0) 拉代码
git clone https://github.com/maqy1995/rag-demo.git
cd rag-demo

# 1) 装依赖（uv 管理的 Python 3.12，跟系统 / conda 完全隔离）
uv sync --extra dev

# 2) 健康检查：确认 Python / git / uv / 配置 都就位
uv run rag-demo doctor

# 3) 启动服务（默认 http://127.0.0.1:8000，后台自动 ingest）
uv run rag-demo up

# 4) 打开浏览器
open http://127.0.0.1:8000
```

你会看到 3 篇样例笔记（欢迎 / 微服务治理 / 常见问题）已经被加载了。试着问：

```
微服务治理是什么？
什么是配置中心？
```

> 想跑自己的笔记？把 `.md` 文件丢进 `data/raw/`，然后：
> ```bash
> uv run rag-demo ingest --data ./data/raw --index ./data/index
> ```
> 再 `uv run rag-demo up` 重启服务即可。

---

## 部署指南

### 1. 环境要求

| 项 | 要求 | 备注 |
|----|------|------|
| OS | macOS / Linux | Windows 通过 WSL2 也可，尚未官方验证 |
| Python | 3.12.x | **必须**用 uv 装，不建议用系统 Python |
| 磁盘 | ≥ 500 MB | uv-managed Python + `.venv` + 索引 |
| 内存 | ≥ 512 MB | stub 阶段几乎不占 |
| 网络 | 仅首次 `uv sync` 需要 | 跑起来后默认走本地 ollama，可完全离线 |

### 2. 安装 Python 3.12（一次性）

```bash
uv python install 3.12
```

### 3. 安装项目依赖

```bash
cd ~/Code/rag-demo
uv sync --extra dev
```

> 默认会装：`fastapi` / `uvicorn` / `pydantic` / `httpx` / `pyyaml` / `python-dotenv` + 开发套件 `pytest` / `ruff` / `mypy`。
>
> 想要真实向量库或 LLM 客户端，按需加 `--extra`：
> ```bash
> uv sync --extra dev --extra faiss       # FAISS 向量库
> uv sync --extra dev --extra chroma      # Chroma 向量库
> uv sync --extra dev --extra langchain --extra openai  # LangChain + OpenAI
> ```

### 4. 准备数据

把你的笔记放到 `data/raw/` 目录下（支持 `.md` / `.txt` / `.rst`）：

```bash
mkdir -p data/raw
cp -r ~/Documents/my-notes/*.md data/raw/
```

不准备也行——cold-start 模式会自动 fallback 到 `data/raw.sample/`，跑通 3 篇样例笔记。

### 5. 启动服务

#### 选项 A：FastAPI + 后台 ingest（推荐）

```bash
uv run rag-demo up --host 127.0.0.1 --port 8000
```

服务会做 5 件事（详见 `docs/dev/design.md` §3.7）：

1. 加载 `config.yaml`（不存在则 fallback 到 `config.example.yaml` → 内置默认）
2. **后台线程**启动全量 ingest（不阻塞 API 启动）
3. `uvicorn` 启动 FastAPI，监听 `--host: --port`
4. 收到 `SIGINT` / `SIGTERM` 后等 ingest 跑完再优雅退出
5. `--no-ingest` 可跳过 ingest（仅用于调试）

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

### 浏览器（最简单）

打开 `http://127.0.0.1:8000`，根目录会返回占位 `index.html`（v0.1 阶段是简单 placeholder，后续会有完整聊天 UI）。

> 占位 HTML 由 `scripts/init_static.py` 一次性生成（dev-time 写文件，不在 import 时副作用）。如果访问 `GET /` 看到 404，先跑：
> ```bash
> uv run python scripts/init_static.py
> ```

### 命令行

```bash
# 一次性问一个问题（不走 HTTP，直接调 retrieve + answer）
uv run rag-demo ask "微服务治理是什么？"
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
| `GET`  | `/`                     | 静态 `index.html`（占位） |

### 决策码

`/api/chat` 和 `/api/chat/stream` 的 `decision` 字段三态：

| 值 | 含义 | LLM 是否被调 |
|----|------|--------------|
| `RETRIEVE_EMPTY`  | 检索为空（vault 里没相关内容） | ❌ 不调 |
| `NOT_DEFINED`     | 检索到了片段但没有"明确定义"（如 query 后没接"是 / 为 / 指"等定义短语） | ❌ 不调 |
| `GENERATED`       | 命中且定义充分，走 LLM 生成 | ✅ 调 |

`RETRIEVE_EMPTY` / `NOT_DEFINED` 走 200 + `decision` 字段，**不**走错误壳——这是设计上的有意决定，让前端能用统一结构处理兜底文案。

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
    provider: "ollama"     # ollama | openai | anthropic
    model: "qwen2.5"
    base_url: "http://localhost:11434"
  embedding:
    provider: "ollama"
    model: "nomic-embed-text"
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
# .env 示例 — 仅在你用云端 LLM 时才需要
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Multica runtime（仅在 demo 调用 multica API 时需要，可选）
MULTICA_TOKEN=
MULTICA_BASE_URL=https://api.multica.ai
```

`.env` 在 `.gitignore` 里，**永远不会**被 commit。

---

## 目录结构

```
rag-demo/
├── README.md                # 你正在读的文件
├── pyproject.toml           # uv-managed；extras for FAISS/Chroma/LangChain/OpenAI
├── .python-version          # 3.12
├── .env.example             # 复制为 .env 并填入 API key
├── config.example.yaml      # 配置示例（不进真实 key）
│
├── src/rag_demo/            # 三段式 pipeline + 配置 + 错误壳
│   ├── __main__.py          # CLI: ingest / ask / doctor / up / web
│   ├── ingest.py            # 扫描 + 切分 + 写索引
│   ├── retrieve.py          # 检索（当前 stub）
│   ├── generate.py          # 决策链 + LLM 桩
│   ├── validate.py          # "明确定义"判定（纯函数）
│   ├── config.py            # AppConfig + load_config
│   ├── errors.py            # AppError + ERROR_CODES
│   ├── vault_uri.py         # vault:// 协议编解码
│   ├── logging_setup.py     # 日志
│   └── web/main.py          # FastAPI 9 端点 + 静态文件
│
├── tests/                   # pytest，US4/US6/happy path + cold-start 30s 断言
├── data/
│   ├── raw/                 # 你的笔记（git ignore，自己放）
│   ├── raw.sample/          # 3 篇 demo 笔记（git 跟踪，冷启动 fallback 用）
│   ├── index/               # 索引输出（git ignore）
│   └── usage/               # 本地埋点日志（git ignore）
│
├── scripts/
│   ├── doctor.sh            # 包装 rag-demo doctor
│   └── init_static.py       # 一次性生成占位 index.html（dev-time）
│
└── docs/                    # 4 角色协作通道
    ├── README.md            # 文档总览
    ├── architecture.md      # pipeline 流程图
    ├── github-setup.md      # 推到 GitHub 的三种方法
    ├── product/             # 产品：backlog + spec
    ├── dev/                 # 开发：design + runbooks
    ├── review/              # 审查员：checklists + reports
    ├── envops/              # 环境准备与部署：environments + deployment + runbook
    ├── adr/                 # 跨角色架构决策记录
    ├── handoffs/            # 跨角色交接单
    └── templates/           # 空白模板
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

### 服务起不来，500 错误

```bash
# 先跑 doctor 排环境
uv run rag-demo doctor

# 看具体错误码
curl -i http://127.0.0.1:8000/api/health
```

### 索引卡在 `state=building`

```bash
# 看进度
curl http://127.0.0.1:8000/api/index/status | jq .
# → current_progress = { "done": 3, "total": 12 }  说明还在跑
# → state=idle  说明跑完了
```

如果一直卡住，看 `data/index/status.json` 的 `last_built_at` 字段是不是很久以前的——很可能是后台 ingest 线程崩了，重启服务即可。

### 为什么我搜不到东西

v0.1 阶段 `retrieve()` 永远是空 list（接口已就位，向量库待接）。这是**预期行为**，不是 bug。验证服务健康的姿势：

```bash
# 1. ingest 跑通了吗
curl http://127.0.0.1:8000/api/index/status | jq .state
# 应该看到 "idle"

# 2. /api/chat 决策码是什么
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"微服务治理是什么？"}' | jq .decision
# 应该看到 "RETRIEVE_EMPTY"（v0.1 stub 行为） 或 "NOT_DEFINED"
# 真实 LLM 接好后才会是 "GENERATED"
```

### 怎么加我自己的笔记

```bash
# 1. 复制进去
cp ~/my-note.md data/raw/

# 2. 重建索引
uv run rag-demo ingest --data ./data/raw --index ./data/index

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
| 产品 | `docs/product/` | `docs/adr/` | [`docs/product/README.md`](./docs/product/README.md) |
| 开发 | 代码 + `docs/dev/` | spec + ADR | [`docs/dev/README.md`](./docs/dev/README.md) |
| 审查员 | `docs/review/reports/` | 全部 PR | [`docs/review/README.md`](./docs/review/README.md) |
| 环境准备与部署 | `docs/envops/` + handoff | 全部 | [`docs/envops/README.md`](./docs/envops/README.md) |

跨角色交接走 `docs/handoffs/<date>-from-A-to-B-<slug>.md` 模板。
架构分歧先在 `docs/adr/NNNN-<slug>.md` 写 ADR 决议，Accepted 后全员遵循。

### Multi-agent 工具链

- **Claude Code** 在 multica workspace 跑，负责计划 / 审查 / 协调。
- **Codex CLI** 在同仓库执行实现：`codex exec "<task>"`。
- **Multica** 是 durable record，本仓库已通过 `multica project resource add` 绑到 `知识库问答` 项目下。

### 推到 GitHub

```bash
gh auth login                              # 一次性
gh repo create maqy1995/rag-demo --public --source=. --remote=origin --push
```

详细步骤见 [`docs/github-setup.md`](./docs/github-setup.md)。

---

## License

MIT © maqy

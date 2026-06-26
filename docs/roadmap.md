# rag-demo 技术栈与演进路线

> **multica-issue**: [MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 收尾后下一阶段规划
> **作者**: 研发主管（`7ac4615f…`）
> **日期**: 2026-06-26
> **当前版本**: v1.2（4 provider + 真 LLM / Embedding / Vector）
> **本文定位**: 一份给项目 owner / 后续接手开发者看的"技术全景 + 路线图"，每条演进项都给出 *动机 / 目标 / 验收 / 风险*。

---

## 目录

- [一、当前技术栈（v1.2 快照）](#一当前技术栈v12-快照)
- [二、架构现状一张图](#二架构现状一张图)
- [三、已落地的能力矩阵](#三已落地的能力矩阵)
- [四、技术债与短板（驱动演进的真实痛点）](#四技术债与短板驱动演进的真实痛点)
- [五、演进路线](#五演进路线)
  - [v1.3 — 检索质量与可观测性](#v13--检索质量与可观测性)
  - [v1.4 — 索引能力扩展](#v14--索引能力扩展)
  - [v1.5 — 评估与持续集成](#v15--评估与持续集成)
  - [v2.0 — 后端生产化](#v20--后端生产化)
  - [v2.1 — Agent 与工具调用](#v21--agent-与工具调用)
  - [v2.2 — 多模态摄取](#v22--多模态摄取)
  - [v3.0 — 分布式与知识图谱](#v30--分布式与知识图谱)
- [六、横向非功能目标（贯穿所有阶段）](#六横向非功能目标贯穿所有阶段)
- [七、版本节奏与里程碑建议](#七版本节奏与里程碑建议)

---

## 一、当前技术栈（v1.2 快照）

### 1.1 语言 / 运行时 / 包管理

| 维度 | 选型 | 备注 |
|------|------|------|
| 语言 | **Python 3.12**（`<3.13`） | pyproject 锁定，`match` 语句 + 类型注解新语法齐 |
| 包管理 | **uv**（`uv.lock` 已生成） | `uv sync --extra llm --extra vector --extra web --extra dev` 一步到位 |
| 构建后端 | hatchling | 入口 `rag-demo = "rag_demo.__main__:main"` |

### 1.2 后端框架

| 维度 | 选型 | 备注 |
|------|------|------|
| Web 框架 | **FastAPI 0.110+** | ADR-0004 拍板（"撤回成本 ≈ ∞"） |
| ASGI 容器 | **uvicorn[standard]** | 9 端点（health / config / search / chat 非流式 + chat SSE / ingest / usage / static） |
| 数据校验 | **pydantic v2** | `BaseModel` 严格模式 + frozen dataclass 配置 |
| 流式协议 | SSE via `StreamingResponse` | 不引 `sse-starlette`，事件类型 `event: token` / `event: done` |
| 客户端 | `httpx>=0.27` | 透传到 `openai` SDK 内部 |

### 1.3 LLM / Embedding 层（ADR-0001 / 0003）

| 维度 | 选型 | 备注 |
|------|------|------|
| 抽象 | **直裸 OpenAI 兼容 SDK** + 极薄抽象 `BaseLlmClient` / `BaseEmbedder` | 弃用 LangChain / LlamaIndex（抽象泄漏） |
| LLM Provider（4 家） | **OpenAI / 智谱 GLM / MiniMax / 小米 Mimo** | 全部声明 OpenAI 兼容 → 1 个 client + `base_url`+`api_key`+`model` 三元组切换 |
| Embedding Provider | **与 LLM 解耦**，4 家任选 | `config.yaml::generate.{llm,embedding}.provider` 独立配置 |
| 默认配置 | LLM = `minimax M3`，Embedding = 智谱 `embedding-3` | MAQ-45 拍板 |
| Fallback | **无** | 首次启动必须填至少 1 个 `*_API_KEY`，否则 `AppError(401)` fast-fail |

### 1.4 检索层（ADR-0002）

| 维度 | 选型 | 备注 |
|------|------|------|
| 向量库 | **FAISS-CPU `IndexFlatIP`** | 1k 切片毫秒级；>10k 切片时换 `IVFFlat` / `HNSW` |
| 持久化 | `faiss.index` + `faiss_meta.json`（append-only） | 与 `manifest.json` + `status.json` 共存于 `data/index/` |
| 文本切分 | 标题优先 + 长度兜底 | `chunk_size=500` / `chunk_overlap=80` / 标题边界切分 |
| 元数据 | 字典列表（`source` / `chunk_id` / `mtime`） | typed filter 待 v1.3 |
| Embedding 模型解耦 | ✅ | v1.2 已落 |

### 1.5 前端（ADR-0005）

| 维度 | 选型 | 备注 |
|------|------|------|
| 形态 | **单 HTML + Vue 3 CDN + marked.js CDN** | 零构建；`git clone` → `uv run rag-demo up` 一条命令 |
| 面板 | 左 Search / 右 Ask 双面板 | 5 示例问题按钮 + 索引状态条轮询 |
| Markdown 渲染 | marked.js 单文件 | 引用块、代码块、列表全支持 |
| 样式 | 暖灰配色 `static/style.css`（MAQ-48 落地） | 现代化 UI 升级（MAQ-50） |

### 1.6 工程化

| 维度 | 选型 | 备注 |
|------|------|------|
| 测试 | **pytest 8 + pytest-asyncio** | 145 passed（v1.2 净增 65 断言），含 `e2e` / `eval` 双 marker |
| Lint | **ruff**（E/F/I/W/B/UP/N） | 0 errors（v1.2） |
| 类型检查 | **mypy strict** | 全模块通过 |
| 评估 | `scripts/eval_recall.py` | Recall@K + `pytest -m eval` 入口 |
| 协作 | Multica（issue / comment / squad） | 4 角色：产品 / 开发 / 审查员 / 环境部署 |
| 架构决策 | `docs/adr/0000~0005` | ADR 锁死后实现，不再口头"架构" |

### 1.7 数据 / 部署

| 维度 | 选型 | 备注 |
|------|------|------|
| 数据存储 | 文件级（`data/raw/` + `data/index/` + `data/index.sample/`） | 无 Redis / Postgres / Celery（PRD §6.1.5 硬约束） |
| 隐私 | vault 原文 / 索引 / 日志全本地，**仅检索片段上送 LLM** | 符合企业内网合规 |
| 冷启动 | `data/raw.sample/` 5 篇 + `data/index.sample/` 预 embed | 30s 内浏览器可见 5 示例按钮 |
| 部署 | `uv run rag-demo up` | 单进程 FastAPI + 后台 ingest 线程 |

---

## 二、架构现状一张图

```
                    ┌──────────────────────────────────────────────┐
                    │  Browser (Vue 3 CDN + marked.js)             │
                    │  Search │ Ask (SSE) │ 索引状态条              │
                    └──────────┬──────────────────┬─────────────────┘
                               │ /api/search       │ /api/chat/stream
                               ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FastAPI + uvicorn (web/main.py)                                     │
│  9 端点：health / config / search / chat / chat/stream / ingest /     │
│         usage / static / (debug)                                     │
└────┬────────────────────────────┬──────────────────────────┬────────┘
     │                            │                          │
     ▼                            ▼                          ▼
┌──────────┐                ┌──────────┐               ┌────────────┐
│ retrieve │                │ generate │               │   ingest   │
│ embed()  │                │ stream() │               │ chunk+embed│
│ +search  │                │ +cite    │               │ +write FAISS│
└────┬─────┘                └────┬─────┘               └──────┬─────┘
     │                           │                            │
     ▼                           ▼                            ▼
┌──────────┐                ┌──────────────┐           ┌─────────────┐
│ FAISS    │                │ OpenAI 兼容  │           │ Chunker     │
│ IndexFlat│                │ SDK (4 家)   │           │ (标题+长度) │
│ +IP +meta│                │              │           └──────┬──────┘
└────┬─────┘                └──────────────┘                  │
     ▲                                                        ▼
     │                                                  ┌────────────┐
     │                                                  │ Embedder   │
     │                                                  │ (4 家)     │
     │                                                  └─────────────┘
     │
     └──── 启动时后台线程 full-ingest；运行时 mtime 增量 diff
```

---

## 三、已落地的能力矩阵

| 能力 | 状态 | 关键 issue |
|------|------|-----------|
| 4 家 OpenAI 兼容 LLM | ✅ | MAQ-28 / 31 |
| LLM / Embedding 解耦 | ✅ | MAQ-28 |
| 真 FAISS 检索（IndexFlatIP） | ✅ | MAQ-27 / 34 |
| 真 Embedder（4 家可切） | ✅ | MAQ-32 |
| 真流式 LLM（SSE token） | ✅ | MAQ-31 / 36 |
| FastAPI 9 端点 | ✅ | MAQ-29 |
| 后台 ingest（启动即跑） | ✅ | MAQ-37 |
| 冷启动 demo（30s 可用） | ✅ | MAQ-38 / 39 / 41 / 42 |
| Recall@K 评估脚本 | ✅ | MAQ-40 |
| 真实 Vue 3 双面板 UI | ✅ | MAQ-41 / 48 / 50 |
| 决策码（`RETRIEVE_EMPTY` / `NOT_DEFINED` / `GENERATED`） | ✅ | design §3.5 |
| 配置脱敏（`/api/config` 不回显 API key） | ✅ | design §3.4 |
| e2e cold-start 30s 测试 | ✅ | MAQ-42 |
| 完整 dev 自审 + Reviewer 通看 | ✅ | MAQ-43 |

---

## 四、技术债与短板（驱动演进的真实痛点）

> 这部分**不**是"理论上要补的清单"，而是 v1.2 真实跑下来暴露出来的问题。每条都对应下面演进路线的某一项。

| # | 痛点 | 表现 | 驱动路线 |
|---|------|------|----------|
| T1 | 纯 dense 检索在"精确词命中"场景下表现差 | 用户问某个 API 名 / 命令字 → 召回率掉 | **v1.3** 混合检索 |
| T2 | 无任何 token / 成本 / 延迟可观测 | 出问题只能猜是 LLM 慢还是 embedding 慢 | **v1.3** 可观测性 |
| T3 | 元数据过滤（按 source / mtime）透传不报错 | 用户期待"只看近 7 天笔记"做不到 | **v1.3** 元数据 |
| T4 | ingest 启动时全量重跑；运行中无 watch | 改了笔记要重启服务 | **v1.4** 增量 watch |
| T5 | 只支持 `.md` / `.txt` | 用户扔 PDF / DOCX 进来直接忽略 | **v1.4** 多格式 |
| T6 | 评估集 5 条硬编码，太少 | 改了一个参数不知道是变好还是变坏 | **v1.5** 评估扩充 |
| T7 | 无鉴权 / 限流 | 一旦部署到非本机就裸奔 | **v2.0** 生产化 |
| T8 | 单 vault 绑定单进程 | 多人/多库场景无解 | **v2.0** 多用户/多 vault |
| T9 | 单答案生成，无法引用多源对比 / 反驳 | 用户问"X 和 Y 的区别"只能拼凑 | **v2.1** Agent |
| T10 | vault 里图片 / 表格 / 截图无法被检索 | 图文混排笔记只能问文字 | **v2.2** 多模态 |
| T11 | IndexFlatIP 在 >10k 切片下变慢；无服务化向量库 | 真上线要的是 Qdrant / Milvus | **v3.0** 分布式 |

---

## 五、演进路线

> 命名沿用既有节奏：**v1.x = 单机 + 单 vault 能力补全**，**v2.x = 生产化 + Agent 化**，**v3.0 = 分布式 + 知识图谱**。
> 每条都写 *动机 / 目标 / 验收 / 风险*，避免"看起来很美但没人接得住"。

### v1.3 — 检索质量与可观测性

> **目标**：让"问得到"稳定 + "出了问题能定位"。

#### 1.3.1 混合检索（BM25 + dense）
- **动机**：T1。dense 擅长语义，BM25 擅长精确词（API 名 / 命令 / 错误码）。
- **目标**：在 `retrieve.py` 增加 BM25 通道（`rank_bm25>=0.2`），与 FAISS dense 召回结果 RRF 融合（reciprocal rank fusion, k=60）。
- **验收**：
  - `scripts/eval_recall.py` 新增 10 条"精确词命中"题（如"`MiniMax M3` 默认 base_url 是什么"），混合检索 Recall@5 ≥ 0.8（纯 dense 基线 ≈ 0.4）。
  - `/api/search?mode=dense|hybrid|bm25` 三模式切换。
  - pytest 增加：纯 dense 跑一遍、纯 BM25 跑一遍、hybrid 跑一遍；同 query 同 ground truth → hybrid ≥ max(dense, bm25)。
- **风险**：BM25 索引需随 dense 索引一起 rebuild；要做"同源同生命周期"（chunk_id 共用 → rebuild 一致）。

#### 1.3.2 可观测性（logging + metrics + request_id）
- **动机**：T2。LLM / Embedding 调用慢、401、429 现在散落在 stdout。
- **目标**：
  - 引入 `structlog`（或保留 stdlib + `extra`），统一 JSON 日志：每条请求一个 `request_id`，关联到 embedding 调用 + LLM token 流。
  - `GET /api/usage` 返回 `{requests, prompt_tokens, completion_tokens, est_cost_usd, p50_latency_ms, p95_latency_ms}`，按 provider 拆分。
  - 4 家 provider 的费率表（USD/1k token）放 `config.yaml::pricing`，调用时按 token 数累计。
- **验收**：
  - 跑 10 次 chat，记录的 token 总和与 provider dashboard 一致（±5%）。
  - 日志中任意一条 `event=llm_call` 都能通过 `request_id` 找到对应的 `event=embedding_call` + `event=retrieve_done`。
  - `/api/usage` 返回 JSON 结构稳定，文档化字段。
- **风险**：定价表会过期；写一个 `scripts/check_pricing.py`（CI 跑，>30 天 warn）。

#### 1.3.3 元数据过滤（typed filter）
- **动机**：T3。`data/raw/` 里笔记可能想按 `source` / `mtime` / `chunk_type` 过滤。
- **目标**：`FAISS MetaStore`（`src/rag_demo/vector/meta.py`）升级为 typed：`source: str` / `mtime: int` / `chunk_type: Literal["title","body","code"]`。`/api/search?since_mtime=...&source_prefix=...` 走 filter。
- **验收**：
  - pytest：插入 5 切片，过滤 `since_mtime=now-1d` → 只返 ≤ 1d 的；`source_prefix=docs/` → 只返 docs 下的。
  - 向后兼容：旧 `faiss_meta.json` 自动 migrate（缺字段填默认值）。
- **风险**：IndexFlatIP 本身不支持原生 filter；要在 Python 层先按 meta 过滤再搜向量（**反**过来更高效：先按 meta 子集 subset 索引再 search）。

---

### v1.4 — 索引能力扩展

> **目标**：让 vault "放得进、删得掉、改得动"。

#### 1.4.1 多格式摄取（PDF / DOCX / HTML）
- **动机**：T5。`unstructured>=0.12`（一份依赖覆盖 PDF / DOCX / HTML / 图片 OCR）。
- **目标**：`chunker.py` 之上加 `loaders/`：`.md/.txt` 走现有纯文本路径，`.pdf` 走 `unstructured.partition.pdf`，`.docx` 走 `python-docx`，`.html` 走 `unstructured.partition.html`；输出统一 `list[Chunk]`。
- **验收**：
  - `data/raw.sample/` 加 1 篇 PDF + 1 篇 DOCX，ingest 后能召回。
  - `pyproject.toml` 新增 `unstructured[all-docs]` extra。
  - 不新增常驻进程；解析走 ingest 一次性。
- **风险**：`unstructured[all-docs]` 拉很多 native 依赖（poppler / tesseract），CI 镜像要装系统包；文档化到 `docs/envops/environments.md`。

#### 1.4.2 增量 watch（mtime / fs event）
- **动机**：T4。现在改笔记要重启。
- **目标**：服务运行时后台线程用 `watchfiles>=0.21` 监听 `data/raw/` 变化（debounce 2s），触发增量 ingest（只 embed 变化的文件 + 删除已不存在的）。
- **验收**：
  - 启动服务 → 编辑 `data/raw/01-xxx.md` 加一行 → 30s 内 `/api/index/status` 显示 `last_ingest_at` 更新。
  - 删除文件 → 对应切片从 index 移除。
  - pytest 用 `tmp_path` + `watchfiles` 同步触发验证。
- **风险**：watch 与"冷启动全量"两个入口要分清（写一份 `IngestOrchestrator` 状态机，cold/full/incremental 三态）。

#### 1.4.3 软删除与重建
- **动机**：delete 现在只能 rebuild 整个 index。
- **目标**：`vector.delete(chunk_ids)` 实现：在 `faiss_meta.json` 标 `deleted=true`，`search()` 时跳过；超过阈值（如 5%）触发后台 `rebuild_index()`。
- **验收**：
  - 删除 1 篇笔记 → `/api/search` 不再召回；FAISS `.index` 体积不变。
  - 标记 100 篇删除 → 触发 rebuild，10s 内完成（1k 切片规模）。
- **风险**：rebuild 是阻塞操作；用 `BackgroundTasks` 异步触发 + 进度通过 `/api/index/status` 暴露。

---

### v1.5 — 评估与持续集成

> **目标**：让"改了一个参数是否变好"有据可循。

#### 1.5.1 评估集扩充（50+ 题 + 自动生成）
- **动机**：T6。5 条 hard-code 太少。
- **目标**：
  - 拆 3 个子集：`data/eval/{exact_match, semantic, multi_hop}.jsonl`，每集 20+ 题。
  - 增加 `scripts/build_eval_set.py` —— 从 `data/raw/` 抽 2-3 句原文 → 调 LLM 反向生成 question（LLM-as-questioner），人审后入集。
- **验收**：
  - 评估集 ≥ 50 题，每题结构 `{q, expected_source_substring, expected_keywords?: list[str]}`。
  - `scripts/eval_recall.py` 支持 `--subset exact_match|semantic|multi_hop|all`。

#### 1.5.2 LLM-as-judge（答案质量）
- **动机**：Recall@K 只能评检索，不能评"答案好不好"。
- **目标**：用 GPT-4o-mini（或本地 Qwen）做 judge，给定 `(question, ground_truth_answer, generated_answer)` 打 1-5 分；输出到 `data/eval/results/<timestamp>.json`。
- **验收**：
  - 跑 50 题 → 平均分 ≥ 3.5 / 5（基线为 v1.2）。
  - 同一问题换不同 provider → judge 分数差异可解释（不是噪声）。
- **风险**：judge 自身有偏差；规则之一：judge 不用生成答案的同一 provider（同模型自评有偏向）。

#### 1.5.3 CI 集成
- **目标**：`.github/workflows/ci.yml` 跑 `ruff` + `mypy` + `pytest -m 'not e2e and not eval'` + `pytest -m eval`（用 mock embedder，避免 CI 烧 API 钱）。
- **验收**：
  - push 后 CI 90s 内出结果。
  - mock embedder 文件 `tests/_fixtures/mock_embedder.py` 已提交。
  - 失败时日志带 `request_id`，可一键定位。

---

### v2.0 — 后端生产化

> **目标**：从"我自己跑"到"团队 / 客户能跑"。

#### 2.0.1 鉴权 + 限流
- **动机**：T7。
- **目标**：
  - `Authorization: Bearer <token>` 校验，token 从 `config.yaml::auth.tokens` 读（多 token 列表）。
  - 限流用 `slowapi`（基于 token-bucket），per-token 60 req/min。
  - `/api/health` 与 `/api/config`（脱敏）放行。
- **验收**：
  - 错误 token → 401；超限 → 429。
  - 文档化到 `docs/envops/auth.md`。

#### 2.0.2 多 vault / 多租户
- **动机**：T8。
- **目标**：`config.yaml::vaults` 数组，每个 vault 有独立 `data_dir` / `index_dir` / `name`；URL 路径 `/v/{vault_name}/api/...`。
- **验收**：
  - 2 个 vault 同时跑，互不串数据。
  - ingest / search / chat 全栈按 vault 分隔。
- **风险**：复杂度上升；保留 v1.x 单 vault 路径为默认（`/api/...` 走默认 vault）。

#### 2.0.3 async ingest
- **目标**：当前 ingest 在后台线程；改成 `asyncio.Task` + `httpx.AsyncClient` 调 embedding（vLLM/远程都更顺）。
- **验收**：
  - 1000 切片 ingest 时间下降 ≥ 20%（并发 batch embedding）。
  - 服务在 ingest 中能正常 `/api/health` 200。

#### 2.0.4 Docker 镜像
- **目标**：`Dockerfile`（python:3.12-slim）+ `docker-compose.yml`（单服务，挂 `data/` 卷）。
- **验收**：
  - `docker compose up` 30s 内 `http://localhost:8000/` 可见 cold-start UI。
  - 镜像 < 500 MB（`unstructured` 留在 extra，不进 base image）。

---

### v2.1 — Agent 与工具调用

> **目标**：从"单答案"到"多步推理 + 外部信息"。

#### 2.1.1 Agent loop（ReAct 风格）
- **动机**：T9。
- **目标**：`generate.py` 新增 `answer_with_agent(question, vault)`，支持多轮：think → tool_call → observe → … → final。
- **工具**：
  - `search_vault(query, top_k)` —— 内部 RAG。
  - `web_search(query)` —— 选 Tavily / Bing Search（config 配 key）。
  - `calculator(expr)` —— 沙箱 `python-eval`（限制 `math` / `json` 模块）。
  - `datetime_now()` —— 时间相关问题。
- **验收**：
  - "对比 vault 里 X 笔记和外部 Y 资料的区别"能给出 2 段对照。
  - 工具调用次数上限 5（防 runaway），单次超时 10s。
- **风险**：agent 不收敛会烧钱；强约束：max_steps + max_tokens_per_step + 全程 stream 给前端看进度。

#### 2.1.2 工具调用协议（OpenAI 兼容）
- **目标**：4 家 provider 都支持 OpenAI `tools` 协议；直接用 `client.chat.completions.create(tools=...)`。
- **风险**：4 家对 `tool_choice` 支持略有差异，config 加 `tool_compatible: bool` 字段做兜底。

---

### v2.2 — 多模态摄取

> **目标**：让"图、表格、音频"也能被问答到。

#### 2.2.1 图片 OCR + 图文混排 chunk
- **动机**：T10。
- **目标**：
  - PDF / DOCX 中的图片用 `unstructured` + `pytesseract` OCR 出文字。
  - chunker 在图片位置插入 `[image: <ocr_text>]` 占位 chunk，meta 标 `chunk_type="image"`。
  - Embedding 模型换 multimodal（CLIP / Qwen-VL embedding），或图文分别 embed 后融合。
- **验收**：
  - 含图的 PDF → ask "这个图说的是什么" → 召回含 OCR 文字的 chunk。
- **风险**：multimodal embedding 4 家 provider 不全支持；先支持 OpenAI `text-embedding-3-large` + 自托管 CLIP（Ollama 路线已被 ADR-0003 否决，**走 OpenAI-only v2.2 起步**）。

#### 2.2.2 音频转写
- **目标**：`data/raw/` 接受 `.mp3` / `.wav`；用 OpenAI `whisper-1` 转写后走 chunker。
- **验收**：1 段 1 分钟音频 → 转写后能召回。

---

### v3.0 — 分布式与知识图谱

> **目标**：从"个人 / 团队"到"企业 / SaaS"。

#### 3.0.1 向量库升级（Qdrant / Milvus）
- **动机**：T11。IndexFlatIP 在 >10k 切片下变慢。
- **目标**：`src/rag_demo/vector/` 新增 `qdrant_store.py` / `milvus_store.py`，通过 `config.yaml::vector.backend` 切换；FAISS 保留为单机 dev 默认。
- **验收**：
  - 100k 切片下 Recall@10 与 FAISS 一致（±1%），p95 延迟 < 50ms。
  - pytest 跑通 Qdrant 路径（CI 用 testcontainers）。

#### 3.0.2 元数据上 Postgres
- **目标**：用户、vault、token、usage 全部入 Postgres；SQLAlchemy 2 + asyncpg。
- **验收**：迁移脚本 `alembic upgrade head` 幂等。

#### 3.0.3 GraphRAG（知识图谱增强）
- **动机**：跨笔记的关系比纯 chunk 召回更准。
- **目标**：
  - ingest 时调 LLM 抽"实体 + 关系" → 写 Neo4j。
  - retrieve 时先 graph query 找到相关实体 → 再做向量召回。
- **验收**：
  - "X 的负责人是谁？他在 Y 文档里写了什么？" 跨笔记问题召回率 ≥ 0.6（纯 RAG 基线 ≈ 0.2）。
- **风险**：GraphRAG 成本高（抽实体调 LLM），对长尾 vault 不划算；提供开关 `config.yaml::graph.enabled`。

---

## 六、横向非功能目标（贯穿所有阶段）

> 这些**不**是某个版本独占，而是每次发版都要保持不退步。

| 维度 | 目标 | 度量 |
|------|------|------|
| 测试 | pytest ≥ 200 passed，e2e 30s，eval Recall@5 ≥ 0.7 | CI 报告 |
| 静态检查 | ruff 0 errors，mypy strict 全过 | CI |
| 文档 | 每个新 issue 都建对应的 ADR / release notes 一行 | multica issue link |
| 可观测 | 任意请求 1 个 `request_id` 串起全链路 | 日志结构化 |
| 性能 | 100 篇 cold-start ≤ 30s；1000 篇 ingest ≤ 90s（远程 API） | `scripts/bench.py` |
| 安全 | 鉴权 + 限流 + 配置脱敏 + 无明文 API key 入 git | `git log -p` + `scripts/scan_secrets.py` |
| 隐私 | vault 原文 / 索引 / 日志全本地；上送 LLM 仅 chunk 文本 | ADR-0003 + 设计 §3.4 |
| 兼容性 | 4 家 LLM + 4 家 Embedding 持续跑通 | `scripts/smoke_all_providers.py` CI cron |

---

## 七、版本节奏与里程碑建议

| 版本 | 周期（估） | 关键产出 | 上线门槛 |
|------|----------|----------|----------|
| **v1.2**（已发） | — | 4 provider + 真 LLM / Embedding / Vector + 真 UI | ✅ 145 pytest + 0 ruff |
| **v1.3** | 2-3 周 | 混合检索 + 可观测性 + 元数据 filter | Recall@5 ≥ 0.7；`/api/usage` 落 |
| **v1.4** | 2-3 周 | 多格式 + watch + 软删除 | 1000 切片 ingest ≤ 90s；运行中编辑 30s 内生效 |
| **v1.5** | 1-2 周 | 评估集 50+ + LLM-as-judge + CI | CI 跑通 eval，回归可视化 |
| **v2.0** | 4-6 周 | 鉴权 + 限流 + 多 vault + async + Docker | 镜像 < 500 MB；docker compose 30s 起 |
| **v2.1** | 3-4 周 | Agent loop + tools | max_steps=5；前端可看思考流 |
| **v2.2** | 3-4 周 | 多模态 | 图文混排 chunk 召回 OK；音频转写 OK |
| **v3.0** | 8 周+ | Qdrant + Postgres + GraphRAG | 100k 切片 p95 < 50ms；跨笔记问题 Recall@5 ≥ 0.6 |

---

## 附录 A：技术决策索引（演进时优先复用的 ADR）

| ADR | 主题 | 影响后续哪些演进 |
|-----|------|----------------|
| 0001 | LLM 框架：直裸 OpenAI 兼容 SDK | v1.3 配 OpenAI 协议 tools；v2.1 tool calling |
| 0002 | 向量库：FAISS IndexFlatIP + JSON meta | v1.3 typed meta；v1.4 软删除；v3.0 切换后端 |
| 0003 | 4 provider + LLM/Embedding 解耦 + 无 Ollama | v2.2 multimodal embedding 受限（Ollama 路线否决） |
| 0004 | FastAPI + pydantic v2 | v2.0 async 改造基于现有 FastAPI |
| 0005 | 单 HTML + Vue 3 CDN + marked.js | v2.1 前端展示 agent 思考流需扩展 index.html |

## 附录 B：演进过程中可能新增的 ADR 候选

- ADR-0006：混合检索融合策略（RRF vs 加权）
- ADR-0007：可观测性栈（structlog vs OpenTelemetry）
- ADR-0008：鉴权方案（API token vs OAuth2）
- ADR-0009：多 vault 路由策略
- ADR-0010：Agent 框架（自研 ReAct vs LangGraph）
- ADR-0011：向量库后端切换条件（什么时候必须从 FAISS 切到 Qdrant）
- ADR-0012：GraphRAG 启用条件与回退策略

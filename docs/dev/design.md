# 概要设计 — 知识库问答 (Knowledge-Base QA)

> multica-issue: [MAQ-8](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab)
> 维护者：资深全栈开发工程师 (`01386b69…`)
> 上游输入：[MAQ-5](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) PRD v0.3（Final, Reviewer Approved with comments）
> 关联交接单：[handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md](../handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md)
> 状态：**Review-ready v1**（5 个 ADR 落地后即可进入实现 v1）
> 日期：2026-06-24

---

## 0. 读者指南

| 角色 | 重点章节 | 看完后请 |
|------|---------|---------|
| 产品 | §1、§2.2、§5、§10（验收）、§11（开放问题） | 在 §10 验收逐条打勾；§11 阻塞答复一条删一条 |
| 开发（实现） | 全部 + `docs/adr/NNNN-*.md` | 严格按 §3 函数签名实现；任何对外契约变更先改本文再改码 |
| 审查员 | §3、§4、§6、§10 | 用 `review/checklists/code-review.md` 逐项打勾 |
| 环境运维 | §7（启动顺序）、§8（错误/日志）、§9（性能） | 写进 `envops/runbooks/`；启动顺序改动先在 §7 落字 |

> 本文是 **架构意图** + **对外契约** 的单一信源。具体技术选型（LLM 框架 / 向量库 / 来源 / Web / 前端）一旦 `docs/adr/` 拍板，**以最新 ADR 为准**，本文随之在 §12 修订记录里挂一行。

---

## 1. 设计目标与非目标

### 1.1 设计目标

1. **让 PRD v0.3 的全部 F1–F12、US1–US6 可在一个 Sprint 内端到端跑通**——骨架已在 main 分支，三段式 stub 各自只剩"换实现"。
2. **业务函数签名稳定**，使 CLI、HTTP API、Web UI 三条入口能共享同一份核心代码：替换 LLM 框架 / 向量库 / Embedding 来源时不许改 CLI、不许改 HTTP 路由。
3. **对 LLM 行为做硬约束**：US4 / US6 不依赖 LLM 服从 prompt，而用确定性前后置处理兜底（参见 §3.4 决策链）。
4. **可评估、可观测**：Recall 脚本、自动化断言（chat / cold_start）、结构化错误与一行 JSON 日志在 MVP 阶段就到位，不留到 v0.2。
5. **本地优先、隐私不妥协**：默认配置全程本地；任何远程调用都要 README 高亮、`.env` 显式注入。

### 1.2 非目标（显式不做，避免范围蔓延）

- 多用户 / 鉴权 / 计费（PRD §2.3 + §11 B8）。
- 多模态 / 图片 OCR / PDF（PRD §11 B7）。
- 笔记写入 / 编辑 / 知识图谱构建（PRD §3.3）。
- file-watcher 实时增量同步（PRD §3.1 F3，v0.2 再做）。
- 跨设备 / 云端部署（PRD §10）。
- 第二条依赖管理路径（PRD §6.1.2）。

---

## 2. 架构总览

### 2.1 一张图

```
                       ┌───────────────────────────────────────────────┐
                       │          知识库问答  Knowledge-Base QA          │
                       └───────────────────────────────────────────────┘

 ┌──────────┐    ┌─────────────────────────────────────────────────────────┐
 │  Vault   │    │                       进程内 (Python 3.12)              │
 │  (md)    │    │                                                         │
 │  data/   │    │   ┌─────────┐    ┌──────────┐    ┌──────────┐           │
 │  raw/    │───▶│   │ INGEST  │───▶│ RETRIEVE │───▶│ GENERATE │──┐        │
 │          │    │   │         │    │          │    │          │  │        │
 └──────────┘    │   │ loader  │    │ embed    │    │ is_defined   │        │
                 │   │ chunker │    │ ANN topK │    │ _in_hits() │  │        │
                 │   │ embed?  │    │          │    │   ↓        │  │        │
                 │   │         │    │          │    │  answer()  │  │        │
                 │   └────┬────┘    └────┬─────┘    └────┬─────┘  │        │
                 │        │             │              │        │        │
                 │        ▼             ▼              ▼        │        │
                 │   ┌─────────────────────────────────────┐    │        │
                 │   │         持久化 data/index/          │    │        │
                 │   │   ├─ manifest.json (mtime/sha)      │    │        │
                 │   │   ├─ <vector store dir>/            │    │        │
                 │   │   └─ usage/local-{date}.jsonl       │    │        │
                 │   └─────────────────────────────────────┘    │        │
                 │                                             │        │
                 │   ┌────────────────┐    ┌────────────────┐  │        │
                 │   │  CLI (argparse)│    │  Web (FastAPI) │◀─┘        │
                 │   │  rag-demo      │    │  /api/...      │  SSE      │
                 │   │  ingest/ask/   │    │  static/       │           │
                 │   │  doctor/up     │    │  index.html    │           │
                 │   └────────────────┘    └────────────────┘           │
                 │                                                         │
                 │   ┌──────────────────────────────────────┐            │
                 │   │  CONFIG  (./config.yaml + .env)        │            │
                 │   │  LOG    (一行 JSON: ts/level/stage/   │            │
                 │   │          cost_ms/msg)                 │            │
                 │   │  ERROR  ({error:{code,message,stage}})│            │
                 │   └──────────────────────────────────────┘            │
                 └─────────────────────────────────────────────────────────┘
                              ▲                                ▲
                              │                                │
                              │   ┌──────────────────────┐     │
                              └── │   external LLM /     │ ◀───┘  (only if remote)
                                  │   Embedding API      │
                                  │   (Ollama 默认本地)   │
                                  └──────────────────────┘
```

### 2.2 分层职责

| 层 | 模块 / 路径 | 职责 | **不**做什么 |
|----|------------|------|-------------|
| **L1 数据** | `data/raw/`、`data/index/`、`data/usage/` | 知识库原文、向量库持久化、本地埋点日志 | 任何业务逻辑；任何对用户可见的文案 |
| **L2 核心 (core)** | `src/rag_demo/{ingest,retrieve,generate,validate}.py` | 业务函数；纯函数化、依赖注入；可在 pytest 直接调用 | 任何 CLI 参数解析；任何 HTTP 路由；任何全局副作用（除日志/埋点） |
| **L3 接口 (interface)** | `src/rag_demo/__main__.py`（CLI）、`src/rag_demo/web/main.py`（FastAPI）、`src/rag_demo/web/static/index.html`（前端） | 把 core 函数包成用户可调用的形态；等价复用 core | 任何业务规则；任何错误文案生成（统一走 core + 错误码表） |
| **L4 横切 (cross-cutting)** | `src/rag_demo/config.py`、`src/rag_demo/logging_setup.py`、`src/rag_demo/errors.py`、`src/rag_demo/vault_uri.py` | 配置加载 / 日志格式 / 错误码表 / `vault://` 编解码 | 任何与 ingest/retrieve/generate 业务相关的逻辑 |

> **黄金法则**：L3 只能调 L2、L4；L2 只能调 L1、L4；L4 不依赖 L2 / L3。
> 任何 L3 → L2 的依赖都通过 **注入**（函数参数 / FastAPI Depends），保证 core 可在测试中完全离线运行。

---

## 3. 核心模块与契约

> 本节是 **对外契约的单一信源**。`src/rag_demo/` 下的模块签名必须严格匹配；任何变动必须先改本文 + 走 PR + 跑 `tests/test_smoke.py`。

### 3.1 模块总览

| 模块 | 文件 | 关键导出 | 行数（目标） |
|------|------|---------|------------|
| `ingest` | `src/rag_demo/ingest.py` | `ingest_directory`, `IngestStats`, `IngestFilters` | ≤ 200 |
| `retrieve` | `src/rag_demo/retrieve.py` | `retrieve`, `Hit` | ≤ 120 |
| `generate` | `src/rag_demo/generate.py` | `answer`, `AnswerResult` | ≤ 180 |
| `validate` | `src/rag_demo/validate.py`（**v0.3 新增**） | `is_defined_in_hits`, `DefinedCheck` | ≤ 80 |
| `web` | `src/rag_demo/web/main.py`（**新增**） | FastAPI app, router | ≤ 250 |
| `web.static` | `src/rag_demo/web/static/index.html`（**新增**） | 单 HTML 双面板 | ≤ 600 |
| `config` | `src/rag_demo/config.py`（**新增**） | `load_config`, `AppConfig` | ≤ 150 |
| `logging_setup` | `src/rag_demo/logging_setup.py`（**新增**） | `setup_json_logging`, `JsonLogRecord` | ≤ 80 |
| `errors` | `src/rag_demo/errors.py`（**新增**） | `AppError`, error code 字典 | ≤ 80 |
| `vault_uri` | `src/rag_demo/vault_uri.py`（**新增**） | `encode`, `decode` | ≤ 60 |
| `__main__` | `src/rag_demo/__main__.py`（**扩展**） | CLI 入口；新增 `up` / `web` 子命令 | ≤ 200 |

> 总目标代码量（不含测试 / 模板）≤ 2000 行 Python + ≤ 600 行 HTML。

### 3.2 ingest

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class IngestStats:
    files_total: int
    chunks_total: int
    skipped_unchanged: int   # 增量更新命中 mtime/sha 的文件数
    duration_ms: int
    state: str               # "idle" | "building" | "error"

def ingest_directory(
    data_dir: str | Path,
    index_dir: str | Path,
    *,
    full: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> IngestStats: ...
```

要点：

- **CLI 与 HTTP API 等价**（PRD §3.1 F3 + §6.1.3）：
  `rag-demo ingest --full` ⇔ `POST /api/ingest`，两者复用同一函数。
- **chunk 默认参数 `chunk_size=500, chunk_overlap=80`**（PRD §3.1 F2）。
- **增量更新范围**（PRD §3.1 F3）：仅启动时 mtime/sha diff；不引入 file-watcher。
- **写入**：`data/index/manifest.json`（已有 stub）+ 向量库子目录（路径 ADR-0002 拍板）。
- **错误**：`FileNotFoundError(data_dir)`、`ValueError(chunk_overlap >= chunk_size)` → 在 L4 包装成 `AppError(code=INGEST_INVALID_CONFIG, stage="ingest")`。

### 3.3 retrieve

```python
@dataclass(frozen=True)
class Hit:
    source: str              # vault://<vault>/<relpath>#<anchor>  (PRD §7.1)
    file: str                # 相对 vault 根的路径
    heading: str             # 命中所在 heading（原文，不做 slug）
    chunk_id: int            # 文件内唯一编号
    snippet: str             # 命中片段（≤ 200 字）
    score: float             # 0-1，ANN 返回值归一化

def retrieve(
    query: str,
    *,
    index_dir: str | Path,
    top_k: int = 5,
    filters: dict | None = None,    # {"folder": "AI/", "since": "2026-01-01"}
) -> list[Hit]: ...
```

要点：

- **空检索**（US4 触发条件）：返回 `[]`；调用方负责把它转成 `RETRIEVE_EMPTY`。
- **过滤器**：PRD §3.2 F11 是 Nice-to-Have，MVP 仅留接口、不强制实现；空 `filters={}` 等价于全库。
- **稳定排序**：`score` 降序；同分按 `file, chunk_id` 升序，便于测试断言。

### 3.4 validate（**v0.3 新增**，响应 Reviewer NB1）

```python
from typing import Callable

# 可注入的判定函数签名（PRD §8.2）
DefinedCheck = Callable[[str, list[Hit]], bool]

def is_defined_in_hits(query: str, hits: list[Hit]) -> bool:
    """判定规则初版（具体正则由 ADR-0001 拍板）：

    任一 hit 的 snippet 或 heading 包含 `query` 后接以下定义短语之一：
        "是 ..."、"为 ..."、"指 ...(是说)"、"：..."、"= ..."、": ..."、"- ..."

    若无任何 hit 命中上述模式 → False（走 US6 兜底）。
    """
```

要点：

- **纯函数**，无副作用、无 LLM 调用。pytest 直接断言行为。
- **正则来源**：v1 沿用 PRD §8.2 初版；ADR-0001 接受后更新为最终正则。
- **可注入**：`generate.answer` 默认 `defined_checker=is_defined_in_hits`，测试时可注入 mock。

### 3.5 generate

```python
@dataclass(frozen=True)
class AnswerResult:
    answer: str
    sources: list[Hit]
    decision: str            # "RETRIEVE_EMPTY" | "NOT_DEFINED" | "GENERATED"

def answer(
    question: str,
    hits: list[Hit],
    *,
    defined_checker: DefinedCheck = is_defined_in_hits,
) -> AnswerResult: ...
```

要点：

- **签名扩展**（handoff §开发待办）：v0.3 把 `defined_checker` 注入到签名，默认走新逻辑；旧无参调用兼容。
- **决策链**（PRD §8.2 v0.3 强化）：
  1. `hits` 为空 → `AnswerResult(answer="未在笔记中找到相关内容", sources=[], decision="RETRIEVE_EMPTY")`
  2. `hits` 非空但 `defined_checker(question, hits) == False` → `AnswerResult(answer="你的笔记里没找到 {q} 的明确定义，仅有的相关片段是：...", sources=hits, decision="NOT_DEFINED")`（**不发 LLM**）
  3. `hits` 非空且 `defined_checker(...) == True` → 走 LLM 生成；返回 `decision="GENERATED"`
- **错误**：`RETRIEVE_EMPTY` / `NOT_DEFINED` **不是异常**，是合法返回值；只有 `GENERATED` 失败才抛 `AppError(code=GENERATE_LLM_FAIL, stage="generate")`。

### 3.6 web（FastAPI，薄壳）

```
POST /api/chat           非流式问答（兜底）
POST /api/chat/stream    SSE 流式问答（**推荐默认**，PRD §7.2）
POST /api/search         纯检索（不调 LLM，F4 左栏）
POST /api/ingest         触发全量重建（等价 CLI ingest --full）
GET  /api/config         当前生效配置（不含 secret）
GET  /api/index/status   索引状态（idle | building | error）
GET  /api/health         健康检查
POST /api/usage          北极星埋点（写 data/usage/local-{date}.jsonl）
```

要点：

- **薄壳**：每个端点 ≤ 30 行；只做参数校验 → 调 core → 套错误壳。
- **SSE 协议**（PRD §7.3）：
  - `event: token` / `data: {"delta": "..."}` 流式片段
  - `event: sources` / `data: {"sources": [...]}` 一次发完整列表
  - `event: meta` / `data: {"retrieved": N, "cost_ms": {"retrieve": 120, "generate": 1830}}` 收尾
  - `event: error` / `data: {"error": {...}}` 异常路径（不破坏 SSE 连接）
- **错误响应**（PRD §5 + §7.3）：统一 `{"error": {"code": "...", "message": "...", "stage": "..."}}`，4xx/5xx 一律此格式。
- **静态文件**：`src/rag_demo/web/static/index.html` 由 FastAPI `StaticFiles` mount 在 `/` 下；冷启动 demo 5 条示例问题在这里硬编码（响应 §3.1 F8 + §8.2）。

### 3.7 CLI

```bash
rag-demo ingest [--data DIR] [--index DIR] [--chunk-size N] [--chunk-overlap N] [--full/--incremental]
rag-demo ask "question" [--index DIR] [--top-k N]
rag-demo doctor
rag-demo up [--host 127.0.0.1] [--port 8000]     # 启动 FastAPI（**v0.3 新增**）
rag-demo web   [--host 127.0.0.1] [--port 8000]   # 等价于 up；别名便于 IDE
```

要点：

- **`up` 是新子命令**（handoff §开发待办提的 `POST /api/ingest` 触发 → CLI 也要有等价入口；否则 web 起得来但没人触发 ingest）。
- **`doctor` 输出增加"config 文件存在与否"行**：方便排查 §3.1 F1 默认配置问题。
- **CLI 不引入新日志格式**——直接复用 L4 `logging_setup`。

---

## 4. 数据流（端到端）

### 4.1 冷启动 demo 路径（F8）

```
T=0      user:  uv run rag-demo up
T+0.5s   rag-demo up:
           - load config.yaml (或 fallback 冷启动 demo 路径, 见 PRD §3 F1)
           - mount FastAPI
           - 后台线程启动 ingest_directory(data_dir, index_dir, full=True)
T+1s     browser GET /static/index.html  →  HTML 字节流出
T+1.5s   browser 渲染 → 显示"5 条示例问题"按钮 + "索引构建中 (0/N)" 进度
           前端立即用示例问题 #1 → POST /api/chat/stream
T+2s     /api/chat/stream: retrieve(示例 #1) → hits[]
                                  is_defined_in_hits(#1, hits)
                                  answer(#1, hits) → 流式返回
T+30s?   如果 30s 时 ingest 还没完成:
           前端必须仍然看到示例按钮可点击 ✅ (PRD §3 F8 + §8.2 断言)
T+?min   ingest 完成 → GET /api/index/status → state=idle
           前端收到 SSE 通知 → 解锁"问你的笔记"入口
```

**断言**（`tests/test_cold_start.py`，PRD §8.2 v0.3 新增）：
- 计时点：`index.html` 首字节 → 5 条示例按钮 DOM `clickable` 属性置位。
- 阈值：mock 后端 5s 内返回 / 真实后端 30s 内必须可点击；超时记入 §8.4 冷启动放弃率埋点。

### 4.2 正常问答路径（F4 / F5）

```
browser POST /api/chat/stream
       │
       ▼
[web.main.chat_stream]
       │ question, top_k, selected_sources
       ▼
retrieve(question, top_k=5)  ──▶ hits[]
       │
       ▼
is_defined_in_hits(question, hits)  ◀── pure function, no LLM
       │
       ├─ False  →  answer() 早返 decision=NOT_DEFINED
       │            SSE: token="你的笔记里没找到..." + sources + meta
       │
       └─ True   →  LLM.stream(question, hits)
                     SSE: token × N + sources + meta
```

### 4.3 纯检索路径（F4 左栏）

```
browser POST /api/search {"query": "...", "top_k": 5, "filters": {...}}
       │
       ▼
[web.main.search]
       │
       ▼
retrieve(query, top_k=5, filters=filters)  ──▶ list[Hit]
       │
       ▼
JSON {"hits": [...]}
       │ (无 LLM 调用)
       ▼
browser 左栏渲染 Top-K 列表；用户点选若干条 → 二次"基于这些给我讲一下"
                                    → 走 §4.2 路径，selected_sources 传入
```

### 4.4 全量重建路径（F3）

```
CLI:                rag-demo ingest --full
                       │
HTTP:               POST /api/ingest  {"full": true}
                       │
                       ▼
              ingest_directory(data, index, full=True)
                       │
                       ▼
              ┌─── full=True ──▶  全量 walk + chunk + embed + write
              │
              └─── full=False ──▶ 增量 walk + mtime/sha diff
                                    ├─ 新增 → 走 embedding pipeline
                                    ├─ 修改 → 删除旧 chunk + 重 embed
                                    └─ 删除 → 清 manifest 中条目
```

- **Web UI 不直接触发全量重建**（PRD §3 F3 + Reviewer NS4）：前端只展示 `/api/index/status`；触发必须经 CLI 或 API 调用方知情同意。

---

## 5. 接口契约（与 PRD §7 对齐）

| Method | Path | 调用 core | 状态 | 备注 |
|--------|------|----------|------|------|
| POST | `/api/chat` | `retrieve → answer` | 必做 | 非流式兜底 |
| POST | `/api/chat/stream` | `retrieve → answer(stream=True)` | 必做 | SSE，首字 ≤ 2s |
| POST | `/api/search` | `retrieve` | 必做 | 无 LLM |
| POST | `/api/ingest` | `ingest_directory(full=True)` | 必做 | 等价 CLI |
| GET | `/api/config` | `config.effective()`（脱敏） | 必做 | 不返回 API key |
| GET | `/api/index/status` | `ingest.status()` | 必做 | F8 冷启动轮询 |
| GET | `/api/health` | — | 必做 | 200 / 503 |
| POST | `/api/usage` | `usage.log(event)` | 必做 | 仅写 `data/usage/local-{date}.jsonl` |
| POST | `/api/usage/query` | `usage.aggregate()` | 选做 | 用于自检冷启动放弃率等 |

错误响应格式（PRD §5 强制）：

```json
{ "error": { "code": "RETRIEVE_EMPTY", "message": "未在笔记中找到相关内容", "stage": "retrieve" } }
```

错误码字典（`src/rag_demo/errors.py` 单一信源）：

| code | stage | 含义 | 触发 |
|------|-------|------|------|
| `INGEST_INVALID_CONFIG` | ingest | chunk 参数非法 / vault 路径不存在 | `ingest_directory` 启动期 |
| `INGEST_BUILD_FAIL` | ingest | embedder 抛错 | `ingest_directory` 中段 |
| `RETRIEVE_EMPTY` | retrieve | Top-K = 0 | `retrieve` 返回 `[]` |
| `RETRIEVE_INDEX_MISSING` | retrieve | `data/index/` 不存在或为空 | `retrieve` 启动期 |
| `NOT_DEFINED` | generate | US6 命中 | `answer()` 早返 |
| `GENERATE_LLM_FAIL` | generate | LLM API 5xx / 超时 | `answer()` 中段 |
| `GENERATE_INVALID_QUESTION` | generate | question 为空 / 超长 | `answer()` 启动期 |
| `CONFIG_LOAD_FAIL` | infra | config.yaml 解析失败 | `config.load()` |
| `USAGE_LOG_FAIL` | infra | 写 jsonl 失败 | `usage.log()` |

---

## 6. 配置 / 日志 / 错误（横切）

### 6.1 配置

```yaml
# config.example.yaml（不提交真实 key；真实值走 .env）
vault:
  path: ~/Documents/ObsidianVault        # 或空 → 走 F8 冷启动 demo
  name: my-notes                         # 用于 vault:// 的 {vault}
  include_extensions: [".md"]            # MVP 仅 .md

ingest:
  chunk_size: 500                        # PRD §3 F2
  chunk_overlap: 80
  full: true                             # 默认全量；增量由 CLI 开关

retrieve:
  top_k: 5
  filters: {}                            # MVP 占位

generate:
  defined_check:                        # ADR-0001 拍板前为空走 PRD §8.2 初版
    pattern: ""
  llm:
    provider: ollama                     # ollama | openai | anthropic
    model: qwen2.5
    base_url: http://localhost:11434     # Ollama 默认
  embedding:
    provider: ollama                     # ollama | openai
    model: nomic-embed-text

web:
  host: 127.0.0.1
  port: 8000

usage:
  enabled: true
  dir: ./data/usage
```

- **加载顺序**：`./config.yaml` → `./config.example.yaml` → 内置默认值（冷启动 demo）。
- **API key 注入**：通过 `.env`，**严禁写入 config.yaml**（PRD §6.2.3）。
- **`./config.yaml` 不存在**：README 提示用 `config.example.yaml` 起步；第一次启动时若 `vault.path` 未配置，**走 §3.1 F8 冷启动 demo 路径**而非报错（PRD §3 F1）。

### 6.2 日志

- **格式**（PRD §5 强制）：
  ```json
  {"ts":"2026-06-24T07:30:00.123Z","level":"INFO","stage":"retrieve","cost_ms":120,"msg":"top_k=5 hits=3"}
  ```
- **实现**：`logging_setup.setup_json_logging()`；使用 `logging` stdlib + 自定义 `JsonFormatter`。
- **stage 取值**：`ingest` / `retrieve` / `generate` / `infra` / `web`。
- **不打印大段 payload**：snippet 只在 `DEBUG` 级；INFO 只打命中数 / 耗时。

### 6.3 错误

- **业务错误统一抛 `AppError`**（`src/rag_demo/errors.py`），由 L4 → L3 的边界处统一捕获并转 JSON。
- **HTTP 状态码映射**：
  - `RETRIEVE_EMPTY` → 200 + `decision="RETRIEVE_EMPTY"`（**业务正常**，不是错误；前端按 `decision` 分支渲染）
  - `NOT_DEFINED` → 200 + `decision="NOT_DEFINED"`（同上）
  - `GENERATE_LLM_FAIL` / `INGEST_BUILD_FAIL` / `RETRIEVE_INDEX_MISSING` → 503
  - `*_INVALID_*` → 400
  - `CONFIG_LOAD_FAIL` → 500

---

## 7. 启动顺序与依赖

### 7.1 ADR 依赖图（**先 0001 → 0003 → 0002 → 0004 → 0005**）

```
   ADR-0001 (LLM 框架) ─────────────┐
        │                            │
        ▼                            ▼
   ADR-0003 (Embedding/LLM 来源)   ADR-0002 (向量库)
        │                            │
        └──────────┬─────────────────┘
                   ▼
              ADR-0004 (Web 框架)
                   │
                   ▼
              ADR-0005 (前端形态)
```

理由（handoff §开发待办）：0001 的取舍会反向影响 0003（本地 Ollama vs 远程 SDK 框架差异）；二者都稳定后，0002 才能在框架的 embedding interface 之上选合适的向量库；0004 依赖核心契约稳定；0005 是最后一公里。

### 7.2 启动顺序（用户视角）

```bash
git clone https://github.com/maqy1995/rag-demo
cd rag-demo
uv python install 3.12
uv sync --extra <按 ADR 选定的 extras> --extra dev
cp config.example.yaml config.yaml       # 编辑 vault.path / model 名称
uv run rag-demo up                       # 启动 FastAPI + 后台 ingest
# 浏览器打开 http://127.0.0.1:8000/
```

### 7.3 内部模块导入顺序（防止循环依赖）

```
errors ──▶ vault_uri ──▶ config ──▶ logging_setup ──▶ validate ──▶ ingest ──▶ retrieve ──▶ generate ──▶ web/CLI
```

> 任何反向依赖都视为架构违规；code review 必查。

---

## 8. 性能 / 资源 / 可观测

### 8.1 性能预算（PRD §5）

| 指标 | 预算 | 条件 | 测量点 | 测试位置 |
|------|------|------|--------|---------|
| 首字延迟（流式） | ≤ **2 s** | Vault ≤ 1k 切片 + 本地 LLM | SSE 第一个 `event: token` 时间戳 | `tests/test_chat.py::test_first_byte_latency` |
| 总延迟（非流式） | ≤ **10 s** | 同上 | HTTP 响应完整时间 | `tests/test_chat.py::test_total_latency` |
| 冷启动 demo | ≤ **30 s** | `index.html` 首字节 → 5 按钮可点击 | Playwright / 纯计时 | `tests/test_cold_start.py` |
| 增量更新 | ≤ **30 s** | 改动 ≤ 10 个文件 | CLI `ingest` 退出耗时 | `tests/test_smoke.py::test_ingest_incremental` |
| 全量建索引（3b） | README 列预期 | 100 篇 ≈ 5–15 min（远程） / 2–3×（本地） | README §"性能预期" | 仅文档 |

### 8.2 资源占用

- **内存**：≤ 1 GB（Ollama 默认 qwen2.5 7B ≈ 5 GB；按用户配置可升）。
- **磁盘**：`data/index/` ≤ 100 MB（1k 切片、bge-small 向量）；`data/usage/` 按 100 事件/天 ≈ 10 KB/天。
- **不强制 GPU**；Embedding 走 API 或 Ollama CPU。

### 8.3 可观测

- **日志**：§6.2 一行 JSON；启动 / ingest 完成 / 检索命中数 / 问答耗时都按此格式。
- **埋点**：§8.4 北极星指标，仅落 `data/usage/local-{date}.jsonl`，**无任何外发**（PRD §5 v0.3 + §8.4 v0.3）。
- **不使用** sentry / datadog / 全链路追踪——MVP 阶段本地优先、零运维。

---

## 9. 测试策略

### 9.1 测试金字塔

```
        ┌──────────────────────────────────┐
        │ E2E  tests/test_cold_start.py    │  冷启动 30s 断言（Playwright 计时）
        ├──────────────────────────────────┤
        │ 集成 tests/test_chat.py          │  US4 / US6 / happy path（mock LLM = unreachable）
        │       tests/test_web.py          │  FastAPI 端点 + SSE 帧
        │       tests/test_ingest.py       │  mtime/sha diff 增量逻辑
        ├──────────────────────────────────┤
        │ 单元  tests/test_validate.py      │  is_defined_in_hits 正反例（纯函数）
        │       tests/test_retrieve.py     │  排序 / 过滤器 / 空检索
        │       tests/test_config.py       │  config 加载 + .env 注入
        │       tests/test_errors.py       │  AppError → JSON 映射
        │       tests/test_vault_uri.py    │  vault:// 编解码
        ├──────────────────────────────────┤
        │ 烟雾  tests/test_smoke.py        │  CLI end-to-end（已有）
        └──────────────────────────────────┘

        评估  scripts/eval_recall.py       │  Recall@5 ≥ 80% on 10 题样例（PRD §8.1）
```

### 9.2 关键断言

- **US4**（`test_chat.py::test_us4_empty_hits`）：`retrieve` 返回 `[]` → `answer(question, [])` → `decision == "RETRIEVE_EMPTY"`；mock LLM = `unreachable`，LLM **未被调用**。
- **US6**（`test_chat.py::test_us6_no_definition`）：mock `defined_checker` 返回 `False` → `answer()` → `decision == "NOT_DEFINED"`；mock LLM = `unreachable`，LLM **未被调用**。
- **happy path**（`test_chat.py::test_happy_path`）：mock `defined_checker` 返回 `True` → LLM 被调用一次 → `decision == "GENERATED"`；mock LLM 校验 prompt 包含 `hits` 片段。
- **冷启动 30s**（`test_cold_start.py`）：mock `ingest_directory` 延迟 5s → 计时前端首字节到示例按钮可点击 ≤ 30s。

### 9.3 不要在测试里做的事

- ❌ 调真实 LLM API（`unreachable` mock 是断言 LLM 不被调用的唯一可信手段）。
- ❌ 把 `data/raw/` 仓库自带样本塞进 git（`.gitignore` 守住）。
- ❌ 跳过 `pytest -q` 就提交。

---

## 10. 验收对照（PRD §8）

| PRD 章节 | 验收点 | 实现位置 | 测试 | 状态 |
|---------|--------|---------|------|------|
| §8.1 Recall | Top-5 ≥ 80% on 10 题 | `scripts/eval_recall.py` + `data/index.sample/` | `pytest -m eval` | 待产品提供 10 题（S2） |
| §8.2 US4 | 空检索 → RETRIEVE_EMPTY 文案 | `generate.answer` | `test_chat.py::test_us4_empty_hits` | 设计落地 |
| §8.2 US6 | 找到但无定义 → NOT_DEFINED | `validate.is_defined_in_hits` + `generate.answer` | `test_chat.py::test_us6_no_definition` | 设计落地 |
| §8.2 冷启动 30s | 前端首字节 → 按钮可点击 ≤ 30s | `tests/test_cold_start.py` | `test_cold_start.py` | 设计落地 |
| §8.3 3a | 新环境 ≤ 3 分钟 demo | README + `data/index.sample/`（**待建**） | 手工 / smoke | 缺产物 |
| §8.3 3b | 100 篇 ≈ 5–15 min | README §性能预期 | 文档 | 文档落地 |
| §8.4 活跃频次 | 5 天 ≥ 3 次/天 | `POST /api/usage` → `data/usage/` | 上线后观测 | 设计落地 |
| §8.4 引用点击率 | ≥ 30% | 同上 + 前端埋点 | 上线后观测 | 设计落地 |
| §8.4 冷启动放弃率 | < 20% | 前端 + `/api/usage/query` | 上线后观测 | 设计落地 |

> 8.3 3a 缺 `data/index.sample/` 是开发侧阻塞（S2 软阻塞也依赖产品 10 题样例）。已在 §11 挂出。

---

## 11. 阻塞 / 待办（PRD §11 + 软待办）

### 11.1 硬阻塞（不解除则无法进入实现 v1）

| # | 阻塞项 | Owner | 截止 | 状态 | 影响 |
|---|--------|-------|------|------|------|
| B1 | ADR-0001 LLM 框架 | 开发 | MAQ-5 close 前 | **未起草** | LLM 框架未定 → `generate.answer` 实现无法选型 |
| B2 | ADR-0002 向量库 | 开发 | MAQ-5 close 前 | **未起草** | `retrieve` 实现无法选型 |
| B3 | ADR-0003 Embedding/LLM 来源 | 开发 | MAQ-5 close 前 | **未起草** | `config.yaml` `provider` 字段未定 |
| B4 | ADR-0004 Web 框架 | 开发 | MAQ-5 close 前 | **未起草** | `web/main.py` 无法动工 |
| B5 | ADR-0005 前端形态 | 开发 | MAQ-5 close 前 | **未起草** | `index.html` 无法动工 |
| B6 | Vault 规模预期（笔记数 / 单文件大小） | **产品** | MAQ-5 close 前 | 待产品 | 性能预算 §8.1 数字需复核 |
| B7 | 是否需要图片 / PDF | **产品** | MAQ-5 close 前 | 待产品 | 影响切片策略 |
| B8 | 是否需要登录 / 鉴权 | **产品** | MAQ-5 close 前 | 待产品 | 影响 §6.1 横切 |

> **B1–B5 起草顺序**：按 §7.1 ADR 依赖图串行。

### 11.2 软阻塞（不阻塞 in_progress，但在对应 ADR 落地前答复）

| # | 阻塞项 | Owner | 影响 |
|---|--------|-------|------|
| S1 | 5 条示例问题清单 | 产品 + 用户 | §3 F8 冷启动 demo 内容 |
| S2 | Recall 评估 10 题样例集 + ground truth | 产品 | §8.1 评估无法跑 |
| S3 | 参考日志 JSON schema 草稿 | 开发 | §6.2 schema 二次校验（开发可自提） |
| S4 | `data/index.sample/` 内置示例索引 | 开发 | §8.3 3a ≤3 分钟 demo |

### 11.3 设计本轮遗留（合入前自清）

- [ ] `src/rag_demo/validate.py` 落地（**首个开发工单**）
- [ ] `src/rag_demo/config.py` / `logging_setup.py` / `errors.py` / `vault_uri.py` 四个 L4 模块落地
- [ ] `generate.answer` 签名扩展（带 `defined_checker`），旧签名保留
- [ ] `__main__.py` 新增 `up` 子命令
- [ ] `tests/test_smoke.py` 不变；新增 `test_validate.py` / `test_chat.py` / `test_cold_start.py` 骨架

---

## 12. 修订记录

| 日期 | 版本 | 变更 | 来源 |
|------|------|------|------|
| 2026-06-24 | v1 | 首版：基于 PRD v0.3（[MAQ-7](mention://issue/0798b1d3-0fca-44dd-84bf-9c40e49d6e47)）落地，把"三段式 stub + 待决项"骨架扩为分层架构 + 契约 + 决策链 + 验收对照 | [MAQ-8](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab) |

---

## 附录 A — 与 v0.1 占位 design.md 的差异

| 原占位内容 | 本文对应章节 |
|-----------|------------|
| 三段式 pipeline 简图 | §2.1（含 L1–L4 分层） |
| "retrieve 是 stub" | §3.3（完整签名 + 排序 / 过滤器约定） |
| "generate 是 stub" | §3.5（决策链 + US4/US6 早返） |
| 待决项表（4 项） | §7.1 ADR 依赖图 + §11.1 B1–B5 |
| — | §3.4 `validate.py` 新模块（响应 Reviewer NB1） |
| — | §4 端到端数据流（冷启动 / 问答 / 检索 / 重建 四路径） |
| — | §5 接口契约 + 错误码字典 |
| — | §6.1/6.2/6.3 横切（配置 / 日志 / 错误） |
| — | §8 性能 / 资源 / 可观测 |
| — | §9 测试金字塔 + 关键断言 |
| — | §10 PRD §8 验收逐条对照 |

## 附录 B — 跨文档引用

- PRD：[docs/product/specs/MAQ-5-prd-kb-qa.md](../product/specs/MAQ-5-prd-kb-qa.md)
- 上轮 review：[docs/review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md](../review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md)
- 上轮 handoff：[docs/handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md](../handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md)
- 本轮 handoff：[docs/handoffs/2026-06-24-from-dev-to-reviewer-design.md](../handoffs/2026-06-24-from-dev-to-reviewer-design.md)（详见交付时的交接单）
- 架构图（旧占位）：[docs/architecture.md](../architecture.md)（本设计 §2.1 落地后，旧图保留作历史快照；后续可在 review 后替换）
- ADR 模板：[docs/adr/0000-template.md](../adr/0000-template.md)
- Code Review 清单：[docs/review/checklists/code-review.md](../review/checklists/code-review.md)
- 开发 Runbook：[docs/dev/runbooks/local-dev.md](./runbooks/local-dev.md)
- 环境 Runbook：[docs/envops/runbooks/local-dev.md](../envops/runbooks/local-dev.md)
# 0001. LLM 框架 — 直裸 OpenAI 兼容 SDK + 极薄抽象

> multica-issue: [MAQ-26](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890)
> 状态：**Accepted**（owner 2026-06-25 在 [MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d) 拍板）
> 日期：2026-06-25
> 提议人：资深全栈开发工程师（`01386b69…`）

## 背景

[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 描述里 owner 明确：

> 客户可以调用远程 API 的 LLM 服务或 embedding 服务，包括智谱、MiniMax 或者小米 Mimo 等。

这与 [PRD v0.3](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) §6.1.6 原"默认本地 Ollama、远程作为可选"是**反向**调整。我们需要一个 LLM 框架选型：

- 覆盖 4 家 provider（OpenAI / 智谱 GLM / MiniMax / 小米 Mimo）
- embedding 与 LLM **解耦**（owner 拍板新增约束）
- 决策链（design §3.5）保持硬编码早返（不依赖 LLM 服从 prompt）

## 候选方案

### 方案 A — LangChain

- 优点：社区生态全、provider 切换最快、链式抽象齐。
- 缺点：抽象泄漏重（chain / agent / retriever 强绑定）；prompt 模板与 design §3.5 决策链整合需绕；依赖臃肿（pull 几十个包）；本地 stub 测试要用 `langchain_core.language_models.fake.FakeListLLM` 等额外 mock 设施。
- **评估**：不采纳。

### 方案 B — LlamaIndex

- 优点：比 LangChain 轻、RAG 抽象（QueryEngine / Index）齐。
- 缺点：仍在抽象层；RAG 抽象是为"通用 RAG"设计，与本项目"三段式骨架 + 决策链"重叠且冲突；增量更新 / status 单一信源等本项目特有约束要"绕过"框架。
- **评估**：不采纳。

### 方案 C — **直裸 OpenAI 兼容 SDK + 极薄抽象**（采纳）

- 优点：
  - 4 家 provider **全部声明 OpenAI 兼容**（OpenAI 自家 + 智谱 OpenAI 兼容端点 + MiniMax 兼容端点 + Mimo 兼容端点）→ 一个 `openai` SDK + base_url + api_key + model 三元组就能覆盖，**无需 4 个 adapter**。
  - 依赖最薄：`openai>=1.30` 一个包 + `httpx`（openai 传递依赖）。
  - 决策链（design §3.5）继续走 `generate.answer` 的硬编码早返——LLM 仅在第 3 段被调；不依赖 prompt 工程的"听话"。
  - 流式输出是 `openai` SDK 一等公民（`client.chat.completions.create(stream=True)`），直接对应 design §3.6 SSE `event: token` 协议。
- 缺点：
  - 切到 Anthropic / Google 等**非 OpenAI 兼容** provider 时要自写 adapter（v1 范围不涉及，列为未来扩展点）。
  - 4 家 provider 的"小怪癖"（如部分仅支持 `temperature >= 0.5`、部分要求 `model` 写完整版本号）要在 adapter 里显式处理。

## 决议

**采纳方案 C**。理由汇总：

1. **覆盖度**：4 家 provider 全 OpenAI 兼容 → 一个 client 即可（base_url + api_key + model 切换），MAQ-31/32 工时从 2d+1d 缩到 **1d+0.5d**。
2. **依赖最薄**：MVP 阶段"组件尽量少"（PRD §1.1）原则要求。
3. **决策链清晰**：`generate.answer` 早返路径不依赖 LLM 行为（US4 / US6 测试用 `unreachable_llm` 显式 raise）；引入 LangChain 反而要绕它的 chain 抽象。
4. **流式一等公民**：`openai` SDK `stream=True` 天然对应 design §3.6 SSE 协议。

## 实施范围

### 新增模块

| 路径 | 行数预算 | 职责 |
|------|---------|------|
| `src/rag_demo/llm/__init__.py` | ≤ 10 | 模块导出 |
| `src/rag_demo/llm/base.py` | ≤ 80 | `BaseLlmClient` / `BaseEmbedder` 抽象基类 + dataclass（`LLMConfig` / `EmbedConfig`） |
| `src/rag_demo/llm/openai_compat.py` | ≤ 120 | `OpenAICompatibleClient`（一个类覆盖 4 家）+ 错误映射（401/403/429/5xx → `AppError`） |
| `tests/test_llm_base.py` | ≤ 100 | 接口契约 + 参数校验 + retry 行为（≥ 5 断言） |

### 接口签名

```python
# base.py
from collections.abc import Iterator
from dataclasses import dataclass
from .retrieve import Hit


@dataclass(frozen=True)
class LLMConfig:
    provider: str         # "openai" | "zhipu" | "MiniMax" | "mimo"
    model: str            # "gpt-4o-mini" / "glm-4-flash" / "abab-7-chat" / "mimo-7b"
    base_url: str         # "https://api.openai.com/v1" 等
    api_key: str          # 来自 .env 注入
    timeout_s: float = 30.0
    max_retries: int = 2


class BaseLlmClient:
    def __init__(self, config: LLMConfig) -> None: ...
    def stream(self, question: str, hits: list[Hit]) -> Iterator[str]:
        """流式生成 — 每段 yield 一个 token 片段 (SSE event: token.data.delta)."""
        raise NotImplementedError


@dataclass(frozen=True)
class EmbedConfig:
    provider: str         # 同上（可与 LLM 独立）
    model: str            # "text-embedding-3-small" / "embedding-2" / "embo-01" / "mimo-embedding"
    base_url: str
    api_key: str
    timeout_s: float = 30.0
    batch_size: int = 64


class BaseEmbedder:
    def __init__(self, config: EmbedConfig) -> None: ...
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embed — 返回与 texts 等长的向量列表."""
        raise NotImplementedError
    def embed_one(self, text: str) -> list[float]:
        """单条便捷方法 — 内部转 embed([text])[0]."""
        return self.embed([text])[0]
```

### openai_compat.py 关键设计

- **单类多 provider**：`OpenAICompatibleClient(LLMConfig)` 构造时 `self._client = openai.OpenAI(base_url=config.base_url, api_key=config.api_key)`——4 家都用 `openai.OpenAI`，差异**仅在 config**。
- **流式 yield**：`for chunk in self._client.chat.completions.create(..., stream=True): yield chunk.choices[0].delta.content or ""`
- **错误映射**：捕获 `openai.APIStatusError` / `openai.APIConnectionError` / `openai.RateLimitError` → 转 `AppError(code="GENERATE_LLM_FAIL" / "EMBEDDING_FAIL", stage="generate" / "ingest", http_status=e.status_code if available else 503)`。
- **不引入 LangSmith / Langfuse 之类的可观测中间件**（与 design §8.3"不使用 sentry / datadog"一致）。

### 修改模块

| 路径 | 改动 |
|------|------|
| `src/rag_demo/config.py` | `AppConfig` 加 `llm_provider` / `llm_model` / `llm_base_url` / `embedding_provider` / `embedding_model` / `embedding_base_url` / `api_key_env` 字段；从 `.env` 读对应 `*_API_KEY` 注入 |
| `src/rag_demo/errors.py` | `ERROR_CODES` 加 `EMBEDDING_FAIL = {http_status: 503, stage: "ingest", message: "embedding 调用失败"}`（LLM 复用 `GENERATE_LLM_FAIL`） |
| `src/rag_demo/generate.py` | `_call_llm` 替换为 `BaseLlmClient.stream(...)` 调用；模块级 import + 默认实例化（`@lru_cache` 单例） |
| `src/rag_demo/ingest.py` | 加 `embedder: BaseEmbedder | None` kwarg，stub 阶段用 `None` 跳过真实 embed（保留 status.json / manifest.json 写盘逻辑） |
| `src/rag_demo/__main__.py` | `_cmd_up` 启动期检查 `OPENAI_API_KEY`（默认 provider）是否设置；未设则 print 警告 + 让 web 启动但 `/api/chat` 会 fail-fast |
| `src/rag_demo/web/main.py` | `/api/chat/stream` 与 `/api/chat` 调用 `BaseLlmClient.stream()` 流式；SSE `event: token` 帧 yield |
| `.env.example` | 改为只放 `OPENAI_API_KEY` / `ZHIPU_API_KEY` / `MIMAX_API_KEY` / `MIMO_API_KEY`（**分别命名**，不合并）；删 `LLM_PROVIDER` / `VECTOR_STORE` / `TOP_K` / `CHUNK_SIZE` / `CHUNK_OVERLAP` / `DATA_DIR` / `INDEX_DIR`（这些走 config.yaml，与 NI1 处置一致） |
| `pyproject.toml` | `[project.optional-dependencies]` 加 `llm = ["openai>=1.30", "httpx>=0.27"]`（与 `web` / `vector` extras 并列） |
| `README.md` | §"Quick start" 同步改 `.env` 描述 + provider 切换说明 |

### 测试改动

- **新增** `tests/test_llm_base.py`（≥ 5 断言）：
  - `OpenAICompatibleClient` 用 `unittest.mock.patch("openai.OpenAI")` mock 父 SDK → 不真发请求
  - 覆盖 4 家 base_url 都能正确构造 client
  - `stream` 流式 yield 顺序与 `delta.content` 拼装正确
  - 401 / 429 / 5xx 错误映射到正确 `AppError.code` / `http_status`
  - `BaseEmbedder.embed_one` 调用 `embed([text])[0]`
- **保留** 现有 80 测试全绿（`test_chat.py` 用 `unreachable_llm` 显式 raise 测 US4/US6 决策链——本 ADR 落地后这层 mock 改成 `@patch("rag_demo.llm.openai_compat.OpenAICompatibleClient.stream")`，行为不变）
- **保留** NB1 SSE `cost_ms.generate` 用 `t_after_retrieve` 计时（MAQ-23 已合入）

## 验证标准

1. `docs/adr/0001-llm-framework.md` 存在（本文件）— 状态 **Accepted**
2. `src/rag_demo/llm/{base,openai_compat}.py` 落地，按接口签名实现
3. `tests/test_llm_base.py` ≥ 5 断言 + 旧 80 测试全绿 + ruff 全过
4. `.env.example` / `pyproject.toml` / `config.py` 同步更新
5. `multica issue status f8d606a7-… in_review`（合入前 reviewer 复审）

## 依赖与下一步

- **本 ADR 是 stage 1**：完成后唤醒 dev agent → 开 MAQ-28 (ADR-0003 provider) 阶段 stage 2
- **本 ADR 是 Phase B 真实接入的前置**：MAQ-31 (BaseLlmClient 真接 4 家) / MAQ-32 (BaseEmbedder 真接 4 家) 都依赖本 ADR
- **不依赖** MAQ-27 / MAQ-29 / MAQ-30（stage 2 与本 ADR 平行）

## 异议

> （暂无。Reviewer 复审时若有反对意见，按时间倒序记在这里。）

## 跨文档引用

- 父 issue：[MAQ-26](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890)
- 根 issue：[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
- 拍板评论：[MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d)
- 上游：[PRD v0.3](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) §6.1.6 + [design v1.1](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab) §3.5 §3.6 §7.1
- 后续 ADR：[0003 provider](mention://issue/89764482-428b-4fa5-9c8a-385859e9423f)（MAQ-28）/ [0002 vector store](mention://issue/fa03584b-ece9-4729-a437-2ee694fa170e)（MAQ-27）

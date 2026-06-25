# 0003. Embedding / LLM 来源 — 4 provider 解耦 + 无 Ollama

> multica-issue: [MAQ-28](mention://issue/89764482-428b-4fa5-9c8a-385859e9423f)
> 状态：**Accepted**（owner 2026-06-25 在 [MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d) 拍板）
> 日期：2026-06-25
> 提议人：资深全栈开发工程师（`01386b69…`）

## 背景

[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 描述里 owner 明确：

> 客户可以调用远程 API 的 LLM 服务或 embedding 服务，包括智谱、MiniMax 或者小米 Mimo 等。

owner 在 MAQ-25 评论 `d560c6ca-…` 进一步拍板：
1. 4 家 provider 必支持：**OpenAI / 智谱 GLM / MiniMax / 小米 Mimo**
2. **embedding 与 LLM provider 解耦**（`generate.llm.provider` 与 `generate.embedding.provider` 分别配置）
3. **不考虑本地 Ollama**（不再有 fallback）
4. 抽象方式：`BaseLlmClient` + `BaseEmbedder` 抽象基类

[ADR-0001](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) 已决议用直裸 OpenAI 兼容 SDK（理由：4 家都声明 OpenAI 兼容）；本 ADR 把 provider 配置 + 4 家实际端点 + `.env` 字段落字。

## 候选方案

### 方案 A — 各家单独 adapter

- 优点：每家 provider 行为差异显式处理（认证 header、流式协议、错误码）；
- 缺点：4 个 adapter × 2 接口（LLM + Embedder）= 8 个文件 + 8 套测试；owner 拍板"4 家都 OpenAI 兼容"——重复样板代码。
- **评估**：不采纳（违反"DRY"且无必要）。

### 方案 B — **统一 OpenAI 兼容 client + 4 家仅 config 切换**（采纳）

- 优点：基于 [ADR-0001](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) 的 `OpenAICompatibleClient` / `OpenAICompatibleEmbedder`，provider 切换是 `base_url` + `api_key` + `model` 三元组切换；零运行时 if-else 分支；新增第 5 家时只需 config YAML 加一段。
- 缺点：4 家"小怪癖"（如部分仅支持 `temperature >= 0.5`、部分要求 `model` 写完整版本号）要靠 model 名字 string 隐式处理；不能显式 per-provider hooks。
- **评估**：采纳。理由：owner 明示"全部按推荐来" + 4 家都 OpenAI 兼容是公开事实。

## 决议

**采纳方案 B**。理由汇总：

1. **DRY**：1 个 `OpenAICompatibleClient` 类覆盖 4 家 LLM；1 个 `OpenAICompatibleEmbedder` 类覆盖 4 家 embedding。
2. **config 驱动**：`config.yaml::generate.llm.{provider,model,base_url,api_key_env}` + `embedding.{...}` 分别配置，4 家无 if-else。
3. **解耦**：LLM 与 Embedder 可独立选 provider（如 LLM 用 OpenAI、Embedding 用智谱）。
4. **可观测**：每个 `*_API_KEY` 字段独立，log/config 显示哪些 provider 已配。

## 实施范围

### Provider 清单（v1 必支持，锁定）

| Provider | base_url | LLM model（默认） | Embedding model（默认） | API key env |
|---|---|---|---|---|
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o-mini` | `text-embedding-3-small` | `OPENAI_API_KEY` |
| **智谱 GLM** | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4-flash` | `embedding-2` | `ZHIPU_API_KEY` |
| **MiniMax** | `https://api.MiniMax.chat/v1/` | `abab-7-chat` | `embo-01` | `MIMAX_API_KEY` |
| **小米 Mimo** | `https://api.mimo.xiaomi.com/v1/` | `mimo-7b` | `mimo-embedding` | `MIMO_API_KEY` |

> ⚠️ 上表 endpoint / model 是 2026-06 公开信息；如某家 endpoint 实际是 path-prefix 形式（如 `/v1/chat/completions` vs SDK 自动加），由 `OpenAICompatibleClient` 内部的 `base_url` 处理；v1 假设 4 家都兼容 `openai.OpenAI(base_url=..., api_key=...)` 形式。

### 默认 provider

- **LLM 默认**：OpenAI（最稳）
- **Embedding 默认**：OpenAI（最稳）
- **无 `OPENAI_API_KEY` 时**：fast-fail with `AppError(code="GENERATE_LLM_FAIL", http_status=401)` + 明确文案"请在 `.env` 设置 `OPENAI_API_KEY` 或换 `config.yaml::generate.llm.provider`"
- **不再回退 Ollama**（owner 拍板）

### `.env.example` 字段（已 Reviewer `dd21b10` 落地）

```bash
# 4 家 provider API key, 分别命名; 填你用的那几家
OPENAI_API_KEY=
ZHIPU_API_KEY=
MIMAX_API_KEY=
MIMO_API_KEY=
```

### `config.yaml` 字段扩展（待 MAQ-37 真接 config.py 时落地）

```yaml
generate:
  llm:
    provider: openai              # openai | zhipu | minimax | mimo
    model: gpt-4o-mini
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY   # 从 .env 哪个字段读 key
    timeout_s: 30
    max_retries: 2
  embedding:
    provider: openai              # 可与 llm.provider 不同 (owner 拍板)
    model: text-embedding-3-small
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    timeout_s: 30
    batch_size: 64
```

### 抽象接口（已 [ADR-0001](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) 落地）

```python
# src/rag_demo/llm/base.py (本 ADR 不重复)
class BaseLlmClient:
    def stream(self, question: str, hits: list[Hit]) -> Iterator[str]: ...

class BaseEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def embed_one(self, text: str) -> list[float]: ...
```

### 错误映射（已 `src/rag_demo/llm/openai_compat.py` 落地）

- 401 / 403 → `AppError(GENERATE_LLM_FAIL, http_status=401, stage="generate")`
- 429 / 5xx → 默认按 `max_retries=2` 重试（线性退避 `_BACKOFF_BASE_S = 0.5s`）；耗尽后抛 `AppError`
- 其他 `APIStatusError` → `AppError(GENERATE_LLM_FAIL, http_status=502)`
- `APIConnectionError` → `AppError(GENERATE_LLM_FAIL, http_status=503)`
- Embedder 错误 → `AppError(EMBEDDING_FAIL, stage="ingest")`

## 验证标准

1. ADR 文件存在（本文件）— 状态 **Accepted**
2. `.env.example` 含 4 个 `*_API_KEY` 字段（已 Reviewer 落地 in `dd21b10`）
3. `src/rag_demo/llm/{base,openai_compat}.py` 落地（已 Reviewer 落地 in `dd21b10`，115 tests pass）
4. `config.yaml` 的 `generate.llm` / `generate.embedding` 字段落 `config.py::_flatten`（待 MAQ-37 后真接 config.py 时补）
5. 4 家 base_url 与 model 列入 `docs/adr/0003-llm-embedding-source.md` 本文件（已落）

## 依赖与下一步

- **依赖**：[ADR-0001](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) 的 `OpenAICompatibleClient` / `OpenAICompatibleEmbedder` 已实现（Reviewer 落地 in `dd21b10`）
- **本 ADR 是 Phase B 真接入的前置**：MAQ-31 (LLM 真接) / MAQ-32 (Embedding 真接) 都依赖本 ADR 的 provider 清单
- **下一步**：MAQ-37 真接 config.py（让 `generate.llm.provider` 等字段真正从 config 流入 client 构造）+ MAQ-41 真实 UI

## 异议

> （暂无。Reviewer 复审时若有反对意见，按时间倒序记在这里。）

## 拼写约定（MIMAX vs MiniMax）

> 由 [MAQ-44 review 反馈](mention://issue/f47fbe2d-02f8-48f0-a05d-c28dc8d6062a) 补记（2026-06-25）

本仓为了避免 Python 标识符与官方品牌名冲突、以及让 `valid_provider` 校验不踩编码坑，**统一把 MiniMax（稀宇科技）拼作 `MIMAX`**：

- API key 环境变量：`MIMAX_API_KEY`（而非 `MINIMAX_API_KEY`）
- 配置 `provider` 字段：`minimax`（小写、无连字符）
- `VALID_LLM_PROVIDERS` 集合成员：`"minimax"`
- 代码标识符（包名、模块名、变量名）：`minimax` / `MIMAX`

对外展示（README、release notes、user-facing 错误消息）保留 `MiniMax` 写法以与公司名一致。混用是有意为之，**不是 bug**。

> 历史 review 中有人提议改回 `MiniMax` / `minimax` / `MINIMAX_API_KEY`，owner 在 MAQ-25 评论 `d560c6ca-…` 拍板"按现有命名走，文档里写明约定即可"，故沿用至今。

## 跨文档引用

- 父 issue：[MAQ-28](mention://issue/89764482-428b-4fa5-9c8a-385859e9423f)
- 根 issue：[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
- 拍板评论：[MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d)
- 上游：[PRD v0.3 §6.1.6](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) + [design v1.1 §6.1](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab)
- 关联 ADR：[0001 LLM](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) / [0002 向量库](mention://issue/fa03584b-ece9-4729-a437-2ee694fa170e)
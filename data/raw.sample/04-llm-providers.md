# LLM Provider 配置

## 概览

本项目支持 4 家 OpenAI 兼容的远程 LLM / Embedding provider，
通过 `config.yaml` 的 `generate.llm.provider` 和 `generate.embedding.provider`
字段切换；LLM 与 Embedding 可以独立选不同的 provider。

## 4 家 provider 清单

### OpenAI

- base_url: `https://api.openai.com/v1`
- LLM 模型：`gpt-4o-mini`（推荐入门）
- Embedding 模型：`text-embedding-3-small`（1536 维）
- API key 环境变量：`OPENAI_API_KEY`

### 智谱 GLM

- base_url: `https://open.bigmodel.cn/api/paas/v4/`
- LLM 模型：`glm-4-flash`
- Embedding 模型：`embedding-2`
- API key 环境变量：`ZHIPU_API_KEY`

### MiniMax

- base_url: `https://api.MiniMax.chat/v1/`
- LLM 模型：`abab-7-chat`
- Embedding 模型：`embo-01`
- API key 环境变量：`MIMAX_API_KEY`

### 小米 Mimo

- base_url: `https://api.mimo.xiaomi.com/v1/`
- LLM 模型：`mimo-7b`
- Embedding 模型：`mimo-embedding`
- API key 环境变量：`MIMO_API_KEY`

## 切换示例

### 用 OpenAI 作 LLM、智谱作 Embedding

```yaml
generate:
  llm:
    provider: openai
    model: gpt-4o-mini
  embedding:
    provider: zhipu
    model: embedding-2
```

`.env` 需同时设置 `OPENAI_API_KEY` 与 `ZHIPU_API_KEY`。

## 没有 API key 怎么办

跑 `rag-demo ingest` 不需要 API key（用 dummy 全 0 向量，仅 smoke）。
但跑 `rag-demo ask` 必须要 LLM 的 `*_API_KEY`，
否则 `AppError(401, GENERATE_LLM_FAIL)`。
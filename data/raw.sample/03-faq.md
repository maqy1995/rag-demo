# 常见问题

## Q: 我的 vault 里什么都没放，跑得起来吗？

A: 跑得起来。`uv run rag-demo up` 会检测到 vault 目录为空，
自动 fallback 到 `data/raw.sample/`（cold-start demo 路径）。
你会看到 demo 三篇样例笔记，问问题也能给出合理的回答。

## Q: 默认 LLM 是哪一家？

A: 默认是 ollama 本地推理（`qwen2.5`），走 `http://localhost:11434`。
如果你想用 OpenAI 或 Anthropic，改 `config.yaml` 的 `generate.llm` 段。
`OPENAI_API_KEY` 走 `.env` 注入，不进 config 文件。

## Q: 数据会上云吗？

A: 不会。所有数据（vault 原文、index、usage log）都落在你本地 `data/` 目录。
LLM 调用走你配置的 provider（默认是本地 ollama，没有外部网络）。

## Q: 这个项目生产可用吗？

A: 这是 demo，不是产品。生产化前需要补的东西：
真实向量库（Chroma / FAISS）、真实 chunker（Recursive splitter）、
真实 embedding、retrieval 评估、监控告警。详见 `docs/dev/design.md`。

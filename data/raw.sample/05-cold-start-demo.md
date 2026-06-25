# 冷启动 Demo

## 是什么

第一次跑 `uv run rag-demo up` 时，vault 可能还没索引完成。
前端需要立刻能 demo，所以设计了一个 cold-start demo 路径：

1. 后台异步建索引
2. 前台预置 5 条示例问题，先用 `data/index.sample/`（预 embed 索引）跑端到端
3. 用户 vault 索引完成后，通过 SSE/轮询通知前端解锁"问你的笔记"

## 30 秒反馈机制

PRD §3.1 F8 + §8.2 要求：

- 自前端 `index.html` 首字节起
- 终点 = "前端看到 5 条示例按钮可点击"
- 阈值：mock 后端 5s / 真实后端 30s

超时记入 `data/usage/local-{date}.jsonl` 的 `cold_start_abandoned` 事件。

## 5 条示例问题

S1 软阻塞未解锁前用现有 raw.sample 3 篇内容硬编码 5 条起步：

1. "微服务治理是怎么定义的？"
2. "服务发现是什么？"
3. "冷启动 demo 是怎么做的？"
4. "怎么切换 LLM provider？"
5. "怎么评估检索质量？"

S1 解锁后由产品给 5 条更贴合演示场景的问题替换。
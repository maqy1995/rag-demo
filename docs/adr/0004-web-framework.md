# 0004. Web 框架 — FastAPI + pydantic v2（确认现状）

> multica-issue: [MAQ-29](mention://issue/2fe6d7c4-b1e6-45b8-8531-0366b1c8e99f)
> 状态：**Accepted**（owner 2026-06-25 在 [MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d) 拍板）
> 日期：2026-06-25
> 提议人：资深全栈开发工程师（`01386b69…`）

## 背景

[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 推进中需要确认 web 框架选型。**实现 v1（MAQ-17）已落地 FastAPI**——`src/rag_demo/web/main.py` 9 端点 + pydantic v2 + SSE 协议。本 ADR 是"确认现状"性质，把"已选 FastAPI"正式落字。

## 候选方案

### 方案 A — Flask

- 优点：成熟、文档全。
- 缺点：与 pydantic v2 整合弱（需手写 request body 解析）；SSE 要 werkzeug 手动 yield；与现有 9 端点 + Pydantic BaseModel 体系**完全冲突**——撤回成本极高。
- **评估**：不采纳（撤回成本）。

### 方案 B — Django

- 优点：full-stack、自带 admin/orm/migration。
- 缺点：包体大；强 ORM 耦合；与 MVP"组件尽量少"原则冲突；MVP 无 admin/orm 需求。
- **评估**：不采纳（over-engineering）。

### 方案 C — **FastAPI + pydantic v2 + uvicorn**（采纳）

- 优点：
  - 实现 v1 已落地（`src/rag_demo/web/main.py` 9 端点），撤回成本 ≈ ∞；
  - Pydantic v2 BaseModel 自动校验 + OpenAPI 文档；
  - `StreamingResponse(media_type="text/event-stream")` 直接对应 design §3.6 SSE 协议；
  - FastAPI 异步支持与未来 async 改造预留；
  - 测试用 `fastapi.testclient.TestClient` 与生产 uvicorn 行为一致。
- 缺点：
  - Starlette/FastAPI 偶尔有 deprecation warning（如 httpx vs httpx2）——本项目用 `httpx>=0.27` 即可；
  - FastAPI 0.110+ 的 `Annotated[..., Depends(...)]` 新风格暂未采用，保持现有 `Depends(get_config)` 函数式注入。

## 决议

**采纳方案 C**。理由汇总：

1. **现状已落地**：9 端点 + SSE + pydantic v2 已在 `src/rag_demo/web/main.py`（MAQ-17 落地），全部测试通过（`test_web.py`）；
2. **设计约束对齐**：design §3.6 SSE 协议 / §6.3 L3→L2 边界错误壳 都基于 FastAPI；
3. **生态**：与本项目其他依赖（`pydantic>=2.7`、`uvicorn[standard]>=0.27`）一致。

## 实施范围

### 已落地（[MAQ-17](mention://issue/...) 实现 v1）

| 文件 | 状态 |
|------|------|
| `src/rag_demo/web/main.py`（281 行） | 9 端点 + SSE + Pydantic |
| `src/rag_demo/web/static/index.html`（239 字节占位） | 等待 [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI |
| `tests/test_web.py` | 9 端点覆盖 + NB1 SSE `cost_ms.generate` 真计时（MAQ-23 落地） |

### 不引入

- ❌ Flask
- ❌ Django
- ❌ Starlette（FastAPI 内部已含）
- ❌ SSE-Starlette（用 FastAPI 内置 `StreamingResponse` 足够）

### 9 端点清单（与 design §3.6 严格对齐）

| Method | Path | 用途 | 状态 |
|--------|------|------|------|
| POST | `/api/chat` | 非流式问答 | ✅ 实现 |
| POST | `/api/chat/stream` | SSE 流式问答 | ✅ 实现 + NB1 修复 |
| POST | `/api/search` | 纯检索（不调 LLM） | ✅ 实现 |
| POST | `/api/ingest` | 触发全量/增量重建 | ✅ 实现 |
| GET | `/api/config` | 当前生效配置（脱敏） | ✅ 实现 |
| GET | `/api/index/status` | 索引状态（idle/building/error） | ✅ 实现 |
| GET | `/api/health` | 健康检查 | ✅ 实现 |
| POST | `/api/usage` | 埋点写 jsonl | ✅ 实现 |
| GET | `/api/usage/query` | 自检事件数 | ✅ 实现（NI6） |

## 验证标准

1. ADR 文件存在（本文件）— 状态 **Accepted**
2. `pyproject.toml` extras 已声明 `web = ["fastapi>=0.110", "uvicorn[standard]>=0.27", "pydantic>=2.7"]`
3. `tests/test_web.py` 9 端点覆盖 + 80 测试 + Reviewer 24 + chunk 11 + vector 10 + retrieve 7 = **142 passed**

## 依赖与下一步

- **依赖**：无（实现已落地）
- **下一步**：MAQ-41 (真实 UI) / MAQ-42 (e2e test) / MAQ-44 (README 重写)

## 异议

> （暂无。Reviewer 复审时若有反对意见，按时间倒序记在这里。）

## 跨文档引用

- 父 issue：[MAQ-29](mention://issue/2fe6d7c4-b1e6-45b8-8531-0366b1c8e99f)
- 根 issue：[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
- 拍板评论：[MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d)
- 上游：[design v1.1 §3.6 §6.3](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab)
- 关联 ADR：[0001 LLM](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890) / [0002 向量库](mention://issue/fa03584b-ece9-4729-a437-2ee694fa170e) / [0003 provider](mention://issue/89764482-428b-4fa5-9c8a-385859e9423f) / [0005 前端](mention://issue/e28ed177-3edc-4865-91ad-562ca286e437)
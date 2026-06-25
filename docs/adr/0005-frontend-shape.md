# 0005. 前端形态 — 单 HTML + Vue 3 CDN + marked.js（确认现状 + MAQ-41 落地路径）

> multica-issue: [MAQ-30](mention://issue/e28ed177-3edc-4865-91ad-562ca286e437)
> 状态：**Accepted**（owner 2026-06-25 在 [MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d) 拍板）
> 日期：2026-06-25
> 提议人：资深全栈开发工程师（`01386b69…`）

## 背景

[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 推进中需要确认前端形态选型。当前 `src/rag_demo/web/static/index.html` 是 239 字节占位（"Static index placeholder — see MAQ-18 for full cold-start UI"）。本 ADR 把"单 HTML + Vue 3 CDN + marked.js"选型正式落字，并为 [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI 留路径。

## 候选方案

### 方案 A — React + Vite

- 优点：生态最全；组件化清晰。
- 缺点：违反 design §6.2.2"前端零构建"硬约束（Vite 是构建工具）；用户从 git clone 到 `uv run rag-demo up` 一条命令跑通的中断；CI/CD 复杂度上升。
- **评估**：不采纳（违反硬约束）。

### 方案 B — Vue CLI / Webpack 工程化

- 优点：单文件组件清晰。
- 缺点：同上违反"零构建"；用户首次启动需 `npm install` + 编译。
- **评估**：不采纳（违反硬约束）。

### 方案 C — **单 HTML + Vue 3 CDN + marked.js 单文件**（采纳）

- 优点：
  - 零构建：单文件 `index.html` + `<script src="https://unpkg.com/vue@3">` + `<script src="https://unpkg.com/marked">`；
  - 与 FastAPI 静态文件 `StaticFiles(directory=..., html=True)` 原生整合；
  - marked.js 单文件渲染 Markdown 原文降低 XSS 风险（design §3.1 F6）；
  - 用户 git clone → `uv run rag-demo up` 浏览器开 `http://127.0.0.1:8000/` 直接看到 UI；
  - 设计 [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI 用此骨架。
- 缺点：
  - 无构建意味着无 tree-shaking（Vue 3 full ≈ 80KB gzip；marked.js ≈ 30KB gzip）；
  - CDN 依赖（unpkg）若 404 则页面不工作——但 [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 落地时考虑本地 vendoring。

## 决议

**采纳方案 C**。理由汇总：

1. **零构建硬约束**：design §6.2.2 明确禁止 Vite/Webpack；
2. **快速起步**：MVP 阶段"组件尽量少"原则；用户从 git clone 到看到 UI 不超过 30 秒（与 §3.1 F8 冷启动 30s 目标对齐）；
3. **真实 UI 留路径**：[MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 用本骨架实现 Search+Ask 双面板 + 5 示例按钮。

## 实施范围

### 已落地（占位 v1）

| 文件 | 状态 |
|------|------|
| `src/rag_demo/web/static/index.html`（239 字节） | 占位 HTML，等 [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 替换 |
| `src/rag_demo/web/main.py:281-289` | `StaticFiles(directory=str(_STATIC_DIR), html=True)` mount 在 `/` |

### [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI 路径（待开工）

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/vue@3"></script>
  <script src="https://unpkg.com/marked"></script>
  <link rel="stylesheet" href="/static/style.css">  <!-- 可选, MVP 不必有 -->
</head>
<body>
  <div id="app">
    <!-- 顶栏: 当前 config (调 /api/config) -->
    <header>{{ config.vault.name }}</header>

    <!-- 左栏: Search -->
    <aside>
      <input v-model="query" @keyup.enter="search">
      <button @click="search">Search</button>
      <ul>
        <li v-for="hit in hits" @click="askSelected(hit)">
          {{ hit.heading }} <span class="score">{{ hit.score.toFixed(2) }}</span>
          <p v-html="marked(hit.snippet)"></p>
        </li>
      </ul>
    </aside>

    <!-- 右栏: Ask (SSE 流式) -->
    <main>
      <textarea v-model="question"></textarea>
      <button @click="ask">Ask</button>
      <article v-html="marked(answer)"></article>
      <details>
        <summary>Sources</summary>
        <ul>
          <li v-for="src in sources">{{ src.file }}#{{ src.heading }}</li>
        </ul>
      </details>
    </main>

    <!-- 5 示例按钮 (依赖 S1 解锁, 未解锁前先用硬编码 3 条起步) -->
    <nav>
      <button v-for="q in exampleQuestions" @click="ask(q)">{{ q }}</button>
    </nav>

    <!-- 索引状态条 -->
    <footer>{{ status.state }} ({{ status.current_progress?.done }}/{{ status.current_progress?.total }})</footer>
  </div>

  <script>
    const { createApp, ref } = Vue;
    createApp({
      setup() {
        const config = ref({});
        const query = ref('');
        const hits = ref([]);
        const question = ref('');
        const answer = ref('');
        const sources = ref([]);
        const status = ref({ state: 'idle' });

        const exampleQuestions = [
          '微服务治理是怎么定义的？',
          '服务发现是什么？',
          '冷启动 demo 是怎么做的？',
          '5 条示例问题怎么选？',
          'Recall 怎么评估？',
        ];

        // ... fetch /api/config, /api/search, /api/chat/stream, /api/index/status

        return { config, query, hits, question, answer, sources, status, exampleQuestions };
      }
    }).mount('#app');
  </script>
</body>
</html>
```

### 不引入

- ❌ React / ReactDOM
- ❌ Vite / Webpack / Vue CLI / Parcel
- ❌ TypeScript 编译（单 HTML 不引入）
- ❌ npm/yarn lockfile（仅 CDN 引用）

## 验证标准

1. ADR 文件存在（本文件）— 状态 **Accepted**
2. `static/index.html` ≥ 200 行（[MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 落地后）
3. 5 示例按钮可点击 → 看到流式回答 + 引用块（依赖 S1 解锁）
4. marked.js 渲染引用块无 XSS 风险（禁止回传 HTML，design §3.1 F6）

## 依赖与下一步

- **依赖**：[ADR-0004](mention://issue/2fe6d7c4-b1e6-45b8-8531-0366b1c8e99f) FastAPI 静态文件 mount
- **下一步**：[MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI 落地 + [MAQ-42](mention://issue/7ed2af85-ed49-4e24-b689-18a811d58637) e2e 测试

## 异议

> （暂无。Reviewer 复审时若有反对意见，按时间倒序记在这里。）

## 跨文档引用

- 父 issue：[MAQ-30](mention://issue/e28ed177-3edc-4865-91ad-562ca286e437)
- 根 issue：[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
- 拍板评论：[MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d)
- 上游：[design v1.1 §6.2.2 §3.1 F6](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab)
- 关联 ADR：[0004 web](mention://issue/2fe6d7c4-b1e6-45b8-8531-0366b1c8e99f) / [MAQ-41](mention://issue/64f62571-2cd1-466a-b038-25d869bd3d6b) 真实 UI
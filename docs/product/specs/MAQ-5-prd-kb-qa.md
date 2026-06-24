# 知识库问答 — 产品需求文档 (PRD v0.3)

> multica-issue: MAQ-5
> 作者：AI 软件产品经理
> 日期：2026-06-24（v0.1）→ 2026-06-24（v0.2，依据开发 + Reviewer 评审意见修订）→ 2026-06-24（v0.3，依据 Reviewer 第二轮评审意见定稿）
> 状态：**Final（v0.3）— Reviewer Approved with comments**
> 关联报告：
> - v0.1 评审：[docs/review/reports/2026-06-24-MAQ-5-prd-review.md](../../review/reports/2026-06-24-MAQ-5-prd-review.md)
> - v0.2 评审：[docs/review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md](../../review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md)

---

## 0. 读者指南（v0.2 新增）

| 角色 | 重点章节 |
|------|---------|
| 产品（含本人复审） | §1 / §2 / §3 / §4 / §8 / §11 |
| 开发 | §3 / §6 / §7 / §11 + `docs/adr/NNNN-*.md`（技术选型决策） |
| 审查员 | §3 / §7 / §8 / §11 |
| 环境准备与部署 | §5 / §6 / §11 |

> 本 PRD 只描述**要做什么 / 不做什么 / 验收标准**；**具体用什么技术实现**由 `docs/adr/NNNN-*.md` 拍板（见 §6 与附录 A）。任何与本 PRD 冲突的实现细节，以最新 ADR 为准。

---

## 修订记录

### v0.3（2026-06-24）— 当前版本（定稿）
依据 [MAQ-7](mention://issue/0798b1d3-0fca-44dd-84bf-9c40e49d6e47) Reviewer 第二轮评审意见修订。变更摘要：

- **解决 NB1**（§8.2）：US6"未找到定义"判定从 prompt 指令前移到检索后处理，新增 `is_defined_in_hits(query, hits) -> bool` 纯函数 + 早返。US4/US6 合并为一条决策链（hits 为空 / 无定义 / 有定义）。
- **解决 NI1**（§5、§8.4）：隐私行 + 北极星埋点采集方式明确为"POST 到本机 `/api/usage` → `data/usage/local-{date}.jsonl`"，无任何外发。
- **解决 NI2**（§7.1）：`vault://` 协议追加编码规则段（vault-name / relative-path / anchor 三段分别编码；anchor 不做 slug 化）。
- **解决 NI3**（§3.2 F10）：F10 收敛为"默认 `localStorage`"；SQLite 留作 v0.3 候选。
- **解决 NS1**（§5）：性能行"≤ 1k 切片"拎为明文条件。
- **解决 NS2**（§3 F8、§8.2）：30s 反馈测量点明确（首字节起 → 示例按钮可点击），加入 `tests/test_cold_start.py` 自动化断言。
- **解决 NS3**（§3 F1）：F1 追加默认配置路径 `./config.yaml`，未配置时走冷启动 demo 路径。
- **解决 NS4**（§3 F3、§6.1.3、§7.2）：`ingest --full` 与 `POST /api/ingest` 关系明确（CLI ⇔ API 复用同一业务函数；Web UI 仅展示状态，不直接触发全量重建）。
- **状态**：**Final**。开发同事可基于此版本启动 ADR-0001-0005 起草；产品硬阻塞 B6/B7/B8 见 §11 仍待产品答复。

### v0.2（2026-06-24）— 已归档（v0.3 之前）
依据 [MAQ-5](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) 下资深全栈开发工程师（agent `01386b69...`）与 Reviewer（agent `e57a9ea0...`）的评审意见修订。变更摘要：

- **新增**：读者指南（§0）、竞品分析（§1.4）、Search+Ask 双面板（F4 升级）、冷启动 demo（F12）、US6 定义缺失兜底、§6 改为"约束与偏好"、附录 A 候选技术栈清单、ADR 决策清单（附录 B）。
- **修正**：§5 "全程本地" 与远程 API 表述矛盾（明确为"默认本地、可选远程，README 高亮告知"）；§3 F2 增加 chunk 默认参数；§3 F3 增量更新范围收窄为"启动时 mtime diff"，"自动检测变更"挪到 v0.2；§7 新增 `/api/chat/stream`、`/api/config`、`/api/index/status`；§5 新增错误响应格式与日志格式基线；§8 验收标准改为可量化；§11 待确认事项升级为"硬阻塞"并标 owner + 截止。
- **重构**：§6 重写为约束与偏好（删除 LangChain / Chroma / FastAPI 等具体选型，全部转交 ADR）。

### v0.1（2026-06-24）— 已归档
首版 PRD。覆盖需求背景、MVP 功能、用户故事、推荐技术栈、接口草案。已被开发 + Reviewer 评审出 10+5+3 条意见（见评论 `da4b8bd6...`、`f6bd95f6...`），由本版本 v0.2 整合。

---

## 1. 需求背景与目标

### 1.1 用户原始诉求（不变）

- 已有 **Obsidian 知识库**（本地 Markdown 文档集合），希望基于其内容进行**问答**。
- 需要一个 **Web 服务**形态的产品。
- 后端 **Python**，前端技术栈不限。
- **组件尽量少**，便于本地部署。
- 技术栈**先不求复杂，先跑通原型验证效果**。

### 1.2 产品定位（v0.2 修订）

面向个人 Obsidian 重度用户的 **轻量级本地 RAG 问答 / 检索增强系统**：把本地笔记库变成一个"可对话、可回顾的外脑"。**MVP 阶段不应只做"问答"**，必须同时覆盖"找笔记"这一更基础、更高频的痛点（见 §3 F4 升级）。

### 1.3 产品目标（MVP 阶段）

- 能在本地**一条命令**启动，成功读取 Obsidian Vault 内容并完成索引。
- 用户输入问题，系统返回**带出处（引用文档 + 片段 + 可点击锚点）**的回答。
- 用户**能直接搜索** Top-K 召回片段并基于若干条发起"基于这些给我讲一下"二次提问。
- 回答质量、可解释性、稳定性达到"可用"水平，足以判断后续是否值得继续投入。

### 1.4 竞品 / 替代品分析（v0.2 新增，回应 Reviewer I1）

| 方案 | 形态 | 优势 | 本 PRD 的差异化点 |
|------|------|------|--------------------|
| **Obsidian Smart Connections** | Obsidian 插件 | 装即用、与编辑器深度集成 | 本 PRD 目标：① **Web 端独立可用**（不绑死 Obsidian 客户端）；② **更可控的引用协议**（vault://, 便于未来 Obsidian 插件 / MCP 共用）；③ **本地可观测、可评估**（Recall 自动化脚本、North Star 指标） |
| **Obsidian Copilot** | Obsidian 插件 | UI 成熟、模型选项多 | 同上；额外强调 **冷启动体验** 与 **"未定义时诚实拒绝"** 的兜底（见 US4 / US6） |
| **Cherry Studio / AnythingLLM** | 桌面应用 | 全功能、本地优先 | 本 PRD 目标：① **单一 Vault 场景**（不是通用 RAG）；② **零构建前端**（单 HTML）；③ **与现有仓库三段式骨架无缝集成**（CLI 与 Web 共用业务逻辑） |
| **自己写脚本调 LLM API** | 无 | 自由 | 不解决：检索质量、引用回溯、冷启动兜底、可评估性 |

> **结论**：MVP 不必在功能广度上超越插件，但**在"引用协议 / 可评估性 / 与三段式骨架集成"**三点上必须做出明确差异。

---

## 2. 目标用户与典型场景

### 2.1 用户画像（不变）
- **个人知识工作者 / 研究者 / 学生**：长期在 Obsidian 中累积笔记，希望以问答或检索形式快速复用。
- **技术熟悉度**：中高，能接受本地启动一个服务、修改配置文件、查看日志。
- **部署形态**：单机、本地、无并发压力。

### 2.2 典型使用场景

1. **回顾型**：上周读过的一篇笔记讲了什么？想用关键词找回来（**MVP 必支持，纯检索路径**）。
2. **整合型**：我在多个笔记里记录过"微服务治理"的要点，能不能汇总一下？
3. **解释型**：笔记中提到 X 概念，这个概念在我笔记里是怎么被定义和使用的？（**MVP 必须有兜底，见 US6**）
4. **查找型**：找包含某段引用的笔记出处。

### 2.3 反场景（MVP 不做，不变）

- 多用户、权限、计费、企业级管理后台。
- 跨设备同步、移动端。
- 笔记的写入、编辑、协作（Obsidian 自身负责）。
- 多模态（图片 OCR、语音）。

---

## 3. MVP 功能范围（v0.2 重大调整）

### 3.1 必须包含（Must Have）

| 编号 | 功能 | v0.2 说明 |
| --- | --- | --- |
| F1 | **Vault 路径配置** | 用户在配置文件中指定 Obsidian Vault 根目录，支持 `.md` 文件（含子目录）。**默认配置路径：`./config.yaml`（仓库根，相对路径）**；如不存在，README 提示用 `config.example.yaml` 起步。第一次启动时若 `vault.path` 未配置，**走 §3 F8 冷启动 demo 路径**而非报错（响应 Reviewer NS3）。 |
| F2 | **文档解析与切片** | 读取 Markdown，按**标题 + 长度混合策略**切分。**默认参数：`chunk_size=500`，`chunk_overlap=80`**（响应开发 §2.3）。参数位置：`config.yaml` 字段 `ingest.chunk_size` / `ingest.chunk_overlap`，运行时可调。 |
| F3 | **向量化与索引** | 使用 Embedding 模型将 chunk 转为向量，写入本地向量库（持久化目录沿用 `data/index/`，子目录 `data/index/chroma/` 或同类，**最终路径由 ADR-0002 拍板**）。**MVP 增量更新限定为"启动时按 mtime/sha diff，仅重建新增 / 修改文件"**；**自动 file-watcher 实时同步延后到 v0.2**（响应开发 §2.4）。**CLI `rag-demo ingest --full` ⇔ `POST /api/ingest`**：两者复用同一业务函数 `ingest_directory(data_dir, index_dir, *, full=True)`；Web UI 仅展示状态、不直接触发全量重建（响应 Reviewer NS4）。 |
| **F4** | **Search + Ask 双面板**（v0.2 升级） | **左栏**：Top-K 召回片段的纯语义检索列表（可不依赖 LLM，可点击跳转 / 复制 / 选中）。**右栏**：基于左栏选中条目或自由 query 的"问答"流，答案必须附引用。**这是 MVP 的核心交互**，不是 v0.2 才有（响应 Reviewer B1）。 |
| F5 | **问答（Generation）** | 生成前**先做定义存在性检测**：`is_defined_in_hits(query, hits) -> bool` 纯函数（详见 §8.2）。若 `False` → 早返"你的笔记里没找到 X 的明确定义" + hits，**不发 LLM**。若 `True` → 将 Top-K 片段与 query 一并交给 LLM 生成答案；回答必须**附引用来源**（采用 `vault://` 协议，见 §7）。 |
| F6 | **Web 聊天界面** | 单页 Web UI：Search + Ask 双面板（见 F4）；引用点击后渲染**Markdown 原文**（前端用 `marked.js` 单文件渲染，禁止回传 HTML 以降低 XSS 风险）（响应开发 §2.5）。 |
| F7 | **本地启动脚本** | 一条命令完成依赖安装 + 索引构建 + 启动服务。**底层走 `uv sync` + `uv run rag-demo ...`**（响应开发 §1）；README 给出。 |
| F8 | **冷启动 demo**（v0.2 新增，响应 Reviewer I3；v0.3 明确测量点） | **首次启动、Vault 还没索引完**时：① 后台异步建索引；② 前台预置 **5 条示例问题**，先用内置示例完成一次端到端问答 demo；③ 索引完成后通过 SSE 或轮询通知前端解锁"问你的笔记"入口。**30 秒反馈测量点**：自"前端 `index.html` 首字节"起 → 终点 = "前端看到 5 条示例按钮可点击"或"前端看到 `state=building` + 进度"。超 30s 视为放弃（见 §8.2 `tests/test_cold_start.py`）。 |

### 3.2 可选包含（Nice to Have）

| 编号 | 功能 | 说明 |
| --- | --- | --- |
| F9 | **引用高亮预览** | 在回答中将引用片段的 Markdown 原文渲染出来（部分场景 F6 已覆盖）。 |
| F10 | **会话历史持久化** | MVP 不做，v0.2 阶段考虑。**默认方案：浏览器 `localStorage`**（单机、零运维、和隐私基线一致）；"如需跨设备同步再升 SQLite"列为 v0.3 候选（响应 Reviewer NI3）。 |
| F11 | **过滤与时间范围** | 按文件夹、最近修改时间过滤检索范围。 |

### 3.3 显式不做（Out of Scope，不变）

- 多租户、鉴权、登录。
- 实时协同编辑。
- 笔记写入、知识图谱构建、自动化标签。
- 跨语言模型微调。
- **file-watcher 实时同步**（延后到 v0.2，见 F3）。
- **图片 / PDF / 代码块特殊处理**（MVP 仅处理纯文本，代码块按普通段落切分）。

---

## 4. 用户故事（v0.2 新增 US6）

- **US1**：作为用户，我希望在网页输入框中输入问题并提交，看到基于我个人笔记的回答以及引用位置。
- **US2**：作为用户，我希望点击引用时能看到原文片段，方便验证回答是否正确。
- **US3**：作为用户，我希望新增 / 修改笔记后**启动服务时**能自动重建索引（增量 diff，无需手动触发）。
- **US4**：作为用户，我希望系统能够处理"No relevant context"的情况并**诚实说明**，而不是胡编（必须自动化断言，见 §8.2）。
- **US5**：作为用户，我希望调整配置即可切换不同的 LLM / Embedding 服务（如本地 Ollama 或远程 API）。
- **US6**（v0.2 新增，响应 Reviewer B3）：作为用户，当我在笔记里查询"X 是怎么定义的"且**笔记中无明确定义**时，系统必须返回"**你的笔记里没找到 X 的明确定义，仅有的相关片段是：...**"并禁止 LLM 自由发挥（必须自动化断言，见 §8.2）。

---

## 5. 非功能性需求（v0.2 修订）

| 维度 | 要求 | 备注 |
|------|------|------|
| 部署 | 单机本地，**一条命令启动**。底层走 `uv sync --extra <stack> && uv run rag-demo up`。**不强求 Docker**。 | 响应开发 §1 |
| **数据安全 / 隐私**（v0.2 修订；v0.3 补埋点本地化） | **默认全程本地**（LLM + Embedding 都跑 Ollama）。如用户选择远程 API（OpenAI 兼容 / DeepSeek / 智谱 等），**README 必须在显眼位置列出"哪些文本会离开本机"**（响应开发 §2.1）。**所有使用行为埋点（见 §8.4）仅落本机 `data/usage/local-{date}.jsonl`，无任何外发**（响应 Reviewer NI1）。 | 消除 v0.1 "全程在本地" 与 §6 远程 API 的矛盾 |
| 性能（v0.2 修订，响应 Reviewer I5；v0.3 拎出 1k 条件） | - **首字延迟 ≤ 2s**（基于 `/api/chat/stream` SSE 流式）<br>- **总延迟 ≤ 10s**（非流式兜底）<br>- **以上指标在 Vault 总量 ≤ 1k 切片时成立**（响应开发 §5）；超出后按 §3.1 F3 增量更新策略解决，全量重建按 §8.3 3b 预期时间 | 性能是本地 RAG 对比 ChatGPT 的差异化卖点 |
| 资源占用 | 不强制 GPU；Embedding 可走 API 或本地小模型。 |
| **错误响应格式**（v0.2 新增，响应开发 §2.9） | 4xx / 5xx 一律返回 `{"error": {"code": "<machine-readable>", "message": "<human-readable>", "stage": "<ingest\|retrieve\|generate\|infra>"}}`。前端按 `code` 路由提示文案。 |
| **日志格式**（v0.2 新增，响应开发 §2.10） | 统一 `logging` + **一行 JSON**：`{"ts": "...", "level": "...", "stage": "...", "cost_ms": ..., "msg": "..."}`。启动日志、检索命中数、问答耗时都按此格式，便于后续接 observability。 |
| 可观测性 | 启动日志、检索命中数、问答耗时按上述 JSON 格式打印到控制台。 |
| 可移植性 | macOS / Linux 优先，Windows 不强求。 |

---

## 6. 约束与偏好（v0.2 重写，原 §6 推荐技术栈已移除 → 转 ADR）

> **本节只描述约束与偏好，不指定具体技术。** 具体选型见 `docs/adr/NNNN-*.md`（清单见附录 B）。

### 6.1 硬约束

1. **后端语言**：Python（与现有 `pyproject.toml` 一致）。
2. **依赖管理**：统一使用 **uv**（`pyproject.toml` + `uv.lock`），**禁止引入第二条依赖管理路径**（`requirements.txt` / `pip-tools` / `poetry`）。对应 ADR-0001/0002/0003 的 extras 通过 `uv sync --extra <name>` 安装。
3. **代码组织**：必须沿用现有三段式骨架（`src/rag_demo/{ingest,retrieve,generate}.py`），CLI（`rag-demo ingest/ask/doctor`）与 Web 入口**共用同一份业务逻辑**。FastAPI（候选，见 ADR-0004）只做路由层，业务函数签名（`ingest_directory` / `retrieve` / `answer` / 新增 `is_defined_in_hits`）保持稳定。**CLI 与 HTTP API 等价**：`rag-demo ingest --full` ⇔ `POST /api/ingest`，两者复用同一份业务函数（响应 Reviewer NS4）。
4. **持久化目录**：沿用 `data/index/`（与现有 stub 一致）；向量库文件放其子目录（如 `data/index/chroma/`），具体子目录名由 ADR-0002 拍板。
5. **组件数量**：MVP 期间不引入新服务（无 Redis / Postgres / Celery / Kafka 等），如确需引入必须先走 ADR。
6. **本地优先**：默认配置走本地 Embedding + 本地 LLM（Ollama），远程 API 作为可选 extras 在配置文件中标注。

### 6.2 偏好（非强制，按重要性递减）

1. **优先复用现有 extras**：`langchain` / `llamaindex`、`faiss` / `chroma`、`openai` / `anthropic`（已声明在 `pyproject.toml`，避免新增 extras 字段）。
2. **前端零构建**：单 HTML + 原生 JS（或 Vue 3 CDN）；不引入 Vite/Webpack。Markdown 渲染用 `marked.js` 单文件。
3. **API key 注入**：通过 `.env`（`.env.example` 已存在）注入；**严禁将真实 key 写入 `config.yaml`**；如需提供 `config.example.yaml`，必须配套说明 .env 注入方式（响应开发 §2.7）。
4. **可测试性**：核心业务函数纯函数化 / 依赖注入，便于 `pytest` 直接调用。

### 6.3 目录结构（v0.2 与现有骨架对齐）

```
rag-demo/
├── src/rag_demo/
│   ├── ingest.py          # 文档加载 + 切片 + 索引（已存在 stub）
│   ├── retrieve.py        # 检索逻辑（已存在 stub）
│   ├── generate.py        # LLM 调用 + 答案拼接（已存在 stub）
│   ├── web/
│   │   └── main.py        # FastAPI 路由层（待新增，薄壳）
│   └── cli.py             # rag-demo ingest/ask/doctor 入口（已存在）
├── data/
│   ├── raw/               # Vault 内容（gitignore）
│   └── index/             # 向量库持久化（gitignore）
├── static/
│   └── index.html         # 单文件前端（双面板）
├── config.example.yaml    # 公开示例（不含 key）
├── .env.example           # API key 占位（已存在）
├── tests/                 # 含 recall 评估脚本
├── scripts/eval_recall.py # Recall 自动化评估（响应 Reviewer 量化要求）
└── docs/
    ├── product/specs/MAQ-5-prd-kb-qa.md   # 本文档
    └── adr/NNNN-*.md      # 选型决策（见附录 B）
```

---

## 7. 接口草案（v0.2 扩充）

### 7.1 协议约定

- 引用 `source` 字段采用 **`vault://` 协议**（响应 Reviewer I2；v0.3 补编码规则）：
  ```
  vault://<vault-name>/<relative-path>#<anchor>
  例：vault://my-notes/AI/微服务治理.md#服务治理
  ```
  理由：未来 Obsidian 插件（v0.4）、Web 端、MCP server 共用同一套引用协议，避免后期改造成本。
  **编码规则**（响应 Reviewer NI2）：
  - `<vault-name>`：RFC 3986 unreserved 字符 + 百分号编码（中文按 UTF-8 percent-encoding）。
  - `<relative-path>`：按 URL path 段编码（空格 → `%20`，`/` 保留作分隔符；中文按 UTF-8 percent-encoding）。
  - `<anchor>`：**不做 slug 化**，直接是 heading 原文的百分号编码；前端按原样匹配 heading 节点，最简单也最可读。
  - 实现建议参照 Python `urllib.parse.quote(..., safe='/')`；前端用 `decodeURIComponent` 反解。

### 7.2 端点清单

| Method | Path | 用途 | 备注 |
|--------|------|------|------|
| POST | `/api/chat` | 非流式问答 | MVP 兜底 |
| POST | `/api/chat/stream` | **SSE 流式问答**（v0.2 新增，响应开发 §2.2 + Reviewer I5） | 推荐默认路径，首字延迟 ≤ 2s |
| POST | `/api/search` | **纯检索（不调 LLM）**（v0.2 新增，F4 左栏） | 返回 Top-K 命中片段 |
| POST | `/api/ingest` | 触发全量重建索引 | 异步或同步均可 |
| GET | `/api/config` | **当前生效配置**（不含 secret）（v0.2 新增，响应开发 §2.6） | 前端状态栏用 |
| GET | `/api/index/status` | **索引状态**（chunk 数、上次重建时间、构建中进度）（v0.2 新增，响应开发 §2.6） | F8 冷启动 demo 轮询 |
| GET | `/api/health` | 健康检查 | — |

### 7.3 关键请求 / 响应样例

#### POST `/api/search`

**Request**
```json
{ "query": "微服务治理", "top_k": 5, "filters": { "folder": "AI/", "since": null } }
```

**Response**
```json
{
  "hits": [
    {
      "source": "vault://my-notes/AI/微服务治理.md#服务治理",
      "file": "AI/微服务治理.md",
      "heading": "服务治理",
      "chunk_id": 12,
      "snippet": "微服务治理的核心是……",
      "score": 0.83
    }
  ]
}
```

#### POST `/api/chat/stream`（SSE）

**Request**
```json
{
  "question": "我在笔记里如何定义微服务治理？",
  "top_k": 5,
  "selected_sources": ["vault://my-notes/AI/微服务治理.md#服务治理"]
}
```

**Response**（text/event-stream）
```
event: token
data: {"delta":"根据"}

event: token
data: {"delta":"你的笔记"}

...

event: sources
data: {"sources":[{"source":"vault://...","file":"...","heading":"...","chunk_id":12,"snippet":"..."}]}

event: meta
data: {"retrieved":5,"cost_ms":{"retrieve":120,"generate":1830}}
```

#### POST `/api/chat`（非流式兜底）

**Request**
```json
{ "question": "我在笔记里如何定义微服务治理？", "top_k": 5 }
```

**Response**
```json
{
  "answer": "根据你的笔记，微服务治理主要包括……",
  "sources": [
    {
      "source": "vault://my-notes/AI/微服务治理.md#服务治理",
      "file": "AI/微服务治理.md",
      "heading": "服务治理",
      "chunk_id": 12,
      "snippet": "微服务治理的核心是……"
    }
  ]
}
```

#### GET `/api/index/status`

**Response**
```json
{
  "state": "building",          // idle | building | error
  "chunks_total": 1234,
  "files_total": 89,
  "last_built_at": "2026-06-24T07:30:00Z",
  "current_progress": { "done": 42, "total": 89 }
}
```

#### 错误响应（§5 强制约束）

```json
{
  "error": {
    "code": "RETRIEVE_EMPTY",
    "message": "未在笔记中找到与该问题相关的内容。",
    "stage": "retrieve"
  }
}
```

---

## 8. 评估与验收标准（v0.2 全部可量化）

### 8.1 检索召回（自动化）

- 内置 `scripts/eval_recall.py`：输入 `[(question, expected_doc_substring_or_heading)]`，对 Top-K 结果计算命中率。
- **指标**：在 10 个样例问题上，Top-5 内命中 ≥ **8**（≥ 80%）。
- **执行**：`uv run python scripts/eval_recall.py`，CI / 本地均可跑。

### 8.2 回答质量与冷启动（自动化断言）

- **冷启动 30s 断言**（v0.3 新增，响应 Reviewer NS2）：`tests/test_cold_start.py` 用 mock 后端 + 计时前端 `index.html` 首字节 → 5 条示例按钮可点击 ≤ 30s。超 30s 视为 §8.4 "冷启动放弃率"事件。
- **US4 断言**：当 retrieve 返回空列表时，API 必须返回"未在笔记中找到相关内容"显式文案（错误码 `RETRIEVE_EMPTY`），**禁止 LLM 自由发挥**。在 `tests/test_chat.py` 用 mock retrieve 写断言。
- **US6 断言**（v0.2 新增；v0.3 强化为前移 + 纯函数行为测试）：US4（无 hits）和 US6（hits 非空但无定义）合并为一条**确定性决策链**，不依赖 LLM 行为：
  1. `hits` 为空 → API 返回 `RETRIEVE_EMPTY` + 文案"未在笔记中找到相关内容"（US4 路径）。
  2. `hits` 非空但 `is_defined_in_hits(query, hits) == False` → API 返回 `NOT_DEFINED` + 文案"你的笔记里没找到 X 的明确定义，仅有的相关片段是：..." + hits（US6 路径，**不发 LLM**）。
  3. `hits` 非空且 `is_defined_in_hits(query, hits) == True` → 走 LLM 生成路径。
  - `is_defined_in_hits` 为**纯函数**（`query: str, hits: list[dict] -> bool`），判定规则初版：任一 hit 文本包含 `query` 后接"是/为/指/：/=/:/-"型定义短语（如 "X 是 ..."、"X：..."、"X = ..."）即视为有定义。具体正则由 ADR-0001 拍板。
  - 测试位置：`tests/test_chat.py` 写 3 条确定性行为断言（US4 / US6 / 正常生成），全部 mock LLM = `unreachable`，**确保 LLM 不被调用**即代表 US6 路径正确。
- 指标：上述断言全部通过 = 质量基线达标。

### 8.3 可启动性（v0.2 拆分为 3a / 3b，响应 Reviewer B2）

- **3a 冷启动 ≤ 3 分钟能问答**：新环境按 README 操作，**用预建索引**（仓库自带一份示例索引，位于 `data/index.sample/`）启动，3 分钟内打开 Web、问出第一条问题并拿到带引用的回答。**onboarding 第一步先 demo 一次**，再让用户挂自己的 Vault。
- **3b 全量索引 README 给出预期时间**：用远程 Embedding API（默认推荐）：100 篇笔记约 5–15 分钟；1000 篇约 30–90 分钟。本地用 Ollama：约为远程的 2–3 倍。README 必须显式列出。

### 8.4 北极星指标（v0.2 新增，响应 Reviewer I4）

衡量"原型是否值得继续投入"，需上线后采集：

| 指标 | 阈值 | 采集方式 |
|------|------|---------|
| **活跃使用频次** | 连续 5 天 ≥ **3 次 / 天** | 浏览器 → `POST /api/usage` → 本机 `data/usage/local-{date}.jsonl`（**不上送任何外部服务**，见 §5） |
| **引用点击率** | ≥ **30%** | 答案页中"点击引用"次数 / 答案显示次数（同上本地采集路径） |
| **冷启动放弃率** | < 20%（首次启动 30 秒内未看到任何反馈的会话占比） | 前端埋点（同上本地采集路径）；测量点见 §3 F8 |

> **判定**：连续观察 1 周内**三项同时达标**，即认为 MVP 验证通过，进入 v0.2 迭代；否则复盘是检索质量、冷启动 UX、还是引用体验问题。

---

## 9. 风险与权衡（v0.2 扩充）

| 风险 | 影响 | 应对 |
|------|------|------|
| 远程 LLM / Embedding 调用成本与隐私 | 用户数据离开本机 | §5 已明确：默认本地 + README 高亮告知 + `.env.example` 不放真实 key |
| 切片策略不当导致召回差 | 回答质量差 | §3 F2 提供可配置 `chunk_size / chunk_overlap`；§8.1 用 `eval_recall.py` 量化 |
| **Obsidian 笔记中含大量代码 / 图片**（v0.2 明确） | 切片与 Embedding 不友好 | MVP 仅处理纯文本，代码块按普通段落切分；图片 / OCR 列为 v0.3+ |
| **首次启动等待时间过长**（v0.2 新增） | 用户放弃 | §3 F8 冷启动 demo：后台异步建索引 + 前台 5 条示例先 demo |
| **大 Vault 全量索引慢**（v0.2 新增） | onboarding 体验差 | §8.3 拆 3a / 3b，先 demo 再挂 Vault；增量更新限定在启动时 mtime diff |
| 启动门槛过高 | 用户放弃 | `uv sync` 一条命令 + 详细 README + 录屏优先 |
| **LLM 在"解释型"场景脑补**（v0.2 新增，响应 Reviewer B3） | 答案失真 | US6 强制兜底 + `tests/test_chat.py` 自动化断言 |

---

## 10. 后续迭代路线

- **v0.2**（MVP 验证通过后）：
  - file-watcher 实时增量同步
  - 对话历史持久化（F10）
  - 过滤器（文件夹 / 时间，F11）
  - 本地 Ollama 端到端 demo
- **v0.3**：多模态（图片 OCR）、知识图谱 / 标签增强
- **v0.4**：Obsidian 插件嵌入，引用协议 `vault://` 已在 §7 预留扩展点
- **v1.0**：多 Vault、多用户、云端部署（视情况）

---

## 11. 硬阻塞项（v0.2 升级，响应开发 §2.8 + Reviewer S2）

> 任何一条未达成 = MAQ-5 不能从 `in_review` 推到 `in_progress`。

| # | 阻塞项 | Owner | 截止 | 落地位置 |
|---|--------|-------|------|---------|
| **B1** | **明确 LLM 框架**（LangChain / LlamaIndex / 直裸） | 开发 | MAQ-5 close 前 | `docs/adr/0001-llm-framework.md` |
| **B2** | **明确向量库**（Chroma / FAISS） | 开发 | MAQ-5 close 前 | `docs/adr/0002-vector-store.md` |
| **B3** | **明确 Embedding / LLM 来源**（远程 API + Ollama） | 开发 | MAQ-5 close 前 | `docs/adr/0003-llm-embedding-source.md` |
| **B4** | **明确 Web 框架**（FastAPI 推荐） | 开发 | MAQ-5 close 前 | `docs/adr/0004-web-framework.md` |
| **B5** | **明确前端形态**（单 HTML + marked.js 推荐） | 开发 | MAQ-5 close 前 | `docs/adr/0005-frontend-shape.md` |
| **B6** | **Vault 规模预期**（笔记数 / 单文件大小） | 产品 | MAQ-5 close 前 | 本 PRD §11 末尾追加 |
| **B7** | **是否需要支持图片 / PDF 附件** | 产品 | MAQ-5 close 前 | 本 PRD §3.3 / §9 |
| **B8** | **是否需要登录 / 鉴权** | 产品 | MAQ-5 close 前 | 本 PRD §3.3 |

**软待办**（不阻塞 in_progress，但要在对应 ADR 落地前答复）：

- **S1**：5 条示例问题清单（产品 + 用户协商后定）。
- **S2**：Recall 评估脚本的 10 题样例集（产品提供 ground truth，开发落代码）。
- **S3**：参考日志 JSON schema 草稿（开发提）。

---

## 附录 A — 候选技术栈（供 ADR 起草参考，不在 PRD 决议）

> 本附录只是把开发评审里提到的候选集中列出，**避免散落在评论里**。具体哪个胜出，由对应 ADR 拍板。

| 决策点 | 候选 | 倾向 | 备注 |
|--------|------|------|------|
| LLM 框架 | LangChain / LlamaIndex / 直裸 SDK | LangChain | 切片 / Embedding / Chroma 一行接好，原型阶段省胶水；直裸更可控但工作量翻倍 |
| 向量库 | Chroma / FAISS / LanceDB | Chroma | 持久化免运维，自带 metadata filter |
| Embedding | 远程 OpenAI 兼容 / 本地 Ollama (`nomic-embed-text`) | 远程优先 + Ollama 可选 | 远程更快更省事，本地更安全 |
| LLM | 远程 API / 本地 Ollama (`qwen2.5` / `llama3`) | 同上 | 看用户偏好 |
| Web 框架 | FastAPI / Flask | FastAPI | 与 `pydantic>=2.7` 自然契合，自带 OpenAPI |
| 前端 | 单 HTML + `marked.js` CDN / Vue 3 CDN / React+Vite | 单 HTML + marked.js | 零构建，README 一条命令跑得起来 |
| 切片 | `RecursiveCharacterTextSplitter` / 手写按标题切 | RecursiveCharacterTextSplitter | 标题 + 长度混合，默认 500/80 |

---

## 附录 B — ADR 清单（开发启动前必须拍板的 5 个 ADR）

| 编号 | 标题 | 优先级 |
|------|------|--------|
| ADR-0001 | LLM 框架选型 | 阻塞 |
| ADR-0002 | 向量库选型 | 阻塞 |
| ADR-0003 | Embedding / LLM 来源（远程 vs Ollama） | 阻塞 |
| ADR-0004 | Web 框架（FastAPI 推荐） | 阻塞 |
| ADR-0005 | 前端形态（单 HTML 推荐） | 阻塞 |

> ADR 一旦 `Accepted`，全员遵循并推翻 PRD 中任何与之冲突的描述。

---

## 附录 C — 评审意见对照表（v0.1 → v0.2 → v0.3）

方便追溯每条意见的处置：

| 来源 | 编号 | 意见 | v0.2 处置位置 |
|------|------|------|----------------|
| 开发 | §1 冲突点：uv | 改用 `uv sync` + `uv run` | §5、§6.1.2 |
| 开发 | §1 冲突点：目录结构 | 沿用三段式 + FastAPI 薄壳 | §6.1.3、§6.3 |
| 开发 | §1 冲突点：data 路径 | 沿用 `data/index/` | §6.1.4 |
| 开发 | §1 冲突点：选型应走 ADR | 重写 §6，附录 B 列 ADR 清单 | §6、附录 B |
| 开发 | §2.1 数据安全矛盾 | §5 改为"默认本地、可选远程、README 高亮" | §5 |
| 开发 | §2.2 流式 | §7 新增 `/api/chat/stream` SSE | §7.2、§7.3 |
| 开发 | §2.3 chunk 默认参数 | §3 F2 给定 `chunk_size=500, chunk_overlap=80` | §3.1 F2 |
| 开发 | §2.4 增量更新范围 | §3 F3 限定为启动时 mtime diff，自动 watcher 延后 v0.2 | §3.1 F3 |
| 开发 | §2.5 引用渲染 | §3 F6 / §7 规定 Markdown + marked.js | §3.1 F6、§7.1 |
| 开发 | §2.6 缺 /api/config 与 /api/index/status | §7 新增两个端点 | §7.2 |
| 开发 | §2.7 config 注入方式 | §6.2.3 强调 .env 注入 | §6.2.3 |
| 开发 | §2.8 §11 硬阻塞化 | §11 升级为硬阻塞表，含 owner + 截止 | §11 |
| 开发 | §2.9 错误响应格式 | §5 强制 `{error: {code, message, stage}}` | §5、§7.3 |
| 开发 | §2.10 日志格式 | §5 规定 JSON 一行格式 | §5 |
| 开发 | §3 ADRs | 附录 B 列 0001–0005 清单 | 附录 B |
| 开发 | §4 验收量化 | §8 全部改为可测指标 + `scripts/eval_recall.py` | §8.1、§8.2 |
| Reviewer | B1 Search+Ask 双面板 | §3 F4 升级为左栏搜索 + 右栏问答 | §3.1 F4 |
| Reviewer | B2 30 分钟矛盾 | §8.3 拆 3a（≤3 分钟 demo）/ 3b（README 列出全量预期时间） | §8.3 |
| Reviewer | B3 定义缺失兜底 | 新增 US6 + §8.2 自动化断言 | §4 US6、§8.2 |
| Reviewer | I1 竞品分析 | §1.4 新增竞品分析表 | §1.4 |
| Reviewer | I2 vault:// 协议 | §7.1 强制 `vault://` 来源协议 | §7.1 |
| Reviewer | I3 冷启动体验 | §3 F8 冷启动 demo | §3.1 F8 |
| Reviewer | I4 北极星指标 | §8.4 新增 | §8.4 |
| Reviewer | I5 性能指标收紧 | §5 改为"首字 ≤2s + 总 ≤10s" | §5 |
| Reviewer | S1 §6 改约束与偏好 | §6 整体重写 | §6 |
| Reviewer | S2 §11 owner + 截止 | §11 升级为硬阻塞表 | §11 |
| Reviewer | S3 读者指南 | §0 新增读者指南 | §0 |

### v0.2 → v0.3 处置（[MAQ-7](mention://issue/0798b1d3-0fca-44dd-84bf-9c40e49d6e47) Reviewer 第二轮）

| 来源 | 编号 | 意见 | v0.3 处置位置 |
|------|------|------|----------------|
| Reviewer | NB1 | US6 断言偏弱（仅验 prompt 包含约束） | §8.2 改为前移到检索后处理 + `is_defined_in_hits` 纯函数 + 早返 |
| Reviewer | NI1 | §8.4 "上报"未说明 | §5 隐私行 + §8.4 三行明确为本地 `data/usage/` |
| Reviewer | NI2 | vault:// 缺编码规则 | §7.1 追加编码规则段 |
| Reviewer | NI3 | F10 浏览器/SQLite 矛盾 | §3.2 F10 收敛为 `localStorage` |
| Reviewer | NS1 | §5 "1k 切片"位置 | §5 性能行拎为明文条件 |
| Reviewer | NS2 | F8 30s 缺测量点 | §3 F8 + §8.2 明确首字节→示例按钮 |
| Reviewer | NS3 | F1 缺默认配置路径 | §3 F1 补 `./config.yaml` + 冷启动兜底 |
| Reviewer | NS4 | ingest --full 与 /api/ingest 关系 | §3 F3 + §6.1.3 明确 CLI ⇔ API 等价 |

---

## 附录 D — 评审流程建议（回应 Reviewer 复盘）

- **Codex 启动失败自检**：Reviewer 任务若 1 轮内未产出有意义回复，应**主动自检 `codex doctor` + 通知环境运维**（见本次 MAQ-5 评论 `e3a760a7...` → `d624a32b...` 的处置流程）。
- **`spec-review.md` 模板**：由 Reviewer 与产品联合基于本次报告骨架（阻塞 / 重要 / 文档结构 三档）抽出首版，归档至 `docs/review/checklists/spec-review.md`（README 标"待补"）。
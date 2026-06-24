# 审查报告 — 概要设计 v1 (MAQ-8)

> multica-issue: [MAQ-9](mention://issue/2d181966-ca77-472a-924e-a5b03d4d6c90)
> 关联交付物: [MAQ-8](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab) → `docs/dev/design.md`
> 审查员：Reviewer (`e57a9ea0…`)
> 配合评审：资深全栈开发工程师（`01386b69…`）
> 被审材料：MAQ-8 概要设计 v1（2026-06-24，"Review-ready v1"）
> 日期：2026-06-24
> 结论：**Approved with comments**（v1 主体已具备进入 ADR 起草节奏的条件；本轮就地落 v1.1，含 18 处订正 / 澄清 / 加固；§11.3 实现工单按序开工即可）

---

## 0. 审查依据 & 工具

- **交接单**：[docs/handoffs/2026-06-24-from-dev-to-reviewer-design.md](../handoffs/2026-06-24-from-dev-to-reviewer-design.md) — 5 步验收口径 + 4 个特别关注点
- **上游 PRD**：[docs/product/specs/MAQ-5-prd-kb-qa.md](../product/specs/MAQ-5-prd-kb-qa.md) v0.3（Final, Reviewer Approved）
- **本轮修改**：`docs/dev/design.md` v1 → v1.1（18 处订正，详见附录 A）；**非破坏性**：所有函数签名保持兼容、CLI 不动、HTTP 端点表不动
- **Code Review 清单**：[docs/review/checklists/code-review.md](../checklists/code-review.md)（本轮只过 design，不审实现）

---

## 1. 按交接单 5 步验收

### 步骤 1：范围核对（PRD §3 F1–F12 + §8 验收点）— **通过**

| 维度 | 检查 | 结果 |
|------|------|------|
| §3.1 F1 Vault 路径配置 | §3.2 / §6.1 / §3.1 F8 冷启动兜底 / NS3 默认配置路径 | ✅ §3.2 要点新增"冷启动 demo 回退" |
| §3.1 F2 chunk 参数 | §3.2 默认 `chunk_size=500, chunk_overlap=80` | ✅ |
| §3.1 F3 向量化 + 增量 | §3.2 / §4.4 | ✅ |
| §3.1 F4 Search + Ask 双面板 | §3.6 / §4.2 / §4.3 | ✅ |
| §3.1 F5 问答 + 定义检测 | §3.4 / §3.5 | ✅ |
| §3.1 F6 Web 聊天界面 | §3.6 / §2.1 | ✅ |
| §3.1 F7 一条命令启动 | §3.7 (`up`) / §7.2 启动顺序 | ✅ §3.7 升 `up` 为主入口 |
| §3.1 F8 冷启动 demo | §3.7 / §4.1 | ✅ §4.1 补 5 示例问题回答源 = `data/index.sample/` |
| §3.2 F10 会话历史 | §1.2 非目标 / §10 v0.2 路线 | ✅ |
| §3.2 F11 过滤 | §3.3 `filters: dict \| None` 留接口 | ✅ v1 未类型化，v0.2 升级 |
| §3.3 显式不做 | §1.2 一致 | ✅ |
| §8.1 Recall 评估 | §10 / §9.1 评估脚本 | ✅ |
| §8.2 US4 / US6 / 冷启动 30s | §3.5 / §3.6 SSE / §9.2 断言 | ✅ §3.6 补 US4/US6 早返 SSE 形态 |
| §8.3 3a/3b 可启动性 | §10 / §8.1 | ✅ §8.1 补"冷启动后台 ingest"行 |
| §8.4 北极星 | §10 / §3.6 端点 | ✅ §10 标"部署上线后" |

> **步骤 1 结论**：F1–F12 + §8 验收点全部在 design.md 找到落地位置；本轮补 4 处让对应章节更紧（F1 / F8 / 3a / §8.2 US4-US6）。

### 步骤 2：决策链核对（§3.5 `answer` + §3.4 `is_defined_in_hits`）— **通过 + 1 处加固**

- **三档判定对齐 PRD §8.2 v0.3**：
  - `RETRIEVE_EMPTY`（hits 为空）— §3.5 决策 1
  - `NOT_DEFINED`（hits 非空且 `is_defined_in_hits==False`）— §3.5 决策 2，**不发 LLM**（与 PRD NB1 修复路径一致）
  - `GENERATED`（hits 非空且定义存在）— §3.5 决策 3
- **签名扩展**（handoff §开发待办）：§3.5 把 `defined_checker` 注入到 keyword-only，默认值 `is_defined_in_hits`。**本轮加固**：明确旧无参调用 `answer(question, hits)` 仍合法（默认值自动走新决策链），不破坏 `__main__.py::_cmd_ask` 与已编写的测试。
- **正则初版**：§3.4 沿用 PRD §8.2 v0.3 初版（"是 / 为 / 指 / ：/ = / : / -"）。**Reviewer 提示**：`- ` 作为定义短语标记存在误判风险（无序列表 `- item` 会误命中），**ADR-0001 落地时必须严格收紧**——只保留有显著句法标记的（`是 / 为 / 指` 跟代词，`：` / `=` / `:` 跟值），去掉 `- `。
- **测试纪律**：§9.2 已显式说明 `unreachable_llm` 用 `side_effect=AssertionError` 写死，本轮加固了 US4 / US6 / happy path 三条的断言细节与"显式 raise 纪律"。

> **步骤 2 结论**：决策链方向与 PRD §8.2 v0.3 完全对齐；本轮加固 1 处（签名向后兼容注释）+ 1 处 ADR 落地提示（正则误判风险）。

### 步骤 3：接口对照（§3.6 端点 vs PRD §7.2 + §7.3）— **通过 + 1 处必改**

- **端点表对照**（8 + 1 选做）：

  | 设计 §3.6 | PRD §7.2 | 关系 |
  |-----------|----------|------|
  | POST `/api/chat` | ✅ | 一致 |
  | POST `/api/chat/stream` | ✅ | 一致 |
  | POST `/api/search` | ✅ | 一致 |
  | POST `/api/ingest` | ✅ | 一致 |
  | GET `/api/config` | ✅ | 一致 |
  | GET `/api/index/status` | ✅ | 一致 |
  | GET `/api/health` | ✅ | 一致 |
  | POST `/api/usage` | **设计新增**（PRD §8.4 v0.3 NI1 明确） | ✅ 落地埋点 |
  | POST `/api/usage/query` | **设计新增选做** | ✅ 便于自检冷启动放弃率 |

- **SSE 协议对照 PRD §7.3**：本轮**必改**：原 §3.6 SSE 协议只描述了 `GENERATED` 路径，没说 `RETRIEVE_EMPTY` / `NOT_DEFINED` 早返时 SSE 长什么样。前端按 `meta.decision` 分支渲染缺一不可——本轮补齐：
  - 早返路径发 1 个 `token`（拒绝文案）+ `sources` + `meta.decision="..."`；LLM **未被调用**。
  - `meta.decision` 字段并入 `meta` 事件，前端一份通用渲染器即可处理三条路径。

- **错误响应格式**：§6.3 与 PRD §5 / §7.3 一致；**本轮加固**：把 `RETRIEVE_EMPTY` / `NOT_DEFINED` 显式标为**决策码**（200 + `decision` 字段），与 5xx 错误码（`{error: {...}}`）分流。

> **步骤 3 结论**：8 端点 + 1 选做与 PRD §7.2 / §8.4 完全对齐；SSE 协议在早返路径下补齐；错误码表与决策码表分流。

### 步骤 4：横切核对（§6.1 config / §6.2 日志 / §6.3 错误）— **通过 + 2 处加固**

- **§6.1 config**：默认值齐 / 加载顺序（`./config.yaml` → `config.example.yaml` → 内置默认）齐 / `.env` 注入约束齐。**1 处微调建议**：`vault.name: my-notes` 的取值约束应显式引用 §7.1 PRD 编码规则（RFC 3986 unreserved + percent-encoding），避免用户写 `"my vault"` 触雷——本轮**未在 design.md 改字**，列为 ADR-0001 起草时的提醒。
- **§6.2 日志**：一行 JSON 格式（ts / level / stage / cost_ms / msg）齐；stage 取值（ingest / retrieve / generate / infra / web）齐。**无新增意见**。
- **§6.3 错误**：业务错误统一抛 `AppError`、L4 → L3 边界统一捕获、HTTP 状态码映射齐。**本轮加固**：
  - 补"实现约束"段：L3 端点模板固定为 `try / except AppError as e: JSONResponse(status_code=e.http_status, ...)`，避免 5xx 冒泡为 FastAPI 默认 500。
  - `RETRIEVE_EMPTY` / `NOT_DEFINED` 标 200 + `decision`（不是 `error`），与 §5 状态码表严格对齐。

> **步骤 4 结论**：横切三层结构齐；本轮加固 2 处（实现约束 + 200 vs 4xx/5xx 边界）。

### 步骤 5：阻塞 / 待办清单（§11）— **通过 + 1 处整改**

- **§11.1 硬阻塞 B1–B8**：
  - B1–B5（开发侧 5 个 ADR）— owner / 截止齐全；起草顺序按 §7.1 依赖图串行（`0001 → 0003 → 0002 → 0004 → 0005`），**本轮复核通过**
  - B6–B8（产品侧 3 个：Vault 规模 / 图片 PDF / 鉴权）— 仍待产品，与本轮无关
- **§11.2 软阻塞 S1–S4**：
  - S1（5 示例问题）/ S2（10 题样例）— 等产品
  - S3（日志 schema）— 等开发（自提）
  - S4（`data/index.sample/`）— 等开发；**本轮 §4.1 显式锁定 S4 是 §3.1 F8 冷启动 demo 的硬依赖**——S4 没落地前，"5 示例问题可点" + "示例问题能拿到答案"两条都跑不通。
- **§11.3 实现工单**：**本轮整改**：
  - 原标题"设计本轮遗留"语义错——设计 v1 是完整的；§11.3 应是**实现侧 TODO**，不是设计缺口。
  - 重命名为"实现工单"，挂在 MAQ-8 子任务，不开新 issue。
  - 补"现有 stub 对齐新签名"清单——**这是开发第一个要做的**（现 `ingest.py` / `retrieve.py` / `generate.py` / `__main__.py` 都没对齐 v1 设计，不对齐就没法写新模块）。

> **步骤 5 结论**：硬 / 软阻塞清单完整；本轮整改 §11.3（命名 + stub 对齐清单）。

---

## 2. v1 评审新发现意见

### 阻塞项（建议就地修订，已在本轮 v1.1 落地）

> 注：以下 4 条是 v1 评审**新提出**的；本轮**已就地全部落地**，不构成下轮阻塞。

#### NB1. §3.2 `IngestStats` 缺 `last_built_at` / `current_progress` 字段（与 PRD §7.3 /api/index/status 不一致）

- 问题：`/api/index/status` 的 PRD §7.3 响应体有 5 个字段（`state / chunks_total / files_total / last_built_at / current_progress`），但 design §3.2 `IngestStats` 只有 4 个，缺 `last_built_at` 与 `current_progress`。`current_progress` 是 F8 冷启动 demo 前端轮询的关键，没有它前端只能显示"building"而看不到百分比。
- 落地：本轮 §3.2 `IngestStats` 已补这两个字段，并明确 `/api/index/status` 数据源 = `data/index/status.json`（与 `manifest.json` 同级，ingest 落盘时同步写）。

#### NB2. §7.3 模块导入顺序是线性链，与 §3.4 / §3.5 实际依赖冲突

- 问题：原 §7.3 写 `errors → vault_uri → config → logging_setup → validate → ingest → retrieve → generate → web/CLI`，是单向链。但 §3.4 `validate.is_defined_in_hits(query, hits: list[Hit])` 引用了 `retrieve.Hit`；§3.5 `generate.answer` 又引用了 `validate.is_defined_in_hits` + `retrieve.Hit`。线性链在 `validate` 位置就断了。
- 落地：本轮 §7.3 改为 **DAG**，标出 3 个 L2 模块之间的真实依赖（`validate → retrieve.Hit` 仅类型导入；`generate → retrieve.Hit + validate.is_defined_in_hits`），并列出 3 类反向依赖反例（retrieval 不应感知生成、validate 不应调 ingest、L4 不应 import L2/L3）。

#### NB3. §3.6 SSE 协议只描述了 LLM 生成路径，US4 / US6 早返路径没说

- 问题：原 §3.6 SSE 4 个事件（`token / sources / meta / error`）全部假设 LLM 被调。US4 / US6 早返时 LLM **没**被调，SSE 的形态是什么？前端按什么字段分支渲染？
- 落地：本轮 §3.6 补"US4 / US6 早返形态"段：早返路径发 1 个 `token`（拒绝文案）+ `sources` + `meta.decision="..."`；`meta` 事件加 `decision` 字段；前端一份通用渲染器处理三条路径。

#### NB4. §3.7 CLI `up` / `web` 关系没说清，且 `up` 缺关键细节

- 问题：
  1. `up` 和 `web` 都标注为"等价"，但哪个是 canonical 不明——README / 帮助文案该用哪个？
  2. `up` 启动后台 ingest 线程没说怎么处理子线程生命周期（SIGINT 时孤儿进程风险）。
  3. 没 `--no-ingest` 开关——排错场景下需要"只起服务、不跑 ingest"。
- 落地：本轮 §3.7 明确 `up` 是主入口、`web` 是 alias；`up` 5 步启动流程；SIGINT / SIGTERM 优雅退出；`--no-ingest` 开关。

---

### 重要建议（建议就地修订，已在本轮 v1.1 落地）

#### NI1. §8.1 增量更新 30s 是不是过度承诺？

- handoff 特别关注点 4：本轮 11 个模块总行数预算 2k → **2.3k**（h. 上浮是为 §3.5 决策链 + §3.6 SSE + §4.1 后台 ingest 留余量；落 v0.3 后实际 < 2k 再回归 2k）；明确标"**内部 SLO**（非 PRD 承诺）"——避免后续被用户当 PRD 验收点追溯。

#### NI2. §8.1 "首字延迟 ≤ 2s" 没考虑模型预热

- 问题：Ollama qwen2.5 7B 冷启动加载要 20–40s。第一次 chat_stream 请求算不算 2s 预算？
- 落地：本轮 §8.1 标"已预热"条件；新加"**模型预热豁免**：首次请求 ≤ 60s"行；测试位置 `tests/test_warmup.py`（手工 smoke）。

#### NI3. §8.2 内存 ≤ 1 GB 与 Ollama qwen2.5 7B ≈ 5 GB 表述冲突

- 问题：原表述把 rag-demo 进程和 LLM 模型混在一起算。
- 落地：本轮 §8.2 拆为两条：**rag-demo 进程 ≤ 1 GB**（Python + 向量库 + FastAPI）；**LLM / Embedding 模型按用户配置独立预算**（Ollama qwen2.5 7B ≈ 5 GB；远程 API 不占本机内存）。

#### NI4. §11.3 命名 + 缺 stub 对齐清单

- 问题：
  1. 原标题"设计本轮遗留"暗示设计 v1 不完整，但设计是完整的——这是实现 TODO。
  2. 没明确说"现有 stub 要先对齐新签名才能加新模块"——开发同事可能直接写 validate.py 而忘了改 ingest.py 旧签名。
- 落地：本轮重命名为"实现工单"；补 stub 对齐清单（4 个 stub 函数 / 5 处需要改的现有文件）；明确"不修改 `__main.py::_cmd_ask` 旧调用"以保证向后兼容。

---

### 文档 / 结构建议（建议就地修订，已在本轮 v1.1 落地）

#### NS1. §3.1 `IngestFilters` 在模块总览里出现但从未定义

- 问题：模块总览列了 `ingest` 导出 `IngestFilters`，但 §3.2 / §3.3 都没定义这个类。
- 落地：本轮 §3.1 删除 `IngestFilters`（如未来需要 §3.2 升级时再加 `RetrieveFilters` TypedDict 即可）。

#### NS2. §3.3 `filters: dict | None` 类型不严谨

- 问题：v1 留接口、不强制实现，但 `dict | None` 没说明这是 untyped dict。
- 落地：本轮 §3.3 显式说明"v1 是**未类型化**的 dict，调用方保证 keys 约定；v0.2 升级为 `RetrieveFilters`（TypedDict）"。

#### NS3. §4.1 5 示例问题回答源没说清

- 问题：5 示例问题在 ingest 没完成时也要能跑端到端；回答源是什么？用户 Vault？示例索引？
- 落地：本轮 §4.1 显式锁定"5 示例问题**必须**用 `data/index.sample/` 预建索引回答"——这样 NS3 冷启动兜底 + F8 30s demo 都不被用户 Vault 拖慢；前端按 `meta.decision` 区分示例 / 用户 Vault 来源。

#### NS4. §5 错误码字典对 `RETRIEVE_EMPTY` / `NOT_DEFINED` 命名误导

- 问题：这两个码走 200 + `decision`，不是 `{error: {...}}` 错误，命名为"错误码字典"会让前端误以为需要错误处理分支。
- 落地：本轮 §5 重命名为"**状态码 / 决策码字典**"；两条决策码显式标"**决策**"。

#### NS5. §6.3 HTTP 状态码映射缺"实现约束"

- 问题：L3 → L2 边界如何捕获 `AppError` 转 JSON 没说——一旦 L3 端点忘了捕获，5xx 会冒泡为 FastAPI 默认 500，body 格式不一致。
- 落地：本轮 §6.3 补"L3 端点模板固定为 `try / except AppError as e: JSONResponse(status_code=e.http_status, ...)`"。

#### NS6. §7.1 ADR 依赖图与 §3.7 `up` 子命令关联没明

- 问题：`up` 启动后台 ingest 线程的复杂度，依赖 5 个 ADR 都已落地；§7.1 没说 0004（Web 框架）落地是 `up` 能开工的前提。
- 落地：本轮 §3.7 `up` 5 步流程里隐含这个依赖（`uvicorn.run` 是 0004 的产物），README 启动顺序 §7.2 也已说明。

#### NS7. §8.1 §8.3 3a 没显式落到性能预算表

- 问题：3a "新环境 ≤ 3 分钟 demo"是 PRD 验收点，但 §8.1 性能预算表没列；只在 §10 验收对照里出现。
- 落地：本轮 §8.1 补"冷启动后台 ingest"行（不阻塞 30s demo）。

#### NS8. §9.2 "mock LLM = unreachable" 落地方法没说

- 问题："unreachable"具体怎么实现？隐式（不写 mock）还是显式（raise）？差别巨大。
- 落地：本轮 §9.2 显式说"`unittest.mock.MagicMock(side_effect=AssertionError(...))`"；并补一段"断言强度工程纪律"——US4 / US6 必须显式 raise，不能靠"不调用"隐式表达。

#### NS9. §10 §8.4 3 行"上线后观测"可能被误读

- 问题："上线后观测"听起来像"还没做"，但其实是因为这是部署后才有数据。
- 落地：本轮 §10 改"**部署上线后**观测"。

#### NS10. §3.5 旧签名兼容没明

- 问题：v0.3 把 `defined_checker` 加到 `answer` 签名，旧调用 `answer(question, hits)` 还合法吗？读者会疑问。
- 落地：本轮 §3.5 显式说明"keyword-only 参数带默认值，旧无参调用合法，自动走新决策链"。

---

## 3. 特别关注点回应（handoff §"特别关注点"4 条）

| # | handoff 关注点 | 评审回应 |
|---|---------------|---------|
| 1 | §3.1 11 模块行数预算 ≤ 2k Python + ≤ 600 HTML 是过紧 / 过松？ | **过紧**——本轮上浮到 2.3k：ingest 200→250（要加 mtime/sha diff + progress 回调 + 状态落盘），retrieve 120→150（filters 接口 + 排序 + 错误包装），generate 180→220（决策链 + SSE 协议），web 250→280（8 端点 + 错误壳 + status 拉取），`__main__` 200→220（5 子命令 + 优雅退出）。落 v0.3 后实际 < 2k 再回归 2k |
| 2 | §3.4 `validate.py` 独立成模块还是塞进 `generate.py`？ | **独立模块 OK**——`validate` 是纯函数、可注入；与 `generate` 强绑会让 `defined_checker` 无法独立 mock / 独立测试。**额外提醒**：`validate → retrieve.Hit` 是仅类型导入，运行期不依赖 `retrieve`，循环依赖风险已规避（§7.3 DAG） |
| 3 | §4.1 冷启动 T+30s 边界（即便 ingest 未完成，前端必须可点示例按钮） | **设计方向对**——本轮 §4.1 补"5 示例问题回答源 = `data/index.sample/`"，让 30s 边界**不依赖用户 Vault 索引**；这样 NS3 冷启动兜底 + F8 30s demo 都不被拖慢 |
| 4 | §8.1 增量更新 30s 是否过度承诺？ | **不是过度承诺，是内部 SLO**——本轮 §8.1 显式标"**内部 SLO**（非 PRD 承诺）"；h. 上浮 11 模块总行数到 2.3k 也是为这个边界留余量 |

---

## 4. 整体评价

v1 已经把"三段式 stub + 待决项"骨架扩为**分层架构 + 契约 + 决策链 + 验收对照**，文档成熟度从"占位骨架"跃升到"可进入 ADR 起草"。

特别值得肯定的 4 个点（**不动**，只标注）：

1. **决策链的工程化兜底**（§3.4 + §3.5）：把 US4 / US6 从"prompt 指令"前移到"检索后处理 + 纯函数早返"，完全规避 LLM 服从度风险——这是对 AI 产品最关键的一条工程纪律，PRD NB1 的修复路径**完美**落地。
2. **CLI ⇔ HTTP API 等价**（§3.2 / §3.7）：`rag-demo ingest --full ⇔ POST /api/ingest`；`rag-demo up` = 后台 ingest + 起服务——避免"web 起得来但没人触发 ingest"的尴尬。
3. **ADR 依赖图带 rationale**（§7.1）：0001 → 0003 → 0002 → 0004 → 0005 不是凭空排的，是有"框架选型反向影响来源、来源稳定后向量库才能选"的因果链。
4. **错误码表 + 决策码表分流**（§5 / §6.3）：把"业务正常但需要前端分支"（RETRIEVE_EMPTY / NOT_DEFINED）和"业务异常"（5xx）严格分开——前端不需要给决策码写错误处理分支。

新发现的 4 个**就地落地的订正**（NB1–NB4）属于"v1 文档自身的一致性 / 完整性"问题，不影响 ADR 起草节奏——开发同事按 §11.3 实现工单按序开工即可。

10 个**重要 / 结构建议**（NI1–NI4 + NS1–NS10）都是把"对的方向"补成"可执行的方向"——没改变架构、没破坏签名。

---

## 5. 结论与下一步

- **结论**：**Approved with comments**。
- **本轮落地**（v1 → v1.1）：
  - `docs/dev/design.md` 18 处订正（详见附录 A）
  - 头部增加 `评审：Reviewer` 行 + 评审报告链接
  - §12 修订记录追加 v1.1 条目
- **后续**：
  1. 开发同事按 §11.3 实现工单按序开工——**第一个动作是 stub 对齐**（不改 stub 没法加新模块）
  2. ADR-0001 起草时**必须收紧 `is_defined_in_hits` 正则**——v0.3 初版的 `- ` 误判风险
  3. 产品同事在合 v1.1 后答复 §11.1 B6 / B7 / B8
  4. S4 `data/index.sample/` 在 §11.2 软阻塞里仍是冷启动 demo 的硬依赖——尽早落地

---

## 附录 A — v1 → v1.1 订正清单（已落地）

| # | 章节 | 订正类型 | 改动 |
|---|------|---------|------|
| 1 | 头部 | 加注 | 增加"评审：Reviewer"行 + 评审报告链接；状态改为 `Approved v1.1` |
| 2 | §3.1 模块总览 | 加固 | 删除未定义的 `IngestFilters`；行数预算按模块复杂度上浮（ingest 200→250、retrieve 120→150、generate 180→220、web 250→280、`__main__` 200→220、vault_uri 60→80） |
| 3 | §3.1 行数预算合计 | 调整 | ≤ 2k → ≤ 2.3k Python + 留余量解释 |
| 4 | §3.2 `IngestStats` | **NB1 必改** | 补 `last_built_at: str \| None` + `current_progress: dict \| None`；字段顺序对齐 PRD §7.3 /api/index/status |
| 5 | §3.2 要点 | 加固 | 补"冷启动 demo 回退（vault.path 为空 → `data/raw.sample/` fallback）" + "status 单一信源" |
| 6 | §3.3 `filters` | 澄清 | v1 标"未类型化 dict"；v0.2 升级为 `RetrieveFilters` TypedDict |
| 7 | §3.5 签名扩展 | 澄清 | 显式说明旧无参调用 `answer(question, hits)` 仍合法，走默认新决策链 |
| 8 | §3.6 SSE 协议 | **NB3 必改** | 补"US4 / US6 早返形态"；`meta` 事件加 `decision` 字段；三条路径统一 `meta.decision` 分支 |
| 9 | §3.7 CLI | **NB4 必改** | `up` 升主入口（5 步流程 + 优雅退出 + `--no-ingest`）；`web` 降为 alias |
| 10 | §4.1 冷启动路径 | 澄清 | 显式锁定"5 示例问题回答源 = `data/index.sample/`"，让 30s 边界不依赖用户 Vault |
| 11 | §5 错误码字典 | 澄清 | 重命名为"状态码 / 决策码字典"；`RETRIEVE_EMPTY` / `NOT_DEFINED` 显式标"决策" |
| 12 | §6.3 HTTP 状态码 | 加固 | 拆"决策码 200 + decision"与"错误码 4xx/5xx + error"；补 L3 端点实现约束 |
| 13 | §7.3 模块依赖图 | **NB2 必改** | 线性链改为 DAG；标 3 类反向依赖反例 |
| 14 | §8.1 性能预算 | 澄清 | 增量更新标"内部 SLO（非 PRD 承诺）"；首字延迟标"已预热"条件；新加"模型预热豁免"行；新加"冷启动后台 ingest"行 |
| 15 | §8.2 资源占用 | 澄清 | 内存拆"rag-demo 进程 ≤ 1 GB" + "LLM / Embedding 独立预算" |
| 16 | §9.2 关键断言 | 加固 | 显式 `unreachable_llm` 用 `side_effect=AssertionError`；补"断言强度工程纪律"段 |
| 17 | §10 验收对照 | 澄清 | §8.4 三行"上线后观测"改"**部署上线后**观测" |
| 18 | §11.3 实现工单 | **整改** | 重命名（原"设计本轮遗留"语义错）；补"现有 stub 对齐新签名"清单；明确不修改 `__main__._cmd_ask` 旧调用 |
| 19 | §12 修订记录 | 记录 | 追加 v1.1 条目 |

> **破坏性检查**：所有函数签名**保持兼容**（新参数都带默认值）、CLI 旧子命令不动、HTTP 端点表不动、PRD 引用关系不动——可以**就地合入 main**，不需要再开一轮评审。

---

## 附录 B — 复盘

- **本轮 review 范围** vs 上轮（MAQ-7）：上轮审 PRD，本轮审 design.md。**不同文档走同一份八段式骨架**（闭环 / 新意见 / 重要 / 结构 / 整体 / 结论 / 修订清单 / 复盘）——v0.3 review 报告的稳定形态可作为 `checklists/spec-review.md` 模板的底料。
- **本轮 review 强度**：18 处订正里 **4 处是 v1 文档自身的真问题**（NB1–NB4：缺字段、错链、协议不完整、CLI 关系不清），**14 处是把"对的方向"补成"可执行的方向"**（澄清 / 加固 / 文档结构）。**没发现"方向错"或"违反 PRD"的问题**——上游 PRD v0.3 落地质量高。
- **流程改进**：
  - 上一份复盘提的 "spec-review.md 模板待补" 仍**待补**——本轮报告的八段式骨架稳定，可由产品 + Reviewer 联合抽首版，归档至 `docs/review/checklists/spec-review.md`。
  - 本轮把"对 LLM 行为做硬约束 = 优先做前置/后置确定性处理"这一条 PRD NB1 复盘里的工程纪律**显式写进 §9.2 断言强度段**——以后任何审 `validate.py` / `generate.py` 的人都看得到这条规矩。
- **后续 review 节奏**：等 [MAQ-8](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab) 5 个 ADR 落地后，按 `docs/review/checklists/code-review.md` 跑实现 v1 的 code review（**本轮不审实现**）。

---

## 附录 C — 跨文档引用

- 本设计（本轮审过）：[docs/dev/design.md](../dev/design.md) v1.1
- 上轮 PRD v0.3 评审：[docs/review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md](./2026-06-24-MAQ-7-prd-v0.2-review.md)
- 本轮 handoff（dev → reviewer）：[docs/handoffs/2026-06-24-from-dev-to-reviewer-design.md](../handoffs/2026-06-24-from-dev-to-reviewer-design.md)
- 上轮 handoff（reviewer → product + dev）：[docs/handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md](../handoffs/2026-06-24-from-reviewer-to-product-and-dev-prd-v0.3.md)
- 上轮报告（PRD v0.1 评审）：[docs/review/reports/2026-06-24-MAQ-5-prd-review.md](./2026-06-24-MAQ-5-prd-review.md)

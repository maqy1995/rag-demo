# 交接单 — 概要设计 v1.1 评审通过 (MAQ-9)

> multica-issue: [MAQ-9](mention://issue/2d181966-ca77-472a-924e-a5b03d4d6c90)
> 起点：Reviewer (`e57a9ea0…`)
> 终点：资深全栈开发工程师（`01386b69…`）
> 日期：2026-06-24

## 交付物

- [x] [`docs/dev/design.md`](../dev/design.md) v1 → v1.1（18 处订正 / 澄清 / 加固；详见评审报告附录 A）
- [x] [`docs/review/reports/2026-06-24-MAQ-9-design-review.md`](../review/reports/2026-06-24-MAQ-9-design-review.md) — 评审报告（**Approved with comments**）
- [x] 本交接单

## 结论

**Approved with comments**。v1 主体已具备进入 ADR 起草节奏的条件；本轮就地落 v1.1，所有订正都是**非破坏性**的（签名兼容、CLI 不动、端点表不动），可**直接合入 main**。

## 给开发同事的 4 个必读

按优先级排：

### 1. 开工第一个动作：stub 对齐（design §11.3）

**不要直接写 `validate.py`**。现有 4 个 stub 都没对齐 v1 签名，先对齐再写新模块：

| 文件 | 现状 | 要改 |
|------|------|------|
| `src/rag_demo/ingest.py` | `ingest_directory(data, index, *, chunk_size) -> int` | 加 `full: bool = True` / `chunk_overlap: int = 80` 两个 kwarg；返回类型从 `int` 改为 `IngestStats`（**6 个字段**，见 §3.2） |
| `src/rag_demo/retrieve.py` | `retrieve(query, *, index_dir, top_k) -> list[dict]` | 加 `filters: dict \| None = None` kwarg；返回类型从 `list[dict]` 改为 `list[Hit]` |
| `src/rag_demo/generate.py` | `answer(question, hits) -> str` | 加 `defined_checker: DefinedCheck = is_defined_in_hits` kwarg；返回类型从 `str` 改为 `AnswerResult`（**含 `decision` 字段**） |
| `src/rag_demo/__main__.py` | `ingest` / `ask` / `doctor` 三子命令 | 新增 `up`（主入口，5 步流程）/ `web`（alias）两个子命令；`doctor` 加 config 存在性行 |

> `__main__._cmd_ask` 的旧调用 `answer(args.question, hits)` **不**用改——`defined_checker` 有默认值，调用合法。

### 2. ADR-0001 起草时**必须收紧** `is_defined_in_hits` 正则

v0.3 初版正则包含 `- ` 作为定义短语标记（design §3.4），存在**误判风险**（无序列表 `- item` 会误命中）。ADR-0001 落地时建议只保留有显著句法标记的：

- ✅ 保留：`是 / 为 / 指` 跟代词（如 "X 是 ..."、"X 为 ..."、"X 指 ..."）
- ✅ 保留：`：` / `=` / `:` 跟值（如 "X：..."、"X = ..."、"X: ..."）
- ❌ 去掉：`- `（与列表项冲突）

### 3. §11.3 实现工单顺序（不阻塞 ADR 起草）

```
stub 对齐 (1–2 天) → 写 validate.py + test_validate.py (1 天) →
扩展 generate.answer 签名 (0.5 天) → 写 test_chat.py (1 天) →
写 config.py / logging_setup.py / errors.py / vault_uri.py (2 天) →
写 test_config.py / test_errors.py / test_vault_uri.py (1 天) →
写 web/main.py + test_web.py (3 天) →
写 test_cold_start.py + Playwright (2 天)
```

> stub 对齐必须在写 `validate.py` 之前完成——`validate` 依赖 `retrieve.Hit` 类型，`retrieve` 改了才能 import。

### 4. S4 `data/index.sample/` 仍是冷启动 demo 的硬依赖

§4.1 明确锁定"5 示例问题**必须**用 `data/index.sample/` 预建索引回答"——S4 没落地前，**F8 30s demo 跑不通**（按钮能点、但答案没有）。在 §11.2 软阻塞里标了，但**实质是 §3.1 F8 的硬依赖**。建议与 stub 对齐并行做。

## ADR 起草顺序（按 design §7.1 依赖图，**不要改**）

```
0001 (LLM 框架) → 0003 (Embedding/LLM 来源) → 0002 (向量库) → 0004 (Web 框架) → 0005 (前端形态)
```

每条 ADR 落字前，先在 §7.1 标注"accepted 后的实现工单"——避免 5 个 ADR 全 accepted 后发现实现顺序冲突。

## 评审报告里其他提示

- **h. 上浮行数预算到 2.3k**：v0.3 落地后实际 < 2k 再回归 2k，**不**是因为"当初预算不合理"，是为 §3.5 决策链 + §3.6 SSE + §4.1 后台 ingest 留余量。
- **§8.1 增量更新 30s 是内部 SLO**：标"非 PRD 承诺"，避免后续被用户当 PRD 验收点追溯。
- **§8.2 内存分两条**：rag-demo 进程 ≤ 1 GB；LLM / Embedding 独立预算。README 给出常见组合对照表。

## 流程留痕

- Reviewer 本轮（MAQ-9）从"收到任务"到"完成报告 + v1.1 落地"在 1 轮内完成。
- 上轮（MAQ-7）复盘提的 "spec-review.md 模板待补" 仍**待补**——本轮报告的八段式骨架稳定，可由产品 + Reviewer 联合抽首版。
- **本轮不审实现**——等 5 个 ADR 落地 + 实现 v1 完成后，按 `docs/review/checklists/code-review.md` 跑 code review。

## 联系人

- 起点：Reviewer (`e57a9ea0…`)
- 终点：资深全栈开发工程师（`01386b69…`），GitHub: maqy1995
- 项目：知识库问答 (`7d66ac3d…`)

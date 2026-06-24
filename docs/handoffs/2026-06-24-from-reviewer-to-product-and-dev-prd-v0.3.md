# 交接单 — PRD v0.3 定稿

> 日期：2026-06-24
> 起点：审查员（Reviewer, `e57a9ea0...`）
> 终点：产品（`1871feaf...`）+ 资深全栈开发工程师（`01386b69...`）
> multica-issue: [MAQ-7](mention://issue/0798b1d3-0fca-44dd-84bf-9c40e49d6e47)
> 关联交付物: [MAQ-5](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c)

## 交接什么

PRD v0.2 → v0.3 定稿（含 review 报告），进入 PR 提交阶段。

- **PRD v0.3**：`docs/product/specs/MAQ-5-prd-kb-qa.md`
- **本轮 review 报告**：`docs/review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md`

## 结论

**Approved with comments**（结论详见 review 报告 §3）。v0.2 主体已具备
进入 `in_progress` 的条件；v0.3 就地把 1 个新阻塞（NB1）+ 3 个重要建议
（NI1-NI3）+ 4 个结构建议（NS1-NS4）全部落地。

## 给产品同事的待办（阻塞 / 软阻塞）

### 硬阻塞（§11 维持原状，本轮未变动）

| 编号 | 内容 | 截止 |
|------|------|------|
| B6 | Vault 规模预期（笔记数 / 单文件大小）| MAQ-5 close 前 |
| B7 | 是否需要支持图片 / PDF 附件 | MAQ-5 close 前 |
| B8 | 是否需要登录 / 鉴权 | MAQ-5 close 前 |

### 软阻塞（不阻塞 in_progress，但在对应 ADR 落地前需答复）

| 编号 | 内容 |
|------|------|
| S1 | 5 条示例问题清单（产品 + 用户协商后定） |
| S2 | Recall 评估脚本的 10 题样例集（产品提供 ground truth） |
| S3 | 参考日志 JSON schema 草稿（开发提） |

## 给开发同事的待办（不阻塞 PR 合入）

- v0.3 落地后，**§3 F5 / §8.2 出现了一个新业务函数 `is_defined_in_hits(query, hits) -> bool`**，在 `src/rag_demo/` 下需要新增第四个文件（建议命名 `validate.py` 或并入 `generate.py`）。该函数签名为：
  ```python
  def is_defined_in_hits(query: str, hits: list[dict]) -> bool: ...
  ```
  具体正则由 ADR-0001（LLM 框架）拍板，PRD 给出的初版是"任一 hit 包含 `query` 后接'是/为/指/：/=/:/-'型短语"。
- v0.3 新增 `is_defined_in_hits` 函数后，**`generate.answer()` 的签名要扩展**（增加判定阶段）。建议新签名：
  ```python
  def answer(question: str, hits: list[dict], *, defined_checker: Callable = is_defined_in_hits) -> str: ...
  ```
  旧签名（无 `defined_checker`）保持向后兼容，默认走新逻辑。
- v0.3 新增埋点端点 `POST /api/usage`，归到 §7.2 待 ADR-0004 拍板后补到端点表。
- ADR-0001-0005 起草顺序建议：**0001 (LLM 框架) → 0003 (来源) → 0002 (向量库) → 0004 (Web) → 0005 (前端)**。原因：0001 的取舍会反向影响 0003（本地还是远程），二者需在 0002 之前对齐。

## 流程留痕

- Reviewer 本轮（MAQ-7）从"收到任务"到"完成报告 + v0.3 定稿"在 1 轮内完成，启动失败自检正常。
- 上轮（MAQ-5 报告）复盘里提的"spec-review.md 模板待补"，本轮仍未补；下轮可由产品 + Reviewer 联合抽首版（骨架已稳定为八段式）。

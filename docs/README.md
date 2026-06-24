# 文档目录

本目录是 **产品 / 开发 / 审查员 / 环境准备与部署** 四个角色唯一的协作通道。
所有跨角色的信息传递都通过文件提交完成（git 跟踪，multica issue 引用），
不要在 IM/口头里"说完就算"。

## 顶层结构

| 目录 | 负责角色 | 内容 |
|------|---------|------|
| [`product/`](./product/README.md) | 产品 | 需求池、用户故事、产品规格 |
| [`dev/`](./dev/README.md) | 开发 | 设计文档、ADR 实现记录、Runbook |
| [`review/`](./review/README.md) | 审查员 | 审查清单、审查报告、复盘记录 |
| [`envops/`](./envops/README.md) | 环境准备与部署 | 环境说明、部署流程、运维 Runbook |
| [`adr/`](./adr/README.md) | 跨角色 | Architecture Decision Records（一旦写定全员遵循） |
| [`handoffs/`](./handoffs/README.md) | 跨角色 | 交接单（谁把什么交给了谁） |
| [`templates/`](./templates/) | — | 各角色产出文档的空白模板 |

## 协作约定

1. **每个交付件都要绑定一个 multica issue**。在文档头部写：
   `multica-issue: MAQ-XX`，没有 issue 不算交付。
2. **交接必须留痕**：当 A 角色把工作交给 B 角色时，在
   `handoffs/YYYY-MM-DD-from-A-to-B.md` 写一张交接单（用
   [`templates/handoff.md`](./templates/handoff.md)）。
3. **状态变化都进 git**：每个交付件要么 PR 合入，要么不进。任何"还在飞"
   的内容都应该挂在 issue 而不是 main 分支。
4. **冲突先 ADR 后实现**：架构层分歧先在 `adr/` 写 ADR 决议，再写代码。
5. **审查必须留报告**：每次审查（含自审）都要在
   `review/reports/` 留一份 PDF/MD，否则不算完成。

## 当前活跃交付件

> TODO(产品): 把第一条 MAQ-6 → MAQ-7 的子 issue 填到这里。

| Issue | 标题 | 负责角色 | 文档入口 |
|-------|------|---------|----------|
| MAQ-6 | 知识库 rag 项目环境准备 | 环境准备与部署 | [`envops/environments.md`](./envops/environments.md) |
# 审查员 (Review)

> 负责角色：审查员
> 产出节奏：每次合入前一份清单 + 一份报告

## 这里放什么

- `checklists/` — 各类审查的清单模板（code review / spec review / security / 等）
- `reports/YYYY-MM-DD-<topic>.md` — 实际审查报告（每次都留档）

## 不放什么

- 设计文档（→ `dev/design.md`）
- 产品需求（→ `product/specs/`）
- 环境配置（→ `envops/`）

## 与其他角色的接口

- 开发提 PR → 审查员跑 [`checklists/code-review.md`](./checklists/code-review.md)
- 产品交 spec → 审查员跑 `checklists/spec-review.md`（待补）
- 任何角色提架构级变更 → 审查员先审 ADR 再审实现

## 审查流程

1. 接收 PR / spec
2. 复制对应 checklist 到 `reports/`，逐项打勾
3. 阻塞项 → 在 PR 评论里写明，不通过
4. 通过 → 在 multica issue 上贴报告链接 + 给 "approved"
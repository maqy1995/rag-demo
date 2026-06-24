# 产品 (Product)

> 负责角色：产品
> 产出节奏：每个 sprint 一份 `spec.md` + 持续维护的 `backlog.md`

## 这里放什么

- `backlog.md` — 活跃的需求池（按优先级排序，每条带 multica issue ID）
- `specs/<issue-id>-<slug>.md` — 具体需求的完整规格（用
  [`templates/product-spec.md`](../templates/product-spec.md) 起稿）
- `roadmap.md` — 长期路线图（季度/月度都可）
- `research/`（可选）— 用户访谈、竞品分析

## 不放什么

- 技术实现细节（→ `dev/design.md`）
- 部署/环境细节（→ `envops/environments.md`）
- 审查意见（→ `review/reports/`）

## 与其他角色的接口

- 产品产出 `spec.md` → 交接给 开发（[`handoffs/`](../handoffs/README.md)）
- 审查员可能对 `spec.md` 提出反馈 → 产品修订 → 重新交接
- 环境准备与部署对部署可行性提出约束 → 产品记录到 `spec.md` 的"约束"小节

## 当前 backlog

> 见 [`backlog.md`](./backlog.md)
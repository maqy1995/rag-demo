# 开发 (Development)

> 负责角色：开发
> 产出节奏：每个功能一个 `design.md` 分支，合入前由审查员 review

## 这里放什么

- `design.md` — 当前模块的总体设计（架构、数据流、关键决策）
- `adr-notes/` — 对 `docs/adr/` 中决议的实现笔记（哪一段代码对应哪条 ADR）
- `runbooks/` — 日常开发/调试的步骤（如何跑测试、如何加新依赖、如何本地起 demo）
- `interfaces.md` — 模块对外接口约定（CLI、Python API、HTTP）

## 不放什么

- 产品需求（→ `product/specs/`）
- 审查报告（→ `review/reports/`）
- 环境/部署（→ `envops/`）

## 与其他角色的接口

- 收到产品 `spec.md` → 写 `design.md` → 提交 PR
- 提交 PR 时 @审查员（在 multica 评论里 mention），并附 `review/checklists/code-review.md`
- 实现过程中如果发现架构级问题 → 在 `adr/` 起草 ADR → @产品/审查员/环境运维确认

## 入门指引

```bash
# 1) 克隆仓库后第一次设置
uv sync --extra dev

# 2) 跑烟雾测试
uv run pytest -q

# 3) 起 demo doctor
uv run rag-demo doctor
```

详见 [`runbooks/local-dev.md`](./runbooks/local-dev.md)。
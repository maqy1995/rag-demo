# 环境准备与部署 (EnvOps)

> 负责角色：环境准备与部署
> 产出节奏：环境配置变更 → 同步修订 `environments.md`；每次部署 → 留 `runbook.md` 记录

## 这里放什么

- `environments.md` — 三个环境的固定说明：dev / staging / prod
  （账号、域名、限制、注意事项）
- `deployment.md` — 部署流程（前置、步骤、回滚）
- `runbook.md` — 故障排查（症状 → 排查 → 修复）
- `secrets/` 模板（**只放示例，不放真值**）

## 不放什么

- 代码逻辑（→ `dev/design.md`）
- 产品需求（→ `product/`）
- 审查报告（→ `review/reports/`）

## 与其他角色的接口

- 收到开发"需要新环境/新凭据"的请求 → 在 `environments.md` 加条目
- 部署完成后 → 在 `runbook.md` 记一行时间戳 + 版本号 + 结果
- 任何环境故障 → 在 `runbook.md` 记一行故障 + 根因 + 修复

## 本机开发环境（绑定到 multica）

multica 项目 `知识库问答`（id `7d66ac3d-94eb-4328-8b81-3cbf39c47973`）已绑定：

- `local_directory` → `~/Code/rag-demo`
- `github_repo` → `https://github.com/maqy1995/rag-demo`（推送后）

未来开在 `知识库问答` 项目下的 issue 会自动注入这两个资源作为上下文。
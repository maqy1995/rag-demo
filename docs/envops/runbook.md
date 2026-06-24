# 故障排查 Runbook

> 维护者：环境准备与部署
> 每行一条记录，按时间倒序

| 时间 (UTC+8) | 症状 | 根因 | 修复 | 关联 issue |
|--------------|------|------|------|------------|
| 2026-06-24 | `uv sync` 第一次跑失败：`host unreachable` | `uv` 没读 git 的 `http.proxy`，直连 PyPI 被防火墙拦 | 新建 `~/.config/uv/uv.toml` 加 `http-proxy` / `https-proxy` | MAQ-6 |
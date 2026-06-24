# 环境清单

> 维护者：环境准备与部署
> multica-issue: MAQ-6

## 本机 (developer)

| 项 | 值 |
|----|----|
| 路径 | `~/Code/rag-demo` |
| Python | uv-managed 3.12（`~/.local/share/uv/python/`） |
| 虚拟环境 | `.venv/`（与全局隔离） |
| 代理 | `http://127.0.0.1:7897`（git + uv 都走它） |
| 多 agent 入口 | Claude Code / Codex CLI / multica CLI |

> ⚠️ **不要用 `miniconda3/bin/python3` 或 `/usr/bin/python3` 直接跑项目**。
> 任何 IDE 集成（VS Code / Cursor / PyCharm）请把 interpreter 指向
> `~/Code/rag-demo/.venv/bin/python`。

## staging（待开）

（暂无）

## prod（待开）

（暂无）
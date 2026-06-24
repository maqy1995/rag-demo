# rag-demo

> **位置**：`~/Code/rag-demo`（macOS 本地，IDE 可直接打开）
> **GitHub**：`https://github.com/maqy1995/rag-demo`（推送后）
> **Multica 项目**：`知识库问答` (`7d66ac3d-94eb-4328-8b81-3cbf39c47973`)

A small Retrieval-Augmented Generation demo, designed to be built and
extended through a **Multica + Claude Code + Codex** workflow with
**4 个角色**：产品 / 开发 / 审查员 / 环境准备与部署 —— 协作通道见 `docs/`。

The repository is a skeleton: the CLI works end-to-end with stub
implementations, so the multi-agent wiring can be exercised before
plugging in a real vector store and LLM.

## Layout

```
rag-demo/
├── pyproject.toml           # uv-managed; extras for LangChain / LlamaIndex / FAISS / Chroma
├── .python-version          # 3.12
├── .env.example             # copy to .env and fill in API keys
├── src/rag_demo/            # 三段式 pipeline: ingest / retrieve / generate (stub)
├── tests/test_smoke.py      # 2 passed
├── data/{raw,index}/        # 知识库 + 索引
├── docs/
│   ├── README.md            # 文档总览 + 协作约定
│   ├── product/             # 产品：backlog + spec
│   ├── dev/                 # 开发：design + runbooks
│   ├── review/              # 审查员：checklists + reports
│   ├── envops/              # 环境准备与部署：environments + deployment + runbook
│   ├── adr/                 # 跨角色架构决策记录
│   ├── handoffs/            # 跨角色交接单
│   ├── templates/           # 空白模板
│   ├── architecture.md      # pipeline 流程图
│   └── github-setup.md      # 三种推到 GitHub 的方法
└── scripts/doctor.sh
```

## Quick start

```bash
cd ~/Code/rag-demo

# 0) 一次性：装 uv-managed Python 3.12（与系统/conda 解释器完全隔离）
uv python install 3.12
uv sync --extra dev

# 1) 烟雾测试
uv run pytest -q

# 2) 看环境诊断
uv run rag-demo doctor

# 3) 灌数据 + 提问（stub 阶段）
uv run rag-demo ingest
uv run rag-demo ask "What is in the knowledge base?"
```

> **关于 Python 环境**：本项目只用 **uv 管理的 CPython 3.12.13**
> （`~/.local/share/uv/python/`），`.venv/` 是基于它的独立虚拟环境。
> **不依赖** `/usr/bin/python3` 或 `miniconda3/bin/python3`，不会污染你的
> 其他 Python 工程。IDE（VS Code / Cursor / PyCharm）请把 interpreter
> 指向 `~/Code/rag-demo/.venv/bin/python`。

## 四个角色 + 协作通道

| 角色 | 写 | 读 | 主要入口 |
|------|----|----|---------|
| 产品 | `docs/product/specs/`, `docs/product/backlog.md` | `docs/adr/` | [`docs/product/README.md`](./docs/product/README.md) |
| 开发 | `docs/dev/design.md`, `docs/dev/runbooks/`, 代码 | `docs/product/specs/`, `docs/adr/` | [`docs/dev/README.md`](./docs/dev/README.md) |
| 审查员 | `docs/review/reports/` | 全部 PR + spec + ADR | [`docs/review/README.md`](./docs/review/README.md) |
| 环境准备与部署 | `docs/envops/`, handoff 单 | 全部 | [`docs/envops/README.md`](./docs/envops/README.md) |

跨角色交接：`docs/handoffs/<date>-from-A-to-B-<slug>.md`。
架构分歧：`docs/adr/NNNN-<slug>.md`（一旦 `Accepted` 全员遵循）。

详见 [`docs/README.md`](./docs/README.md)。

## Picking a real stack

`docs/product/backlog.md` 里挂着"选 LLM 框架"和"选向量库"两个待办 issue，
由开发角色开 ADR 决策后替换 stub。候选 extras：

| Need                 | Extra              | 安装命令 |
|----------------------|--------------------|---------|
| LangChain + OpenAI   | `langchain openai` | `uv sync --extra langchain --extra openai` |
| LlamaIndex + OpenAI  | `llamaindex openai`| `uv sync --extra llamaindex --extra openai` |
| FAISS 向量库         | `faiss`            | `uv sync --extra faiss` |
| Chroma 向量库        | `chroma`           | `uv sync --extra chroma` |

替换时函数签名不变（`ingest_directory` / `retrieve` / `answer`），CLI 不动。

## Multi-agent workflow

- **Claude Code** 在 multica workspace 跑，负责计划 / 审查 / 协调。
- **Codex CLI** 在同一仓库内执行实现：`codex exec "<task>"`。
- **Multica** 是 durable record。本仓库已通过 `multica project resource add`
  绑到 `知识库问答` 项目下，未来开在该项目的 issue 会自动注入路径与
  （推送后的）GitHub URL 作为上下文。

## 推到 GitHub（Plan A）

```bash
# 1) 一次性认证（用户在自己终端跑，30 秒）
gh auth login

# 2) 创建仓库并推送（我会在用户认证后跑这条）
gh repo create maqy1995/rag-demo --public --source=. --remote=origin --push
```

详细步骤见 [`docs/github-setup.md`](./docs/github-setup.md)。
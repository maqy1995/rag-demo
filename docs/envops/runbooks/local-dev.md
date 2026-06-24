# 本地开发工作流（multica + GitHub）

> 维护者：环境准备与部署
> 适用：所有参与 `知识库问答` 项目（id `7d66ac3d-94eb-4328-8b81-3cbf39c47973`）的本机开发
> 目的：把"项目资源" / "本地代码" / "GitHub 远端" 三者的关系讲清楚，让接手的人 5 分钟跑通

## 1. 三者的关系（一图）

```
┌──────────────────────────────────────────────────────────────────┐
│  本机 (macOS)                                                     │
│                                                                  │
│  ~/Code/rag-demo/          ← local_directory 资源 336f0efe-…    │
│  │  ├── .venv/             (uv-managed 3.12，不进 git)            │
│  │  ├── src/rag_demo/                                            │
│  │  ├── tests/                                                    │
│  │  ├── docs/                                                     │
│  │  └── pyproject.toml                                            │
│  │                                                               │
│  ├── git remote origin → https://github.com/maqy1995/rag-demo    │
│  │                       (github_repo 资源 731b588e-…)            │
│  │                                                               │
│  ├── ~/.local/bin/multica  (symlink → Multica.app/.../multica)   │
│  │                                                               │
│  └── ~/Library/Keychains/login.keychain-db                        │
│      └─ github.com → PAT (gh auth login 后写入)                   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  multica CLI 走 HTTPS API
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Multica Cloud (multica.ai)                                       │
│  workspace ab0c0808-… → project 7d66ac3d-…「知识库问答」         │
│  resources:                                                       │
│    • local_directory  336f0efe-d44d-4f68-889b-5712c2ccaa4b       │
│    • github_repo      731b588e-5e1f-48c4-b916-a95cae1fc92c       │
└──────────────────────────────────────────────────────────────────┘
```

**关键事实**：
- local_directory 资源的"生效范围"= multica agent 启动时把 `~/Code/rag-demo` 作为 cwd，并把这份资源写进 `.multica/project/resources.json`。
- github_repo 资源 = "告诉 multica 哪个远端仓库属于这个项目"，**不会**自动同步代码，纯粹是上下文注入。
- 两者配合：开在「知识库问答」项目下的 issue，agent 一启动就同时看到本机路径和远端 URL，不用每次手填。

## 2. 首次接入本项目（30 分钟 checklist）

按顺序跑，**别跳**：

| 步 | 动作 | 验证 | 不通过怎么办 |
|----|------|------|-------------|
| 1 | `which multica && multica --version` | 看到 `v0.3.x` | 没有 → 见 §5 重做 symlink |
| 2 | `multica project resource list 7d66ac3d-94eb-4328-8b81-3cbf39c47973` | 看到 local_directory + github_repo 两条 | 没有 → 让 envops 重绑（`multica project resource add`） |
| 3 | `gh auth status` | `Logged in to github.com as <你的账号>` | 没有 → `gh auth login --hostname github.com --git-protocol https --web` |
| 4 | `cd ~/Code/rag-demo && uv sync --extra dev` | `.venv/` 重建完成 | 失败看 `~/.config/uv/uv.toml` 是否带 `http-proxy` |
| 5 | `uv run --extra dev pytest -q` | `2 passed` | 看 `tests/test_smoke.py` 期望 |
| 6 | `uv run --extra dev python -m rag_demo doctor` | 输出 `git / uv / codex / claude / multica 均就绪` | 哪行 unset 就去 §5 找对应工具的补装方式 |
| 7 | `git remote -v` | 看到 `https://github.com/maqy1995/rag-demo.git` | 是 SSH → `git remote set-url origin https://github.com/maqy1995/rag-demo.git` |

> 如果是 IDE 集成：把 interpreter 指向 `~/Code/rag-demo/.venv/bin/python`，
> **不要**用系统 Python 或 miniconda 的 Python。

## 3. 日常开发循环

```
改代码 → uv run --extra dev pytest -q
       → uv run --extra dev python -m rag_demo doctor    # 烟雾检查
       → git add -p && git commit -m "..."
       → git pull --rebase origin main                    # 多人协作时
       → git push origin main
       → multica issue comment add <MAQ-XXX> --content-file ./note.md
```

- 本地 commit 不需要开 issue 审批，但**驱动功能改动的 commit 应该在 multica issue 上留一条链接**（`#12` 形式），让产品/审查员能顺着 issue 看代码。
- `main` 分支受保护程度 = 自由推送（demo 阶段），等 staging/prod 起来后改 PR 流程。

## 4. 多人协作 / 多人本机

- **不要**把 `~/Code/rag-demo/.agent_context/` 提交 —— 那是 agent 启动时生成的 per-run scratchpad，绑了 daemon id 和 issue id，换台机器就失效。
- **不要**把 `~/.local/bin/multica` 的 symlink 同步到同事机器上 —— 路径跟本机 `/Applications/Multica.app` 装的位置有关，换人就要重做 §5。
- local_directory 资源的 `daemon_id` (`019eee4a-9dff-783d-9c56-675c1d50a286`) 是本机 daemon 的 id，**别复制**。每台机器跑 `multica daemon start` 后会生成自己的。

## 5. 故障速查

| 症状 | 根因 | 修复 |
|------|------|------|
| `multica: command not found` | Desktop 安装的 CLI 在 asar 内部，PATH 没有 | `ln -sf /Applications/Multica.app/Contents/Resources/app.asar.unpacked/resources/bin/multica ~/.local/bin/multica`，然后开新终端 |
| `gh: not logged in` | keychain 没存 PAT | `gh auth login --hostname github.com --git-protocol https --web` |
| `git push` 报 `Connection reset by peer` port 22 | 默认走 SSH 但无 `~/.ssh` | `gh auth setup-git && git remote set-url origin https://github.com/maqy1995/rag-demo.git` |
| `uv sync` 报 `host unreachable` | uv 不读 git 的 `http.proxy` | `~/.config/uv/uv.toml` 加 `http-proxy = "http://127.0.0.1:7897"` / `https-proxy` |
| multica 项目页看不到 local_directory 资源 | UI 缓存 / 切错项目 | ⌘⇧R 强刷；用 `multica project list` 确认 project id |
| `python -m rag_demo doctor` 报 Python 解释器是 conda/system | IDE/Shell 切错了 | 改用 `~/Code/rag-demo/.venv/bin/python` |

## 6. 资源绑定 CLI 一览（envops 备用）

```bash
# 看现状
multica project resource list 7d66ac3d-94eb-4328-8b81-3cbf39c47973 --full-id

# 解绑（不会删文件/仓库，只解除 multica 上下文）
multica project resource remove 7d66ac3d-94eb-4328-8b81-3cbf39c47973 \
  --resource-id 336f0efe-d44d-4f68-889b-5712c2ccaa4b

# 重新绑 local_directory（路径变了 / 换台机时）
multica project resource add 7d66ac3d-94eb-4328-8b81-3cbf39c47973 \
  --type local_directory --path ~/Code/rag-demo \
  --label "rag-demo dev directory (~/Code/rag-demo)"

# 重新绑 github_repo
multica project resource add 7d66ac3d-94eb-4328-8b81-3cbf39c47973 \
  --type github_repo --url https://github.com/maqy1995/rag-demo \
  --default-branch-hint main
```

> resource id 不是秘密，但 `daemon_id` 是 per-machine 的，不要复用到另一台机器上。

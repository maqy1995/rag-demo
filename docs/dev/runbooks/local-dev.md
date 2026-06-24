# 本地开发 Runbook

> 维护者：开发
> 适用：所有角色本地 clone 后第一次跑起来

## 0. 前置依赖

- macOS / Linux
- [`uv`](https://docs.astral.sh/uv/) ≥ 0.4
- git ≥ 2.30
- Python 3.12（**不要装到系统**：uv 会自带 managed 解释器）

> 本仓库使用 **uv 管理的 Python**（`uv python install 3.12` 下载到
> `~/.local/share/uv/python/`），完全不依赖 `/usr/bin/python3` 或
> `miniconda3` 的解释器。`.venv/` 是独立虚拟环境，与全局 Python 隔离。

## 1. 第一次拉取代码

```bash
cd ~/Code/rag-demo
uv python install 3.12        # 一次性
uv sync --extra dev           # 创建 .venv/ 并装依赖
```

## 2. 跑测试

```bash
# 从项目根目录跑（推荐）
uv run pytest -q

# 或者从任意目录跑（agent 场景下用得多）
uv run --directory ~/Code/rag-demo --extra dev pytest -q
```

## 3. 看环境诊断

```bash
uv run --directory ~/Code/rag-demo rag-demo doctor
```

应输出：
- 所有工具路径
- 三个 env key 的 set/unset 状态（首次均 unset，正常）

## 4. 加新依赖

```bash
uv add requests               # 运行时
uv add --dev ruff             # 仅开发
```

`pyproject.toml` 与 `uv.lock` 都会同步更新，**`uv.lock` 必须提交**。

## 5. 替换 stub

`src/rag_demo/{ingest,retrieve,generate}.py` 三个文件的函数签名是契约。
替换实现时：

1. 函数名与参数保持不变。
2. 新增环境变量请同步更新 `.env.example`。
3. 在 `tests/` 加至少一个测试。
4. 在 `docs/adr/` 写一张 ADR 说明为什么这样选。
# 审查报告 — MAQ-46 冷启动空索引修复

> multica-issue: MAQ-46
> 审查员：Reviewer (`e57a9ea0…`)
> 被审材料：PR #3 `fix/maq-46-empty-data-fallback`，commit `cd57d2d`
> 依据：design v1.1 §3.2（NB3 cold-start fallback 契约） + 仓库协作约定
> 日期：2026-06-25
> 结论：**Pass (Approved with comments)** —— 修复正确、最小、目标明确；4 条意见里 1 条 minor 测试覆盖缺口、1 条项目级（无 CI）、2 条 out-of-scope 的同模式 hint（按要求仅列在报告里，不阻塞本 PR）。

---

## 0. 审查依据 & 工具

- **本轮范围**：PR #3 的全部改动（2 个文件、+26 / -2 行）
  - `src/rag_demo/ingest.py` —— NB3 fallback 的"空判定"加 dotfile 过滤
  - `tests/test_ingest.py` —— 新增 `test_ingest_dir_with_only_dotfiles_falls_back`
- **测试基线**：`uv run pytest -q` → **146 passed, 5 deselected in 10.49s**（本分支）
- **Linter**：`uv run ruff check src/rag_demo/ingest.py tests/test_ingest.py` → **All checks passed!**
- **手动验证**：跑了一个 4 场景的 ad-hoc 脚本（real+dotfile / .DS_Store+md / .env+md / 纯 .gitkeep）→ 4/4 通过
- **PR 状态**：`mergeable=MERGEABLE`，`statusCheckRollup=[]`（详见 §4）

---

## §1 — 改动面审查（review item 1）

`src/rag_demo/ingest.py:103-112`，改动 diff：

```diff
-    if not data_dir.exists() or not any(data_dir.iterdir()):
-        if _SAMPLE_DATA_DIR.exists() and any(_SAMPLE_DATA_DIR.iterdir()):
+    # 忽略 dotfile (e.g. .gitkeep) — git 占位文件不算"内容".
+    if not data_dir.exists() or not any(
+        p for p in data_dir.iterdir() if not p.name.startswith(".")
+    ):
+        if _SAMPLE_DATA_DIR.exists() and any(
+            p for p in _SAMPLE_DATA_DIR.iterdir() if not p.name.startswith(".")
+        ):
             data_dir = _SAMPLE_DATA_DIR
```

**结论：改动最小且目标明确。**

- 改动**只在 NB3 "is empty" 判定**这一处（共 2 个 `iterdir()` 调用：外层 `data_dir`、内层 `_SAMPLE_DATA_DIR`，**两处都加了同一条 dotfile 过滤**——一致）。
- 后续真正的"文件扫描"在第 124-125 行：
  ```python
  files = sorted(
      p for p in data_dir.rglob("*")
      if p.is_file() and p.suffix in {".md", ".txt", ".rst"}
  )
  ```
  `p.suffix` 已经把 `.gitkeep` / `.DS_Store` / `.env` 这类 dotfile 排除在外，**所以即便 dotfile 漏过 empty 判定也不会被 ingest**。dotfile 过滤只影响"fallback 与否"的决策路径，不影响 ingest 的内容选择。
- **`.md` / `.txt` / `.rst` 真实文件**不受任何影响（dotfile 过滤只发生在 iterdir 层；rglob 层用 suffix 过滤）。
- `rglob` 会走进子目录；理论上如果用户目录是 `data/.vscode/foo.md` 这种纯 dotfile 目录，会触发 fallback——这与"vault 实际无内容"的语义一致，符合 design §3.2 的 NB3 契约（"当 `vault.path` 为空时"），**可以接受**。

---

## §2 — 测试覆盖审查（review item 2）

### 2.1 新增测试是否真覆盖 `.gitkeep` 场景

`tests/test_ingest.py:130-148`：

```python
def test_ingest_dir_with_only_dotfiles_falls_back(tmp_path: Path) -> None:
    data = tmp_path / "raw_with_gitkeep"
    data.mkdir()
    (data / ".gitkeep").write_text("", encoding="utf-8")
    stats = ingest_directory(data, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total >= 1, (
        f"expected fallback to raw.sample, got files_total={stats.files_total}"
    )
```

**结论：覆盖了 `.gitkeep` 占位场景。**

- 精确还原了生产 bug 的复现路径：仓库刚 clone、`data/raw/` 只有 `.gitkeep`。
- 断言用 `files_total >= 1` 而不是 `== N`，避免对 `data/raw.sample/` 内部结构耦合（其他测试也用同样模式，**风格一致**）。
- 在本机跑 → PASS（`tests/test_ingest.py::test_ingest_dir_with_only_dotfiles_falls_back PASSED [87%]`）。

### 2.2 回归用例：用户已有真实文件 + 同目录还有 dotfile

**结论：Minor 缺口（不阻塞）。** 现有 8 个 ingest 测试**没有任何一个**专门覆盖"`data/foo.md + data/.gitkeep`"或"`data/*.md + data/.DS_Store`"这种"真实文件 + dotfile 共存"的场景。

- `test_ingest_basic` —— 只放 1 个 `.md`，无 dotfile
- `test_ingest_state_flips_building_then_idle` / `test_ingest_status_written_while_building` —— 多个 `.md`，无 dotfile
- `test_ingest_empty_data_dir_falls_back` —— 目录**完全空**（既无 dotfile 也无真实文件）
- `test_ingest_dir_with_only_dotfiles_falls_back` —— 目录**只有 dotfile**

也就是说，本 PR 的 dotfile 过滤如果未来被误改回"全过滤掉"或者"全保留"，**测试套件是抓不到的**——只有当目录是"纯 dotfile"或"纯空"时，行为才会分化；混合场景下两种实现都会过。

**我手动跑了 4 场景的 ad-hoc 验证**（real+dotfile / .DS_Store+md / .env+md / 纯 .gitkeep），结果均符合预期（`files_total=1` 不走 fallback；纯 dotfile 走 fallback）。**当前实现是对的**，但缺少一条把这个正确性钉死的断言。

**建议（不阻塞本 PR）**：在 `tests/test_ingest.py` 加一条：

```python
def test_ingest_dir_with_real_files_and_dotfile_does_not_fall_back(tmp_path: Path) -> None:
    """回归 (MAQ-46 follow-up): 真实 .md + dotfile 共存 → 走 ingest，不走 fallback."""
    data = tmp_path / "raw"
    data.mkdir()
    (data / "real.md").write_text("hello world " * 30, encoding="utf-8")
    (data / ".gitkeep").write_text("", encoding="utf-8")
    stats = ingest_directory(data, tmp_path / "index")
    assert stats.state == "idle"
    assert stats.files_total == 1
    assert stats.chunks_total >= 1
```

可以放在 `test_ingest_dir_with_only_dotfiles_falls_back` 之后，作为"对照组"。

---

## §3 — 同模式扫雷（review item 3）

`rg -n "iterdir\\(|os\\.listdir|listdir" --type py`（排除 tests 内部）扫描结果：

| 位置 | 状态 | 影响 | 是否阻塞 |
|------|------|------|----------|
| `src/rag_demo/ingest.py:108` | 本 PR 已修 | 主路径，已修复 | — |
| `src/rag_demo/ingest.py:111` | 本 PR 已修 | `_SAMPLE_DATA_DIR` 判定，已修复 | — |
| `scripts/build_sample_index.py:29` | 未修（同模式） | dev 脚本，guard `data/raw.sample/` 是否存在内容；当前 sample 只有 5 个 `.md` 无 dotfile，**没出 bug**；但若 sample 未来加了 `.gitkeep` 之类的占位，会被误判为"未 provisioning" 而打印 `❌ data_dir missing or empty` | 否（out-of-scope，本 PR 不动） |
| `tests/test_ingest.py:110, 122, 138` | 未修（同模式） | `pytest.skip` guard，同样判 `_SAMPLE_DATA_DIR` 是否"非空"；同样要 sample 出现 dotfile 才会"假阳性 skip"。当前 sample 是干净的，**没出 bug** | 否（out-of-scope） |

**结论：仓库内 `iterdir` 仅 1 处生产热路径（`ingest.py`）和 1 处 dev 脚本（`build_sample_index.py`）+ 3 处 test guard。本 PR 修对了"主病灶"；其余 2 处属于同模式 hint，按 review item 3 的要求**单列在报告里，不在本 PR 范围**。**

注：`src/rag_demo/ingest.py:124` 的 `rglob("*")` + `p.suffix` 过滤**不**属于此类风险（用 suffix 限定，不依赖"是否空"判定）。

---

## §4 — CI 状态（review item 4）

**结论：仓库目前没有 CI，无法验证 PR 上的 CI 是否全绿。**

- `gh pr checks 3` → `no checks reported on the 'fix/maq-46-empty-data-fallback' branch`
- `gh pr view 3 --json statusCheckRollup` → `[]`（空数组）
- 仓库内**没有** `.github/workflows/` 目录（`ls .github/workflows/` → No such file or directory）
- `pyproject.toml` 也没声明任何 CI marker / hatch 任务

**这是一个项目级缺口，不是本 PR 的问题。** PR 本身 `mergeable=MERGEABLE`，无 merge conflict；本机 `uv run pytest -q` → **146 passed, 5 deselected**（5 个 e2e 默认 deselect，不是回归）；`ruff check` → 0 errors。**等同于"手动跑过 CI"**。

**项目级 follow-up（不阻塞本 PR）**：建议产品/环境运维后续排期起一份最小 CI（lint + pytest + 矩阵 Python 3.12），避免以后 PR 改不出 unit test 也能合入。详见 MAQ-43 final review §B 的"流程问题"。

---

## §5 — 整体结论

| 项 | 状态 | 备注 |
|----|------|------|
| 改动面（§1） | Pass | 最小、目标明确、不影响真实 `.md/.txt/.rst` 摄入 |
| 测试覆盖（§2） | Pass with minor | 主场景覆盖；缺一条混合场景回归用例（已给代码建议） |
| 同模式扫雷（§3） | Pass | 主路径已修；2 处 out-of-scope 已列 |
| CI（§4） | N/A | 仓库无 CI；本机 146/146 pytest + ruff 0 errors 等同通过 |

**最终结论：Pass (Approved with comments)。**

- 本 PR **可以合入 main**。
- 合入后建议立刻补 §2.2 那条"混合场景"回归测试（dev 在本 PR 后续 commit 补即可，不必再开一轮 review——一条 8 行测试，属于本 PR 范围"自然延伸"）。
- §3 的 2 处 out-of-scope + §4 的"无 CI"另开 follow-up issue（建议一个 MAQ-47 之类），不阻塞当前 PR。

---

## 附录 A — 复盘

- **改动量** +26 / -2 行，**极其小**——按"非破坏性 in-line 修复"流程可以直接合入，不需要再开一轮 review。
- **审查强度**：4 个 item 全部跑过；2 处需要复盘（§2.2 测试缺口、§4 无 CI），均非 PR 阻塞。
- **流程观察**：`data/raw/` 留 0 字节 `.gitkeep` 的设计本身没问题（确保 git clone 后 `data/raw/` 这个目录存在），但**没有"git-friendly placeholder 不算内容"的协议**——这是 NB3 契约的隐含漏洞。design §3.2 可以加一句"dotfile 不算 vault content"作为正式契约，避免未来再被踩。
- **审查清单 v0.2 候选**：把"`iterdir()` 空判定 + 是否考虑 dotfile / 隐藏文件"加入必查项。

## 附录 B — 跨文档引用

- 本轮 review（本报告）：[docs/review/reports/2026-06-25-MAQ-46-code-review.md](./2026-06-25-MAQ-46-code-review.md)
- 被审 PR：https://github.com/maqy1995/rag-demo/pull/3
- 上轮 final review：[docs/review/reports/2026-06-25-MAQ-43-final-review.md](./2026-06-25-MAQ-43-final-review.md)
- 设计（v1.1，NB3 fallback 契约 §3.2）：[docs/dev/design.md](../dev/design.md)
- 触发 issue：MAQ-46

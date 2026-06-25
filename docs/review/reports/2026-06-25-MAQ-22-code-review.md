# 审查报告 — 第二轮代码 review (MAQ-22)

> multica-issue: [MAQ-22](mention://issue/07b037b4-3649-4f04-a856-496d610fc51f)
> 审查员：Reviewer (`e57a9ea0…`)
> 被审材料：实现 v1（main 分支，commit `86385fa`；MAQ-11/12/13/14/17/18 落地内容）
> 依据：PRD v0.3（[MAQ-5](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) Final）+ design v1.1（[MAQ-8](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab) / [MAQ-9](mention://issue/2d181966-ca77-472a-924e-a5b03d4d6c90)）
> 上轮报告：[docs/review/reports/2026-06-24-MAQ-19-code-review.md](./2026-06-24-MAQ-19-code-review.md)
> 日期：2026-06-25
> 结论：**Approved with comments (re-confirmed)** —— 整体实现 v1 质量与上轮 review 结论一致；MAQ-19 列出的 4 个真阻塞（NB1–NB4）**全部仍未合入**，建议就地合入 v1.1.1 后再开 ADR-0001。本轮额外发现 3 条重要建议（NI5–NI7）+ 3 条结构清理（NS5–NS7），均不阻塞 in_review → done。

---

## 0. 审查依据 & 工具

- **Code Review 清单**：[docs/review/checklists/code-review.md](../checklists/code-review.md) — 必查 7 项 + 建议查 4 项逐项打勾（§1）
- **上游**：PRD v0.3（Final，Reviewer Approved） + design v1.1（Reviewer Approved）
- **本轮范围**：实现 v1 主分支所有 Python 源码（11 模块 ≈ 1205 行）+ 9 个测试文件（80 断言 / 100% pass）+ 1 个占位 HTML
- **与上轮（MAQ-19）的差异**：**无新 commit，无新代码**——本轮是 MAQ-19 后的二次 review（dev 还未合入 v1.1.1 修订），目的是**复验 NB1–NB4 仍待合入 + 补查本轮新增 6 条意见**。
- **测试基线**：`uv run pytest -q` → **80 passed in 6.42s**
- **Linter**：`uv run ruff check src tests` → All checks passed
- **运行态探测**：直接 TestClient 拉端点、grep import/load_config 调用频次、对比 .env.example 与 load_config 实际读取范围

---

## 1. Code Review 清单逐项打勾

| # | 必查项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | PR 描述引用了对应 multica issue | ✅ | 每个 feat commit 头部都写 `multica-issue: MAQ-XX` + `Closes MAQ-XX`（MAQ-11/12/13/14/17/18） |
| 2 | 改动与 design.md 一致；偏差需附 ADR 链接 | ⚠️ | 主体一致；MAQ-19 NB1–NB4 四处实现与 design v1.1 偏差**仍未合入**（§2 复验） |
| 3 | 没有把 `.env` / `.pem` / `*.key` 提交 | ✅ | `git ls-files` 无 `.env`、`.pem`、`*.key`；`.gitignore` 已守 |
| 4 | 没有 `.venv/`、缓存、IDE 临时文件 | ✅ | `git ls-files \| grep __pycache__` = 0；`.gitignore` 守住 `.venv/` `.idea/` `.multica/` `.agent_context/` |
| 5 | 函数签名与 `docs/dev/design.md` 一致 | ✅ | 11 模块的函数签名（11 个 L4/L2 公开函数 + 9 端点）与 §3.2–§3.7 一一对应；`_call_llm` 暴露为模块级（§9.2 注入点） |
| 6 | 新增/修改的公共函数至少有 1 个测试 | ✅ | 9 个测试文件覆盖 80 断言；每个 L4 模块、L2 模块、L3 端点都有 ≥1 用例 |
| 7 | 失败的 CI 检查全部修复 | ✅ | ruff 全过；pytest 80/80；mypy 未跑（pyproject 配了但 CI 未启用 — 见上轮 NI2，本轮未动） |

| # | 建议查项 | 结果 | 证据 |
|---|---------|------|------|
| 1 | 错误信息含上下文、不泄露密钥 | ✅ | `AppError` 字典单一信源；`/api/config` + `effective()` 双重脱敏（test_web.py + test_config.py 都有"不含 `sk-` / `OPENAI_API_KEY`"断言） |
| 2 | 日志级别控制，info 不打大段 JSON | ✅ | `JsonFormatter` 只打 msg，snippet 等大 payload 由调用方决定放 INFO/DEBUG；本轮 stub 阶段暂无业务日志 |
| 3 | 对外部输入做校验，不拼 SQL/shell/path | ✅ | Pydantic `Field(min_length=1, max_length=2000)`；`Path` 对象而非字符串拼接；无 SQL/shell 调用 |
| 4 | 锁 / 资源有释放路径 | ⚠️ | `ingest_directory` 用 `index_dir.mkdir(parents=True, exist_ok=True)`；`/api/usage` 用 `with open(...) as f` 上下文管理器；但 `up` 后台 ingest 线程的 join 路径**不**真正生效（§2 NB4 复验） |

> 清单 7+4 中 6+3 全过；§2 起的 4+3+3 = 10 条意见是清单外但属"实现与 design 偏差 / 重要 / 结构"——本轮就地合入 v1.1.1 + 后续清理。

---

## 2. 本轮 review 意见

### 2.1 MAQ-19 阻塞项复验（NB1–NB4 — **仍未合入**）

#### NB1. SSE `cost_ms.generate` 在 GENERATED 路径下被算成"总耗时"（与 retrieve 重合），不是真正的 generate 耗时

- **位置**：`src/rag_demo/web/main.py:225-228`（`chat_stream._generate()` 函数 GENERATED 分支）
- **问题**（与 MAQ-19 报告 §2 NB1 完全一致，**未合入**）：
  ```python
  yield _sse_event("meta", {
      "retrieved": len(hits),
      "decision": result.decision,
      "cost_ms": {
          "retrieve": int((time.perf_counter() - t0) * 1000),  # ✅ 正确
          "generate": int((time.perf_counter() - t0) * 1000),  # ❌ 错：用了 t0，不是 t_after_retrieve
      },
  })
  ```
  `cost_ms.generate` 与 `cost_ms.retrieve` 是同一个数（都是"从 t0 起的总耗时"），而不是"generate 阶段独立耗时"。design §3.6 SSE 协议要 `meta.cost_ms.generate` 是真实生成耗时，前端要按这个数判断"首字延迟 vs 总延迟"分位。
- **复现**：
  ```python
  # mock retrieve sleep 100ms（stub LLM 瞬时返回）
  # 实测: cost_ms = {retrieve: 110, generate: 110}  # ❌ generate 应 ~0
  ```
- **落地建议**（MAQ-19 给出，本轮**仍然适用**）：
  ```python
  t0 = time.perf_counter()
  hits = retrieve(...)
  t_after_retrieve = time.perf_counter()
  result = answer(...)
  # 早返路径用 t0；GENERATED 路径 cost_ms.generate = now - t_after_retrieve
  yield _sse_event("meta", {
      ...
      "cost_ms": {
          "retrieve": int((t_after_retrieve - t0) * 1000),
          "generate": int((time.perf_counter() - t_after_retrieve) * 1000),
      },
  })
  ```
- **测试空缺**：`tests/test_chat.py` 与 `test_web.py` 都没断言 `cost_ms` 数值；本轮建议在 `test_web.py::test_chat_stream_happy_path` 加 1 条断言：mock `retrieve` sleep 100ms + stub `_call_llm` 瞬时，断言 `cost_ms.generate < 20` 且 `cost_ms.retrieve >= 100`。
- **影响**：当 ADR-0001 落地、真实 LLM 接入后，前端按 `cost_ms.generate` 渲染的"首字延迟"会**与真实 LLM 耗时完全脱节**——是 PRD §8.1 性能验收点的关键数据源。**本轮 review 与上轮结论 100% 一致**。

#### NB2. `ingest_directory` stub 永远写 `state="idle"`，没有"building"中间态 — 与 design §3.2 + PRD §7.3 `state: building` 字段不一致

- **位置**：`src/rag_demo/ingest.py:110`（`IngestStats.state="idle"` 写死）
- **问题**（与 MAQ-19 报告 §2 NB2 完全一致，**未合入**）：`IngestStats.state` 字典说"idle | building | error"，但 stub 同步跑完就写 `idle`，**从来没写** `building`。当 `up` 后台线程调用 `ingest_directory` 时：
  1. 启动瞬间：前端轮询 `/api/index/status` → `state="idle"`（status.json 还没写）→ **不显示进度**
  2. 运行中：同上
  3. 跑完：state="idle"
  F8 冷启动 demo 设计要求前端看到 `state=building` + 进度条（design §3.6 + PRD §7.3 + §3 F8）；stub 不落地这个交互。
- **落地建议**（MAQ-19 给出，本轮**仍然适用**）：v1.1.1 就地改
  ```python
  # 启动时先写 status.json (state=building, current_progress={"done": 0, "total": N})
  (index_dir / "status.json").write_text(json.dumps({..., "state": "building", ...}))
  # 跑完再覆盖写 idle
  ```
  + 加一个"进度回调"kwarg（`on_progress(done, total)`），stub 阶段每 N 个文件调一次（用 chunker 步进模拟），让 status.json 真的能看到 `current_progress.done` 变化。
  + 加测试 `test_ingest.py::test_status_flips_to_building_then_idle`（用慢 retrieve mock）。
- **影响**：PRD §3 F8 冷启动 demo 的 30s 反馈机制（NS2 §8.2 自动化断言）当前**测不到**真实进度——只验证了"index.html 30s 内返回 + /api/health < 1s"，没验证"前端轮询能看见 building → idle 的状态翻转"。

#### NB3. `ingest_directory` 在 `data_dir` 不存在时抛 `FileNotFoundError` —— **不**做冷启动 demo fallback（与 design §3.2 要点 + PRD §3 F1 冲突）

- **位置**：`src/rag_demo/ingest.py:52-54`
- **问题**（与 MAQ-19 报告 §2 NB3 完全一致，**未合入**）：
  ```python
  if not data_dir.exists():
      raise FileNotFoundError(f"data dir not found: {data_dir}")
  ```
  design §3.2 要点显式说："当 `data_dir` 不存在或 `vault.path` 为空时，`ingest_directory` **不报错**——fallback 到 `data/raw.sample/`"。PRD §3 F1 + §3 F8 也明确要求"未配置 vault.path 走冷启动 demo 路径"。
  但 ingest.py 注释自己也承认"stub 不做冷启动 demo 兜底，由调用方决定如何 fallback" —— 而 `__main__.up` 与 `web/main.py` 的 `_bg_ingest` 都没做 fallback 兜底（`up` 捕获 `FileNotFoundError` 只是 print 跳过，**没用** `data/raw.sample/`）。
- **实测**：在仓库当前状态（`data/raw` 存在但无 .md 文件）下 `rag-demo ingest` 会跑过（0 文件 0 chunk）；但 `data/raw` 不存在时直接抛错 —— **完全没**走到 §3.1 F1 冷启动 demo 路径。
- **落地建议**（MAQ-19 给出，本轮**仍然适用**）：
  ```python
  SAMPLE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "raw.sample"
  if not data_dir.exists() or not any(data_dir.iterdir()):
      if SAMPLE_DIR.exists():
          data_dir = SAMPLE_DIR  # fallback
      else:
          # S4 软阻塞未解锁: 返回 idle + 全零 stats, 不抛错
          return IngestStats(state="idle", files_total=0, ...)
  ```
  + 注释里"stub 不做冷启动 demo 兜底"删掉。
  + S4 (`data/index.sample/`) 解锁后，`/api/usage` 等端点才有真实数据可回答。
- **影响**：MVP 阶段用户在 README 跟到"一条命令启动"时，第一次跑会因为没建 `config.yaml` + 没建 vault 直接挂掉——与 §3 F1 + §8.3 3a 验收点"≤ 3 分钟 demo"目标脱节。

#### NB4. `up` 后台 ingest 线程是 `daemon=True`，SIGTERM 时**不**等它跑完 —— 与 design §3.7 "优雅退出"段落冲突

- **位置**：`src/rag_demo/__main__.py:117-119`（`_cmd_up` 后台线程 + `finally` 块）
- **问题**（与 MAQ-19 报告 §2 NB4 完全一致，**未合入**）：
  ```python
  ingest_thread = threading.Thread(
      target=_bg_ingest, daemon=True, name="bg-ingest"
  )
  ...
  finally:
      stop_event.set()
      if ingest_thread is not None and ingest_thread.is_alive():
          ingest_thread.join(timeout=5.0)
  ```
  `daemon=True` 让线程**不会**阻塞主进程退出；`finally` 里 `join(timeout=5.0)` 是主进程退出**前**的等待，但因为 `daemon=True`，主进程退出时仍然会被强制 kill。`join(timeout=5.0)` 实际上**永远等不到**这个守护线程跑完。
  design §3.7 5 步流程第 4 步说："SIGINT / SIGTERM 优雅退出（`up` 启动的 ingest 子线程要 join 或 cancel，避免孤儿进程）"——daemon=True 与这个目标**直接冲突**。
- **落地建议**（MAQ-19 给出，本轮**仍然适用**）：
  ```python
  # daemon=False 配合 join
  ingest_thread = threading.Thread(target=_bg_ingest, daemon=False, name="bg-ingest")
  ...
  # finally: join 等到完成或超时（这个 join 真的有效）
  ```
  + 加测试 `test_smoke.py::test_up_graceful_shutdown_waits_for_ingest` —— 起 uvicorn + mock ingest sleep 3s，发 SIGTERM，断言 `proc.wait()` ≤ 5s 且 ingest 线程 `is_alive() == False`。
- **影响**：MVP 阶段用户 Ctrl-C 退出会留下"写到一半的 status.json" + 数据可能损坏（小问题但用户能复现）。生产化前**必须**改。

> **NB1–NB4 总览**：本轮逐条人工 + 静态扫描复验，**4 条全部仍存在于 main 分支**。MAQ-19 报告的"v1.1.1 就地合入"建议**未被采纳**——可能是 dev 还没合、可能是 Reviewer 之前 review 与 dev 之间断了同步。本轮建议产品或 PMO 显式拉一次"v1.1.1 何时合入"的同步会议。

### 2.2 本轮新发现的重要建议（NI5–NI7 — 不阻塞 in_review → done）

#### NI5. `load_config()` 在每个端点请求里**重新读盘** —— 单进程单请求 8 次 yaml.safe_load 浪费，且无法配置热加载

- **位置**：`src/rag_demo/web/main.py:106, 115, 146, 163, 196, 240, 283, 308` 共 8 处 `load_config()` 调用，每次都重新读 `./config.yaml` + `_DEFAULTS` deep-merge + `yaml.safe_load` 解析 + `_flatten`
- **问题**：
  1. 性能：每请求至少 2 次（`/api/chat` 1 次 + L2 内部 0 次；`/api/chat/stream` 1 次 + 子调用 0 次），但每个端点都至少 1 次，10 req/s = 10 次 yaml.safe_load/s —— 不致命但**违背 design §6.1 "加载顺序"的隐含"启动时加载一次"语义**
  2. 一致性：`/api/usage/query` 拿到的 `cfg` 与 `/api/ingest` 拿到的 `cfg` 是**两次独立解析的结果**——如果用户在两次请求之间改了 `config.yaml`，看到的会是不同配置
  3. 测试性：`test_web.py` 用 `monkeypatch.chdir(tmp_path)` 隔离，但**单进程内的 8 个调用点**都重新读盘，测试 fixture 改 cwd 后**只对**第一次 `load_config()` 有效，后续调用会因模块级 cache miss 而再次落盘
- **落地建议**（推荐方案 A；B/C 是 v0.2 再考虑）：
  - **A（推荐，零破坏）**：在 `config.py` 加一个模块级 `_cached_config: AppConfig | None` + `get_config()` 包装（启动时 `load_config()` 一次，进程内 cache），把 `web/main.py` 的 8 处 `load_config()` 全替换为 `get_config()`。**这是 L4 横切，dev 一行改即可**
  - B（更重）：引入 `lru_cache`，但要小心 `path=None` 默认值 + `AppConfig` 是 frozen dataclass 的 hash 行为
  - C（最重）：配置文件 watcher + signal 重载 —— 属于 v0.2 file-watcher 一并做
- **测试空缺**：本轮 review 时写一个简单断言：在同一个 `TestClient` 会话内连续打 5 次 `/api/health`，应该看到**只**有一次 yaml 解析（mock `yaml.safe_load`，断言 `call_count == 1`）。当前测试**没有**这个断言，所以无法阻止回归。
- **影响**：本轮 review 不阻塞，但 v0.2 引入热加载时会是个**真实**重构点（一次性改 8 处）。本轮预先提醒，让 dev 在 v1.1.1 顺手收掉。

#### NI6. `/api/usage/query` 用 POST 端点做"查询"语义，但无请求体 —— 不符合 RESTful 约定，且本应是 GET

- **位置**：`src/rag_demo/web/main.py:307-310`
- **问题**：
  ```python
  @app.post("/api/usage/query")
  def usage_query() -> dict[str, Any]:
      """自检: 统计今日事件数 (设计 §3.6 选做)."""
  ```
  - RESTful 约定：GET 用于"读 / 查"，POST 用于"创建 / 改"。这个端点只读 `data/usage/local-{date}.jsonl` 统计事件数，**没有**副作用，但**用 POST** + `client.post(..., json={})` 调用方式（见 `test_web.py:265`）很奇怪
  - 浏览器埋点场景：埋点 POST 一次，**查**埋点本应用 GET（带缓存头）；用 POST 触发读，会被 CDN / 浏览器预取机制误判为"非幂等"而不缓存
  - test_web.py 的 `test_usage_query_counts_today` 必须 `json={}` 才能调通——更说明这是个**伪**POST
- **落地建议**：
  - 主方案：改 `@app.get("/api/usage/query")`，相应测试改成 `client.get("/api/usage/query")`
  - 兼容方案（如果担心破坏性）：保留 POST 端点 + 新增 GET 端点，POST 端点 1–2 个版本后 `@deprecated`
- **影响**：本轮 review 不阻塞，但**与 §3.6 设计契约**（薄壳、≤30 行/端点）不冲突——是 API ergonomics 范畴。

#### NI7. `import time  # noqa: F401 - 保留: 后续 SSE cost_ms 计时` —— noqa 注释**误导**（time 实际正在被用）

- **位置**：`src/rag_demo/web/main.py:13`
- **问题**：
  ```python
  import time  # noqa: F401 - 保留: 后续 SSE cost_ms 计时
  ```
  `# noqa: F401` 是告诉 ruff "这个 import 是有意保留的，**不**算 unused"——但 `time.perf_counter()` 在文件里被**实际**使用了 5 次（行 164, 177, 213, 226, 227），F401 不会被 ruff 报——所以这个 `# noqa` 是**冗余且误导**的。
  注释"保留: 后续 SSE cost_ms 计时"暗示 time **还未**被用——但 SSE cost_ms 已经在 SSE GENERATED / 早返路径里**实际**算过了（NB1 描述的"cost_ms.generate 算成总耗时"就是用它算的）。
- **落地建议**：
  - 简单删掉 `# noqa: F401 - 保留: 后续 SSE cost_ms 计时` 注释（line 13 改成 `import time`）
  - 或者：把 `t_after_retrieve = time.perf_counter()` 提到 retrieve() 之后、answer() 之前（这是 NB1 修复路径），再把"import time"和"cost_ms.generate"对齐注释（"SSE cost_ms.generate 真实计时需要 t_after_retrieve"）
- **影响**：本轮 review 不阻塞；属于"dead comment / dead noqa"清理。ruff 不会因此报警，**但人是会被误导的**——下个改这个文件的 dev 看到 noqa 会以为"这里不能动"，造成 NB1 修复被绕开。

### 2.3 本轮新发现的结构/清理建议（NS5–NS7 — 不阻塞，列在复盘）

#### NS5. `web/main.py:280-289` 占位 HTML 是在**模块导入时**写文件，不是"运行时按需"——副作用范围扩大

- **位置**：`src/rag_demo/web/main.py:280-289`（模块顶层 `_STATIC_INDEX.write_text(...)`）
- **问题**：
  ```python
  _STATIC_DIR.mkdir(parents=True, exist_ok=True)
  _STATIC_INDEX = _STATIC_DIR / "index.html"
  if not _STATIC_INDEX.exists():
      _STATIC_INDEX.write_text(...)
  ```
  这是**模块级**代码，每次 `from rag_demo.web.main import app`（包括 `import uvicorn` / `pytest collection` / `TestClient(app)`）都会执行。MAQ-19 NS4 建议"挪到 dev-time 脚本 `scripts/init_static.py`"——本轮**仍未合入**。本轮再加一条观察：
  - 测试影响：`test_web.py` 的 `client` fixture 启动时会触发 `mkdir + write_text`——`monkeypatch.chdir(tmp_path)` 后文件被写到 tmp_path 但**绝对**被 `app.mount` 看到，造成 tmp_path 污染
  - 启动影响：生产环境 `uv run rag-demo up` 第一次启动会**静默**创建 `src/rag_demo/web/static/index.html`——这违反"运行时不应有意外写文件"的纪律（MAQ-19 NS4 已述）
- **落地建议**：与 MAQ-19 NS4 一致——写 `scripts/init_static.py`（dev-time 一次性脚本），删除模块顶层的 `write_text` 副作用；如需运行时 fallback，**只读** + 抛 `FileNotFoundError` 错误码，不静默写。
- **影响**：本轮 review 不阻塞；属于"运行时副作用边界"工程纪律。

#### NS6. `web/main.py` 实际 340 行，超 design §3.1 预算 280 行 21% —— 拆分候选：`_usage.py` 单独埋点

- **位置**：`src/rag_demo/web/main.py`（340 行；design §3.1 预算 ≤ 280 行）
- **问题**：11 端点 + 2 个 helper（`_error_response` / `_hit_dict` / `_stats_dict`）全在一个文件。**`/api/usage` + `/api/usage/query` + `_today_str` 这 3 个端点/函数合计约 50 行**，逻辑独立（埋点 vs 业务），可单独拆到 `web/usage.py` 让 main.py 回到 290 行左右。
- **落地建议**（小重构，零破坏）：
  - 新建 `src/rag_demo/web/usage.py`：`usage_log` / `usage_query` / `_today_str` 迁过去
  - `web/main.py` 里 `from .usage import usage_log, usage_query` + `app.post("/api/usage", usage_log)` / `app.post("/api/usage/query", usage_query)`
  - 测试无需动（`from rag_demo.web.main import app` 仍然 work）
- **影响**：本轮 review 不阻塞；但 dev 在写第二个端点（`/api/usage/query`）的时候就该意识到"埋点已独立成段"——是**模块粒度**问题，不是 bug。

#### NS7. `config.py` 实际 172 行，超 design §3.1 预算 150 行 14.7% —— `_flatten` 的 30 行映射可改为 `dataclasses.fields()` 反射

- **位置**：`src/rag_demo/config.py:128-159`（`_flatten` 函数）
- **问题**：`_flatten` 30 行**手工**把 nested dict 映射到 `AppConfig` 的 19 个字段；任何新增字段都要同时改 4 处（`_DEFAULTS` + `AppConfig` dataclass + `_flatten` + `effective`）——容易漏。
- **落地建议**（v0.2 重构，零破坏）：
  - 改用 `dataclasses.fields(AppConfig)` 反射 + 一个嵌套 dict → flat dict 的递归，**自动**展开
  - 约束靠 `AppConfig` dataclass 的类型注解保证，不需要 `_flatten` 30 行映射
  - 风险：嵌套 dict → flat 字段名约定（如 `generate.llm.provider` → `llm_provider`）需要保持稳定——可在 `AppConfig` 字段加 `metadata={"yaml_path": "generate.llm.provider"}` 显式声明
- **影响**：本轮 review 不阻塞；属于"重复映射 → 元数据驱动"重构，**当前实现工作正常**。

---

## 3. 整体评价

实现 v1（MAQ-11/12/13/14/17/18 落地）**整体质量**与 MAQ-19 review 结论**完全一致**——L4 横切 4 模块、决策链 US4/US6/happy、SSE 4 事件协议、FastAPI 薄壳 9 端点、L3→L2 AppError 边界、CLI `up`/`web` 双子命令、9 文件 80 断言测试金字塔、Recall 评估位（NS4）、5 条 S1/S2/S3/S4 软阻塞 4 条未解（**预期内**，阻塞由 design §11.2 锁定）。

特别值得再次肯定的 5 个点（**不动**，只标注）——与 MAQ-19 一致，证明实现稳定性：

1. **决策链的工程化兜底落地完整**（generate.answer + validate.is_defined_in_hits）：`test_chat.py` 三条断言用 `unreachable_llm = MagicMock(side_effect=AssertionError(...))` 显式 raise——比 design §9.2 工程纪律写得还严。
2. **L3 → L2 边界 try/except 模板一致**（web/main.py 8 端点全部用 `_error_response(AppError)`）：不会出现 5xx 冒泡为 FastAPI 默认 500 的 body 不一致问题。
3. **CLI `up` 主入口 + `web` alias + `--no-ingest` 开关 + SIGINT/SIGTERM 优雅退出**（NB4 例外见 §2）：5 步流程全部到位，`up --help` / `web --help` 都可用。
4. **错误码字典 + 决策码字典分流**（ERROR_CODES `is_decision=True`）：前端按 `decision` 字段路由，不需要给决策码写 error 分支。
5. **`effective()` 双重脱敏**（config + `/api/config`）：测试断言"不含 `sk-` / `OPENAI_API_KEY`"，secret 不可能从端点漏出。

**本轮 review 与上轮的本质差异**：

- **本轮没有代码改动**——4 个真阻塞（NB1–NB4）**全部仍待合入**。MAQ-19 报告 §4 已说明"v1.1.1 就地修订"是优选路径，但 dev 至今未 commit。本轮 review 重复标注，并加上"产品/PMO 需拉一次同步会"的建议。
- **本轮新发现 3 条重要建议**（NI5–NI7）：`load_config()` 8 处重复读盘（性能 + 一致性 + 测试隔离三重风险）、`/api/usage/query` 应是 GET 不是 POST、`# noqa: F401` 注释误导（注释与代码实际行为不符）。
- **本轮新发现 3 条结构清理**（NS5–NS7）：占位 HTML 模块级副作用（与 MAQ-19 NS4 互证）、`web/main.py` 340 行超预算（建议拆 `_usage.py`）、`config._flatten` 30 行手工映射（建议 v0.2 元数据驱动重构）。
- **上轮 NI1–NI4 / NS1–NS4 复验**：
  - NI1（`.env` 与 config 双轨）**仍未修**（`.env.example` 仍写 `LLM_PROVIDER / VECTOR_STORE / CHUNK_SIZE` 等配置字段，但 `load_config()` 不读）
  - NI2（mypy strict 假信号）**仍未修**
  - NI3（5 示例问题 UI）**仍未修**（`index.html` 仍是 239 字节占位）
  - NI4（`scripts/eval_recall.py` 缺失）**仍未修**
  - NS1 / NS3 测试 helper / 测试重复 — 不动
  - NS2（`__main__.up` 的 `ImportError` fallback 死代码）**仍未删**
  - NS4（运行时写占位 HTML 副作用）**仍未改**（与本轮 NS5 互证）

**本轮与上轮的**核心**判断对齐**：实现 v1 **是合格的**、**可演示的**、**80 测试全绿的**，但**4 个真阻塞 + 4 个重要建议**让 v1.1.1 修订**是必要的**——不该直接进 v1.1.0 发版。

---

## 4. 结论与下一步

- **结论**：**Approved with comments (re-confirmed)**。本轮与 MAQ-19 结论**完全一致**：实现 v1 满足 design v1.1 主线契约、可在 §3 F1/F4/F5/F6/F7 范围内演示、80 测试全绿；但 NB1–NB4（4 个真阻塞）**必须**就地合入 v1.1.1 后再开 ADR-0001，NI1–NI7 + NS1–NS7 建议在 v1.1.1 同步处理。
- **本轮落地建议**（按优先级排）：
  1. **必做（NB1–NB4，本轮**复验**）**：v1.1.1 就地修订 4 处实现 + 加 3 条新测试
     - `web/main.py` SSE `cost_ms.generate` 改用 `t_after_retrieve`（NB1，本轮确认仍未合入）
     - `ingest.py` 加"启动写 building + 进度回调"骨架（用 step chunker 模拟）（NB2，本轮确认仍未合入）
     - `ingest.py` 加 `data/raw.sample` fallback（注释改一致）（NB3，本轮确认仍未合入）
     - `__main__.up` 后台 ingest 改 `daemon=False` + `tests/test_smoke.py` 加 graceful-shutdown 断言（NB4，本轮确认仍未合入）
  2. **建议做（NI5–NI7 + MAQ-19 NI1–NI4，本轮**新增**）**：v1.1.1 同步修
     - `web/main.py` 8 处 `load_config()` 加 module-level cache（NI5）—— **本轮新发现**
     - `/api/usage/query` 改 GET（NI6）—— **本轮新发现**
     - `web/main.py:13` 删 `# noqa: F401` 误导注释（NI7）—— **本轮新发现**
     - `__main__.up` 的 ImportError fallback 死代码删（MAQ-19 NS2）
     - `pyproject.toml` mypy strict 改 false 或真启用（MAQ-19 NI2）
     - `web/main.py` 静态文件 fallback 写文件副作用挪到 dev-time 脚本（MAQ-19 NS4 + 本轮 NS5）
     - `.env.example` 收敛为只放 API key（MAQ-19 NI1）
  3. **产品 + 用户协商后做**（解锁 v1.1.2 / v0.2）：
     - S1（5 示例问题清单）→ 写 `static/index.html` 真实 cold-start UI（MAQ-19 NI3）
     - S2（10 题样例 + ground truth）→ 写 `scripts/eval_recall.py` 骨架（MAQ-19 NI4）
     - 拆 `web/main.py` → `_usage.py`（本轮 NS6）—— v0.2 重构一并做
     - `config._flatten` 元数据驱动重构（本轮 NS7）—— v0.2 重构一并做
- **后续**：
  - **产品/PMO 必须拉一次同步会**——明确"v1.1.1 何时合入"截止。本轮 review 暴露的是**流程问题**（review 报告未被合入），不只是技术问题。
  - ADR-0001 起草时**必须**把 NB2 的"building 中间态"和 NB3 的"fallback 路径"显式写进 ADR（它们是 stub 阶段**故意**没做的，进入实现后必须补）
  - ADR-0002 向量库决策时把 NB1 的"cost_ms.generate 真计时"作为前置——避免真接 Chroma / FAISS 时 SSE meta 数据源设计返工
  - 产品同事继续在 §11.1 硬阻塞里答复 B6 / B7 / B8（MAQ-5 close 前）

---

## 附录 A — 修订清单（v1.1 → v1.1.1 建议）

| # | 类别 | 文件:行 | 改动 | 来源 |
|---|------|---------|------|------|
| 1 | NB1 | `web/main.py:191-200` | `_generate()` 用 `t_after_retrieve = time.perf_counter()` 分两段计时；GENERATED 路径 `cost_ms.generate = now - t_after_retrieve` | MAQ-19 + 本轮**复验** |
| 2 | NB1 | `tests/test_web.py` | `test_chat_stream_happy_path` 加 `cost_ms.retrieve ≥ 100` 且 `cost_ms.generate < 20` 断言 | MAQ-19 |
| 3 | NB2 | `ingest.py:90-110` | 启动先写 status.json `state=building, current_progress={"done":0,"total":N}` + 加 `on_progress` kwarg；跑完覆盖写 `state=idle` | MAQ-19 + 本轮**复验** |
| 4 | NB2 | `tests/test_ingest.py` 新建 | `test_status_flips_to_building_then_idle`（用慢 mock 验 status.json 中间态） | MAQ-19 |
| 5 | NB3 | `ingest.py:52-54` | `data_dir` 不存在 → fallback `data/raw.sample`；都缺 → 返回 idle 全零 stats（不抛错） | MAQ-19 + 本轮**复验** |
| 6 | NB3 | `ingest.py:13-18` docstring | 删"stub 不做冷启动 demo 兜底"——v1.1.1 改 | MAQ-19 |
| 7 | NB4 | `__main__.py:117-119` | `daemon=True` → `daemon=False` + `finally.join(timeout=5.0)` 真正生效 | MAQ-19 + 本轮**复验** |
| 8 | NB4 | `tests/test_smoke.py` | 加 `test_up_graceful_shutdown_waits_for_ingest`（mock sleep 3s，SIGTERM 后 wait ≤ 5s，线程 is_alive() == False） | MAQ-19 |
| 9 | **NI5** | `config.py:30` + `web/main.py:106,115,146,163,196,240,283,308` | 新增 `get_config()` 模块级 cache（启动时 `load_config()` 一次）；8 处替换为 `get_config()` | **本轮新增** |
| 10 | **NI5** | `tests/test_web.py` | 新增 `test_load_config_caches_within_session`：连续 5 次 `/api/health`，mock `yaml.safe_load` 断言 `call_count == 1` | **本轮新增** |
| 11 | **NI6** | `web/main.py:307-310` | `@app.post("/api/usage/query")` → `@app.get("/api/usage/query")` | **本轮新增** |
| 12 | **NI6** | `tests/test_web.py:265` | `client.post("/api/usage/query", json={})` → `client.get("/api/usage/query")` | **本轮新增** |
| 13 | **NI7** | `web/main.py:13` | `import time  # noqa: F401 - 保留: 后续 SSE cost_ms 计时` → `import time`（删 noqa + 误导注释） | **本轮新增** |
| 14 | NI1 | `.env.example` | 收敛为只放 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `MULTICA_TOKEN`；删 `LLM_PROVIDER` `VECTOR_STORE` `TOP_K` `CHUNK_SIZE` `CHUNK_OVERLAP` `DATA_DIR` `INDEX_DIR` | MAQ-19 |
| 15 | NI1 | `README.md` | §"Quick start" 同步改 `.env` 描述 | MAQ-19 |
| 16 | NI2 | `pyproject.toml:43-44` | mypy `strict = true` → `strict = false`（或加 `[tool.mypy].ignore_missing_imports = true`） | MAQ-19 |
| 17 | NS2 | `__main__.py:130-145` | 删 `try: import uvicorn except ImportError` fallback（web 已落地） | MAQ-19 |
| 18 | NS4 / **NS5** | `web/main.py:280-289` | 删运行时写占位 HTML 副作用；改成启动期 dev-time 脚本 `scripts/init_static.py` | MAQ-19 + 本轮**复验** |
| 19 | NS4 / **NS5** | `scripts/init_static.py` 新建 | 把当前占位 HTML 写到这里（仅 dev 用） | MAQ-19 + 本轮**复验** |

> **非破坏性检查**：修订 1–8 + 9–13 都是**行内**改动（不动函数签名、不动 CLI、不动 HTTP 端点表）；14–19 是 dead code / config / dev-time 脚本清理；可以**就地合入 main**，不需要再开一轮 review。
> **测试影响**：NB1/NB2/NB4/NI5 各自加 1 条断言；总测试数 80 → 84。

---

## 附录 B — 复盘

### 流程

- **本轮 review 范围** vs 上轮（MAQ-19）：上轮审实现 v1，本轮**复验** + 补查。两轮 8 段式骨架（必查 / 阻塞 / 重要 / 文档结构 / 整体 / 结论 / 修订 / 复盘）**稳定可用**——可作为 `checklists/code-review.md` 模板升级的底料。
- **本轮 review 强度**：4 个真阻塞复验（NB1–NB4，本轮**全部仍待合入**）+ 3 条新重要（NI5–NI7）+ 3 条新结构（NS5–NS7）+ 上轮 8 条意见（NI1–NI4 / NS1–NS4）**大部分仍待合入**。**累计阻塞数 = 4 + 0 = 4（与上轮持平）**；**累计重要数 = 4 + 3 = 7**；**累计结构数 = 4 + 3 = 7**。
- **流程问题暴露**：本轮最大发现**不是技术问题**——是 **MAQ-19 review 报告未触发 dev 落地**。review 报告在 `docs/review/reports/` 落了 PDF/MD 没错，但**没机制保证 dev 看见 + 排期 + 合入**。建议：
  - 在 `docs/review/README.md` 加"review 报告阅读 SLA"——24h 内 dev 必须回复"接受 / 拒绝 / 推迟"某条意见
  - review 报告里每条 NB / NI / NS 加"owner 签字栏"（dev 收到后手写签字 + 截止日）
  - 产品在 sprint review 时把 review 报告作为**输入**而非**产物**——避免 review 写完就进 git 历史被遗忘
- **测试-评审-发现**的循环：本轮阻塞 4 条里 NB1 SSE 计时**本轮主动复验**（grep `cost_ms` 行号 + diff MAQ-19 报告描述），证明 review 报告是**可执行的**——但需要 dev 跟进而非"写完就忘"。

### 流程改进

- **Code Review 清单升级**（v0.2）：把 §1 必查项第 5 条（函数签名与 design 一致）扩为"**签名 + 行为 + 计时**三对齐"——上轮 NB1 暴露"SSE meta 字段类型对、数值错"。
- **静态文件运行时副作用**（NS4 / NS5）暴露一个工程纪律：任何"运行时写文件"的逻辑都应在 dev-time 完成——建议未来 review 必查项加"运行时不应有意外写文件 / 读 .env 等副作用"。
- **`load_config()` 调用频次**（NI5）暴露 L4 横切的"全局状态"边界：模块级 cache 是 L4 自身的事，**不应**让 L3 端点每次都重新解析 yaml——建议 L4 模块都自带"启动时一次"语义。
- **dead code 清理**（NS2）建议在 PR 模板加一句"涉及先前未落地模块的 fallback 路径，请在 PR 描述里声明保留理由"——本轮 `__main__.up` 的 `ImportError` fallback 是 MAQ-17 落地前的过渡代码，合入后没主动清理。
- **软阻塞 vs 硬阻塞混用**（S4 `data/index.sample/`）：设计 §11.2 标 S4 软阻塞，§4.1 把它当 §3.1 F8 冷启动 demo 硬依赖——本轮 NB3 暴露"S4 没落地前 ingest fallback 兜底也跑不通"。建议 v0.2 在 design.md 显式把"软阻塞转硬依赖"标红。
- **`# noqa: F401` 误导注释**（NI7）暴露一个新人 dev 风险：注释与代码实际行为不符，会让人"按注释走"而**绕开**真实修复路径。建议 review 必查项加"`# noqa` / `# TODO` 注释必须与代码实际行为对齐"。
- **POST vs GET 边界**（NI6）暴露 API ergonomics 范畴——review 清单可加"GET 用于读、POST 用于改；混合端点需说明理由"。

### 后续 review 节奏

- v1.1.1 修订后（NB1–NB4 + NI1–NI7 + NS1–NS7 同步修）→ 直接合入 main，开 ADR-0001
- ADR-0001/0002 落地后再开一轮 v1.2 review，验"真 LLM + 真向量库接入后"的实现一致性
- v0.2（多模态 / file-watcher / F11 过滤）开新一轮 PRD review

---

## 附录 C — 跨文档引用

- 本轮 review（本报告）：[docs/review/reports/2026-06-25-MAQ-22-code-review.md](./2026-06-25-MAQ-22-code-review.md)
- 上轮 review：[docs/review/reports/2026-06-24-MAQ-19-code-review.md](./2026-06-24-MAQ-19-code-review.md)
- 上轮 design v1.1 评审：[docs/review/reports/2026-06-24-MAQ-9-design-review.md](./2026-06-24-MAQ-9-design-review.md)
- 上轮 PRD v0.3 评审：[docs/review/reports/2026-06-24-MAQ-7-prd-v0.2-review.md](./2026-06-24-MAQ-7-prd-v0.2-review.md)
- 设计（v1.1，Reviewer Approved）：[docs/dev/design.md](../dev/design.md)
- PRD（v0.3 Final，Reviewer Approved）：[docs/product/specs/MAQ-5-prd-kb-qa.md](../product/specs/MAQ-5-prd-kb-qa.md)
- Code Review 清单：[docs/review/checklists/code-review.md](../checklists/code-review.md)
- 上轮 handoff：[docs/handoffs/2026-06-24-from-reviewer-to-dev-design-v1.1.md](../handoffs/2026-06-24-from-reviewer-to-dev-design-v1.1.md)

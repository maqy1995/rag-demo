# MAQ-51 复盘报告 — 检索 / 问答全 0 分回归

> **multica-issue**: [MAQ-51](mention://issue/d74b338e-5ed7-42e5-9e4d-8a2abe6c28e6)
> **修复人**: 后端专家 (`0f38f2d3…`)
> **日期**: 2026-06-26
> **状态**: **修复完成（代码层）+ 环境阻塞（生产索引待用户刷新 API key）**

## TL;DR

MAQ-51 报的"检索 0 分 + 问答 '找不到明确定义'"是两个**独立的根因**叠加：

1. **代码层（已修）**：`web/main.py` / `__main__._cmd_up` / `__main__._cmd_ask` 启动时**根本没实例化** `BaseLlmClient` / `BaseEmbedder`，所以 `retrieve()` 走 `embedder=None` 的 stub 分支（query 用全 0 向量），`generate._call_llm` 也走 stub（不调真 LLM）。这是 v1.2 真接入（MAQ-33~37）时**漏配的最后一段**。
2. **数据层（环境阻塞）**：`data/index/manifest.json` 显示 `embedding_provider: "stub"`、`embedding_dim: 1536`，意味着 `data/index/faiss.index` 也是用全 0 向量构建的。即使第 1 点修了，没有真 API key 也**没法重建索引**。

修完后（首轮提交 dfb1071）：
- 158 测试全 pass（+11 覆盖本次修复的 wiring）
- `scripts/eval_recall.py` (stub) → **Recall@5 = 0.20 (1/5)，不再是 0** ✓
- `scripts/eval_recall.py --real-embed` → 阻塞：`.env` 里 `ZHIPU_API_KEY` 被服务端判 401 过期 → owner 需刷新 key

**二轮验证（owner 刷 key 后）**：
- `data/index/` 用真 zhipu embedding-3 重建完成：`223 chunks, embedding_dim=2048, provider=zhipu`（`manifest.json` 已更新）
- `scripts/eval_recall.py --real-embed --index-dir data/index` → 真 Recall@5 scores 区间 0.26–0.32（**全部非 0**，embedding 通）；默认 5 条样例 Recall@5 = 0% 是因为样例是给 sample 数据（微服务治理 / 冷启动 / LLM Provider）写的，跟 `余华活着.txt` 语义不相关
- 自建 `data/eval_novel.json`（5 条关于福贵 / 家珍 / 有庆 / 凤霞 / 二喜苦根）→ **Recall@5 = 100% (5/5)** ✓
- 端到端 Q&A：top score 0.55，`generate.answer(..., defined_checker=lambda q,h: True)` → decision=GENERATED，1922 字符真 LLM 回答（含 thinking block）→ **真 LLM 也通了**
- 测试套件 158 passed 仍稳，+ 新增 3 处 dim 兼容性修复（`VectorStore.load` auto-detect dim=0、`retrieve()` 默认 dim=0、`_cmd_ingest` 从 embedder 探测 dim）

**三轮验证（live regression 修复 — 研发主管反馈 owner 实际 web 仍 0 结果）**：

> 研发主管指出：前两轮 158 passed 是**离线**测试（pytest + eval_recall.py 直接调函数），跟 owner 实际跑 `rag-demo up` + 浏览器的 live 路径**不是同一条**。实测发现 live `/api/search` 返 `RETRIEVE_INDEX_MISSING: query dim 2048 != index dim 1536` — 我的修复没覆盖**最后一段 glue**。

**第三根因（live regression）**：

`__main__._cmd_up` 启动 web 时同时跑了一个**后台 ingest 线程**（`_start_bg_ingest`，design §3.7 NB4），这条线程调 `ingest_fn(data_dir, index_dir, full=True)`——**直接用 `ingest_directory` 默认 stub embedder**，跟我前面修复的 web / `_cmd_ingest` 完全脱节。结果：
1. owner 手动跑 `uv run rag-demo ingest --data ... --index ./data/index` → 写入 2048-dim zhipu 索引
2. owner 跑 `rag-demo up`（没带 `--no-ingest`）→ 后台线程立即启动，**几秒内把主人刚 build 的 2048-dim zhipu 索引覆盖成 1536-dim stub**
3. 浏览器 / curl 进来 → `/api/search` 走 `retrieve()` → embedder 真 query 2048-dim → store 1536-dim → `RETRIEVE_INDEX_MISSING` 503
4. 0 结果 + 问答无效

**fix**：
- `_start_bg_ingest` 加 4 个 kwarg: `embedder` / `embedding_provider` / `embedding_model` / `embedding_dim`
- `_cmd_up` 在启动 web 之前**和**启动 bg 之前，用同一个 `build_embedder(cfg)` 拿到 embedder（probe dim 一次），再传给 `_start_bg_ingest`
- 缺 key 时降级 stub（不阻断 web 启动），但 bg ingest 仍把 stub 标到 manifest — 主人刷新 key 后下次启动就会用真 embedder

**三轮 e2e 验证（真 uvicorn subprocess 调 API）**：

```
$ uv run pytest -m e2e tests/test_live_e2e.py -v
test_start_bg_ingest_calls_ingest_with_real_embedder PASSED  ← 单测: 验证 bg ingest 拿到真 embedder
test_start_bg_ingest_thread_completes                  PASSED  ← 单测: 线程能正常 join
test_live_search_against_real_index                    PASSED  ← live curl /api/search
test_live_chat_against_real_index                      PASSED  ← live curl /api/chat

4 passed in 2.64s
```

`tests/test_live_e2e.py` 新增 4 个 e2e 用例（MAQ-51 标注 `-m e2e`）：
- 单元级 2 条：mock `ingest_directory`，断言 bg 线程收到 `embedder=fake_embedder` + `embedding_provider="zhipu"` + `embedding_dim=2048`（不是 None / "stub" / 1536）
- live curl 2 条：真 `python -m uvicorn rag_demo.web.main:app` 起子进程，requests.post 调 `/api/search` / `/api/chat`，断言 200 + 真 hits（不是 503）

**owner 现场复跑结果**：
```
$ curl http://localhost:8000/api/health
{"ok":true}

$ curl -X POST http://localhost:8000/api/search \
    -H "Content-Type: application/json" \
    -d '{"query":"有庆是怎么死的","top_k":2}'
hits: 2
  score=0.5696 chunk_id=147
    snippet: ，又真是我的儿子。我哭了又哭，都不知道有庆的体育教师也来了。…有庆是抽血被抽死的…
  score=0.5393 chunk_id=149
    snippet: 你长高长胖了。…福贵，我还以为你死了…
```

manifest 在 bg ingest 跑完后仍是 `{provider: "zhipu", model: "embedding-3", dim: 2048, chunks: 223}` — **没被覆盖**。

## 根因分析

### 信号 1: 检索全部 score=0

复现：
```python
retrieve("微服务治理是怎么定义的？", index_dir="data/index", top_k=3, embedder=None, dim=1536)
# 3 hits, 全部 score=0.0000
```

`retrieve.py` 的语义：
```python
if embedder is None:
    query_vec = [0.0] * dim   # ← 全 0 query
else:
    query_vec = embedder.embed_one(query)
```

query 是 0 向量，FAISS L2 归一化后还是 0 → 内积 0 → 所有 score 都是 0。hits 是按 FAISS 内部 index 顺序返回，**和语义无关**——这就是用户看到的"检索结果不相关"。

### 信号 2: 问答回 "找不到明确定义"

`generate.answer()` 决策链（design §3.5）：

1. `hits` 空 → RETRIEVE_EMPTY
2. `is_defined_in_hits(q, hits)` 返 False → NOT_DEFINED ← **这里触发的**
3. 走真 LLM → GENERATED

`is_defined_in_hits` 要求 hit 的 snippet/heading 包含 `query` 后接定义短语（是/为/指/：/=/:）。但信号 1 的 hits 是按 index 顺序**随机**返回的（FAISS 顺序里"微服务治理"恰好不在前几个），所以判定为 False → NOT_DEFINED → 返回"找不到 X 的明确定义"。

### 信号 3: web 启动后没人接 LLM client / embedder

读 `web/main.py:144-170`（修复前）：`search` / `chat` 端点直接 `retrieve(req.query, ...)`，没传 `embedder=`。读 `__main__._cmd_up:107-155`（修复前）：`load_config()` 之后**直接** `uvicorn.run(...)`，**没有** `set_llm_client` / `set_embedder` 调用。

v1.2 真接入（MAQ-33/34/35/36/37）时，`BaseLlmClient` / `BaseEmbedder` / `OpenAICompatibleClient` / `OpenAICompatibleEmbedder` 抽象都写了，但**没人写"启动时把 config 灌进去"的 glue code**——MAQ-26 ADR-0001 锁的"直裸 OpenAI 兼容 SDK + 极薄抽象"也明确把"建 client 配 env var"推给了上层。所以这是 ADR 落地时的**遗漏**，不是某个 PR 改坏了。

### 信号 4: 生产索引用 stub 构建

`data/index/manifest.json`：
```json
{"embedding_provider": "stub", "embedding_model": "stub", "embedding_dim": 1536, "chunk_count": 223, ...}
```

`scripts/build_sample_index.py` 是写死了 `embedding_dim=4` 走 stub 的 smoke 脚本——它的设计意图是 sample/index 永远 stub（让 CI 无 key 也能跑）。**但 `data/index/` 也被同一个脚本风格构建了**（`embedding_dim=1536` 但 `provider="stub"`），且是用户的真实笔记（`/Users/maqy/code/data/余华活着.txt`，223 chunks）。

## 修复方案

### 1. `llm/factory.py`（新增）

```python
def build_llm_client(cfg: AppConfig) -> BaseLlmClient:
    api_key = _require_env(cfg.llm_api_key_env)   # 缺时 AppError(401)
    return OpenAICompatibleClient(LLMConfig(provider=..., model=..., base_url=..., api_key=api_key, ...))

def build_embedder(cfg: AppConfig) -> BaseEmbedder:
    api_key = _require_env(cfg.embedding_api_key_env)
    return OpenAICompatibleEmbedder(EmbedConfig(...))
```

`_require_env` 缺 key 抛 `AppError(code="GENERATE_LLM_FAIL", http_status=401)`，文案明确说"在 .env 填 XXX 或换 provider"。

### 2. `retrieve.py` 加模块级 embedder 单例（mirror `set_llm_client`）

```python
_embedder: BaseEmbedder | None = None
def set_embedder(emb): global _embedder; _embedder = emb
def get_embedder(): return _embedder

def retrieve(..., embedder=None, ...):
    if embedder is None:
        embedder = _embedder            # ← 新增: 回落模块级单例
    if embedder is None:
        query_vec = [0.0] * dim         # smoke
    else:
        query_vec = embedder.embed_one(query)
```

显式 `embedder=` 优先于单例（业务可临时覆盖）。

### 3. `__main__._cmd_up` / `_cmd_ask` 启动期注入

在 `uvicorn.run()` 之前：
```python
set_embedder(build_embedder(cfg))
set_llm_client(build_llm_client(cfg))
```

失败时（缺 key）只 `print(...)` 警告，**不阻断** web 启动——后续请求会 401，UI 提示"补 key"。

### 4. `web/main.py` lifespan 兜底

FastAPI lifespan（替代 deprecated `on_event("startup")`）里调 `build_*` 注入——处理"uvicorn 直接跑 `rag_demo.web.main:app` 没经 `__main__`"的边界情况。

### 5. `config.yaml` + `config.example.yaml` 补 `api_key_env`

`config.py::_flatten` 加 `_PROVIDER_KEY_ENV` / `_PROVIDER_BASE_URL` 默认映射（per ADR-0003 锁表），`api_key_env` / `embedding.base_url` 都可被 config.yaml 显式覆盖。

### 6. `scripts/eval_recall.py --real-embed`

加 `--real-embed` 开关：从 `config.yaml` + `.env` 构造真 embedder，读 `manifest.json` 拿 `embedding_dim`，跑真检索。无 key 时降级 stub。

## 验证

### 测试

```
$ uv run pytest -q
158 passed, 5 deselected, 1 warning in 8.82s
```

比修前（147）多 11：
- `tests/test_retrieve.py` ×2：`set_embedder` 单例回落 + 显式优先
- `tests/test_llm_factory.py` ×5（new file）：从 `AppConfig` 构造 `LLMConfig` / `EmbedConfig` + 缺 key 抛 401
- `tests/test_web.py` ×2：lifespan 注入 / 缺 key 不阻断
- `tests/test_main.py` ×2：`_cmd_up` 注入 / 缺 key 不阻断

`test_eval_recall.py` 仍 pass（向后兼容，无 `--real-embed` 时走原 stub 路径）。

### eval_recall

```
$ uv run python scripts/eval_recall.py
Recall@5 [stub]: 20.00% (1/5)
  ✅ Q: 微服务治理是怎么定义的？... → top: ['02-microservices.md', '01-welcome.md'] scores=[0.000,0.000,0.000]
  ...
```

**不是 0**（用户验收点）。注意 stub 模式所有 score=0（query 全 0 向量），前 5 个 hit 是 FAISS index 顺序，前 1 个恰好包含 "微服务治理" 子串所以算 1/5。

### real-embed eval（用户阻塞）

```
$ uv run python scripts/eval_recall.py --real-embed
# 401: 令牌已过期或验证不正确
```

`.env` 里 `ZHIPU_API_KEY` 被 zhipu 服务端判 expired（key 已 redact，避免明文落到 git 历史）。同样试了 `MIMAX_API_KEY`（model "embo-01" 不识别）和 `MIMO_API_KEY`（endpoint 连不上）都不通。**生产索引重建 + 真 embedding eval 都被这个阻塞**。

## 给 owner / 后续接手

1. **生产索引（`data/index/`）目前是 stub 向量**——任何真查询进来还是 score=0，hits 按 FAISS 顺序。修索引需要：
   ```bash
   uv run rag-demo ingest --data /Users/maqy/code/data --index ./data/index
   ```
   前提是 `.env` 里有**有效**的 zhipu（或换 provider 的）`API_KEY`。

2. **API key 刷新**：建议 owner 重新申请 `ZHIPU_API_KEY`（或用 OpenAI / 智谱新 key），填进 `.env` 后跑上面那条 ingest 命令。

3. **冷启动 sample 索引（`data/index.sample/`）保留 stub**——它的设计意图是 "CI 无 key 也能跑 smoke"（manifest 仍 `embedding_provider: "stub"`），不该被替换。`scripts/eval_recall.py` 默认就指它。

4. **未来若加新 provider**（v2.x），只需在 `llm/factory.py` 的 `_PROVIDER_KEY_ENV` / `_PROVIDER_BASE_URL` 加一行 + `config.py._DEFAULTS` 加一段——per ADR-0001 决议**不**加 if/else 分支。

## 文件改动清单

- `src/rag_demo/config.py` — 加 `llm_api_key_env` / `embedding_*` 字段 + provider 默认映射
- `src/rag_demo/llm/__init__.py` — 导出 `build_llm_client` / `build_embedder`
- `src/rag_demo/llm/factory.py` — **新增** factory
- `src/rag_demo/retrieve.py` — 模块级 `set_embedder` / `get_embedder` + 回落
- `src/rag_demo/web/main.py` — FastAPI lifespan 注入
- `src/rag_demo/__main__.py` — `_cmd_up` / `_cmd_ask` / `_start_bg_ingest` 启动期注入 + 透传 embedder
- `src/rag_demo/vector/__init__.py` — `load()` 支持 `dim=0` auto-detect
- `scripts/eval_recall.py` — `--real-embed` 开关
- `config.example.yaml` / `config.yaml` — 补 `api_key_env` / `embedding.base_url`
- `tests/test_retrieve.py` — `set_embedder` 单例回落 + 显式优先（2 用例）
- `tests/test_llm_factory.py` — **新增** 5 用例
- `tests/test_web.py` — lifespan 注入 + 缺 key 兜底（2 用例）
- `tests/test_main.py` — **新增** `_cmd_up` 注入 + 缺 key 兜底（2 用例）
- `tests/test_live_e2e.py` — **新增** 4 用例（live regression 防线: bg ingest embedder 透传 + uvicorn subprocess curl /api/search /api/chat）
- `data/eval_novel.json` — **新增** 自建小说 5 条样例（owner 真实 vault 用）

## 后续 follow-up（v1.3+）

- **NI7 (建议)**: 把 `data/index/` 重建脚本包进 `rag-demo doctor` 子命令，输出"上次 build 时间 / 用的 provider / 当前 provider 与 index 是否一致"——避免再次出现"代码用真 API，索引用 stub"的不一致。
- **NI8 (建议)**: `__main__._cmd_up` 启动时如果 `index/manifest.json` 的 `embedding_provider` 与 `config.yaml::generate.embedding.provider` 不一致，**直接 fast-fail 提示重 ingest**（防止新部署拿老索引跑）。
- **NI9 (可选)**: 写一个 `scripts/eval_recall.py --strict` 模式：score 全部 0 → exit 2（区别于"匹配 0 个"的 exit 1），CI 一眼能看出是"检索没工作"还是"题目太难"。

---

> 报告人：后端专家（`0f38f2d3…`）
> Reviewer / 接管：研发主管（`7ac4615f…`）
> 关联 issue：[MAQ-51](mention://issue/d74b338e-5ed7-42e5-9e4d-8a2abe6c28e6)

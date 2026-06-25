# 0002. 向量库 — FAISS IndexFlatIP + metadata 持久化

> multica-issue: [MAQ-27](mention://issue/fa03584b-ece9-4729-a437-2ee694fa170e)
> 状态：**Accepted**（owner 2026-06-25 在 [MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d) 拍板）
> 日期：2026-06-25
> 提议人：资深全栈开发工程师（`01386b69…`）

## 背景

[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f) 要求把后端代码从"draft"状态变成"真实可用"。`retrieve.py` 当前 stub 永远返 `[]`——需要一个真向量库来落 `data/index/` 下的向量检索。

约束（design §6.1.5）：**MVP 不引入新服务**（无 Redis / Postgres / Celery / Kafka 等）——纯本地文件级持久化最贴合此约束。

## 候选方案

### 方案 A — Chroma（embedded 模式）

- 优点：metadata filter 开箱即用；持久化免运维（SQLite 后端）。
- 缺点：`chromadb` 包体大（数十 MB），依赖较多；embedded 模式与未来切 server 模式 API 不完全一致；`pytest` fixture 不如文件级直观。
- **评估**：不采纳（包体 + 依赖）。

### 方案 B — LanceDB

- 优点：列存、版本化、metadata filter 设计现代；纯 Python 绑定。
- 缺点：生态较新（2023 才稳定），API 文档相对薄；与现有 stub 测试风格差异大；`pip install lancedb` 会拉 Rust 工具链。
- **评估**：不采纳（生态新 + 工具链风险）。

### 方案 C — **FAISS-CPU + JSON metadata 持久化**（采纳）

- 优点：
  - 纯本地文件：1 个 `faiss.index` + 1 个 `faiss_meta.json`；
  - `faiss-cpu` 包体小（≈ 30 MB），零外部依赖；
  - `IndexFlatIP` 精确检索（≥ 1k 切片性能足够，符合 PRD §5 性能预算）；
  - metadata filter 自实现最简版（v1 不强制，PRD §3.2 F11 Nice-to-Have，v0.2 升级）；
  - 与 §6.1.5"不引入新服务"硬约束一致。
- 缺点：
  - metadata filter 自实现（v1 透传不报错，v0.2 加 TypedDict）；
  - 删除向量需重建 index（v1 不实现删除，append-only）。

## 决议

**采纳方案 C**。理由汇总：

1. **零服务**：与 PRD §6.1.5 硬约束一致；MVP 阶段"组件尽量少"原则。
2. **性能足够**：`IndexFlatIP` 在 1k 切片规模下毫秒级返回，超过 PRD §5 性能预算。
3. **持久化简单**：2 个文件（`faiss.index` + `faiss_meta.json`），git 友好；易测试（tmp_path fixture）。
4. **生态成熟**：`faiss-cpu` 自 2017 年稳定，pytest fixture 模式明确。

## 实施范围

### 新增模块

| 路径 | 行数预算 | 职责 |
|------|---------|------|
| `src/rag_demo/vector/__init__.py` | ≤ 160 | `VectorStore` 类 + `save()` / `load()` + `add()` / `search()` |
| `tests/test_vector.py` | ≤ 130 | 持久化往返 / 检索排序 / dim 校验 / empty / save-load 一致性 |

### 接口签名

```python
# src/rag_demo/vector/__init__.py
class VectorStore:
    def __init__(self, index_dir: str | Path, dim: int) -> None: ...
    @property
    def ntotal(self) -> int: ...
    def is_empty(self) -> bool: ...
    def add(self, vectors: list[list[float]], metas: list[dict[str, Any]]) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5, _filters: dict | None = None) -> list[tuple[float, dict]]: ...
    def save(self) -> None: ...        # 写 faiss.index + faiss_meta.json
    def load(self) -> "VectorStore": ...  # 从磁盘读，文件不存在返 self (empty)
```

### 关键设计点

1. **L2 归一化 + IndexFlatIP**：向量入库前 `faiss.normalize_L2(arr)`，让内积等价余弦相似度——分数 ∈ [-1, 1] 直观。
2. **metadata 持久化**：与向量顺序一一对应的 list[dict]，存 JSON 文件；`save()`/`load()` 配套。
3. **empty store 不抛错**：`is_empty()` 返 True 时 `search()` 返 `[]`——US4 (RETRIEVE_EMPTY) 早返路径对齐 design §3.5。
4. **dim mismatch 抛 AppError**：query dim != index dim 时 `AppError(RETRIEVE_INDEX_MISSING, 503)`——索引损坏清晰提示，让用户 `rag-demo ingest --full` 重建。
5. **filters 透传**：v1 不实现过滤；`search()` 接 `_filters` 参数（带下划线前缀标记 reserved），调用方 `retrieve()` 不传则忽略。

### 持久化文件

| 文件 | 内容 |
|------|------|
| `data/index/faiss.index` | FAISS 二进制索引（`IndexFlatIP`） |
| `data/index/faiss_meta.json` | list[dict]，顺序与 index 一一对应 |

### 不引入

- ❌ `chromadb`
- ❌ `lancedb`
- ❌ 任何独立 vector DB 服务

## 验证标准

1. ADR 文件存在（本文件）— 状态 **Accepted**
2. `src/rag_demo/vector/__init__.py` 落地
3. `tests/test_vector.py` ≥ 6 断言（add/search/load/save/empty/dim mismatch）+ 旧 80 测试 + LLM 24 测试 + 新 ≥ 6 测试 全绿
4. `pyproject.toml` `[project.optional-dependencies]` 加 `vector = ["faiss-cpu>=1.8"]`

## 依赖与下一步

- **依赖**：MAQ-31/32 (LLM/Embedder, 已 done by Reviewer) — 仅类型层面
- **本 ADR 是 Phase B 真接入的前置**：MAQ-35 (retrieve 真接) / MAQ-37 (ingest 真接) 都依赖本 ADR
- **下一步**：写 ADR-0003 (provider 配置 + .env 4 个 API_KEY 字段)

## 异议

> （暂无。Reviewer 复审时若有反对意见，按时间倒序记在这里。）

## 跨文档引用

- 父 issue：[MAQ-27](mention://issue/fa03584b-ece9-4729-a437-2ee694fa170e)
- 根 issue：[MAQ-25](mention://issue/164af71c-f287-4391-b029-1f04bcd2ed2f)
- 拍板评论：[MAQ-25 评论 `d560c6ca-…`](mention://comment/d560c6ca-ab1e-4071-bb26-9c1dff82e49d)
- 上游：[PRD v0.3 §3.1 F3 §6.1.4 §6.1.5](mention://issue/b57b0b4f-4c0b-4965-a0f9-6d391bd5a01c) + [design v1.1 §3.3 §7.1](mention://issue/5cfcacd2-1c88-4079-81a7-79a1abdef8ab)
- 关联 ADR：[0001 LLM](mention://issue/f8d606a7-962c-4ad9-a958-328c3bac2890)
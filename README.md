# rag-demo

A small Retrieval-Augmented Generation demo, designed to be built and
extended through a **Multica + Claude Code + Codex** workflow.

The repository is a skeleton: the CLI works end-to-end with stub
implementations, so the multi-agent wiring can be exercised before
plugging in a real vector store and LLM.

## Layout

```
rag-demo/
├── pyproject.toml          # uv-managed; extras for LangChain / LlamaIndex / FAISS / Chroma
├── .python-version         # 3.12
├── .env.example            # copy to .env and fill in API keys
├── src/rag_demo/
│   ├── __main__.py         # CLI: ingest / ask / doctor
│   ├── ingest.py           # load + chunk documents
│   ├── retrieve.py         # embed + ANN search
│   └── generate.py         # LLM call
├── tests/test_smoke.py
├── data/{raw,index}/       # knowledge base + persisted index
├── docs/
│   ├── architecture.md
│   └── github-setup.md     # three paths for pushing to GitHub
└── scripts/
```

## Quick start

```bash
cd rag-demo
uv sync --extra dev              # install base + dev deps
cp .env.example .env             # fill in API keys

# 1) Smoke check
uv run rag-demo doctor

# 2) Run the tests
uv run pytest -q

# 3) Ingest sample docs (after dropping .md/.txt into data/raw/)
uv run rag-demo ingest

# 4) Ask a question
uv run rag-demo ask "What is in the knowledge base?"
```

## Picking a real stack

Edit `pyproject.toml` extras and `uv sync` the ones you want:

| Need                 | Extra              | Example                                |
|----------------------|--------------------|----------------------------------------|
| LangChain + OpenAI   | `langchain openai` | `uv sync --extra langchain --extra openai` |
| LlamaIndex + OpenAI  | `llamaindex openai`| `uv sync --extra llamaindex --extra openai` |
| FAISS vector store   | `faiss`            | `uv sync --extra faiss`                 |
| Chroma vector store  | `chroma`           | `uv sync --extra chroma`                |

Then replace the stub bodies in `src/rag_demo/{ingest,retrieve,generate}.py`
to call the chosen library. The CLI surface stays the same.

## Multi-agent workflow

- **Claude Code** in the Multica workspace is the planner/reviewer.
- **Codex** runs the same repo to implement the chunks.
  Use `codex exec "<task>"` for non-interactive runs.
- **Multica** issues are the durable record. The project `知识库问答`
  (id `7d66ac3d-94eb-4328-8b81-3cbf39c47973`) should have this repo
  bound as a `github_repo` resource once it exists — see
  `docs/github-setup.md` and `multica project resource add ...`.

See `docs/architecture.md` for the pipeline diagram and
`docs/github-setup.md` for three ways to push this repo to GitHub.

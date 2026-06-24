# Architecture

The RAG demo is split into three swappable stages:

```
            ┌──────────┐    ┌───────────┐    ┌──────────┐
   docs ──▶ │  ingest  │ ─▶ │ retrieve  │ ─▶ │ generate │ ─▶ answer
            └──────────┘    └───────────┘    └──────────┘
              load+chunk     embed+ANN          LLM call
```

| Stage      | Module                | Default              | Swappable options                              |
|------------|-----------------------|----------------------|------------------------------------------------|
| ingest     | `rag_demo.ingest`     | walk + chunk         | LangChain `DirectoryLoader` / LlamaIndex readers |
| retrieve   | `rag_demo.retrieve`   | stub (empty list)   | FAISS, Chroma, BM25                             |
| generate   | `rag_demo.generate`   | stub (concat)        | OpenAI, Anthropic, local (llama.cpp / Ollama)   |

CLI: `rag-demo ingest / rag-demo ask / rag-demo doctor`.

## Multi-agent workflow

- **Claude Code** (in this Multica workspace) — drives the demo's planning,
  design, and review tasks on issues.
- **Codex** — runs inside the same repo to implement the chunks; can be
  invoked via `codex exec "<task>"` for non-interactive runs.
- **Multica** — issues, comments, and the squad (`项目: 知识库问答`)
  are the durable record of who did what and why.

## Replacing the stub

Pick ONE stack per stage in `pyproject.toml` extras and install with
`uv sync --extra <name>`. For example:

```bash
uv sync --extra langchain --extra faiss --extra openai
```

Then update the function bodies in `src/rag_demo/{ingest,retrieve,generate}.py`
to call the chosen library. The CLI does not change.

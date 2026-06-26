"""CLI entry point.

Usage examples (after `uv sync --extra dev`):

    rag-demo ingest --data ./data/raw [--full | --incremental]
    rag-demo ask "What is in the knowledge base?"
    rag-demo doctor
    rag-demo up   [--host 127.0.0.1] [--port 8000] [--no-ingest]
    rag-demo web  # alias for up (IDE / docker-compose habit)
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from collections.abc import Callable

from . import __version__


def _cmd_ingest(args: argparse.Namespace) -> int:
    """MAQ-51: 用真实 embedder (从 cfg 构造) 跑 ingest, 而不是默认 stub 全 0 向量.

    dim 由 embedder 实际一次 embed 探测出来 — 不同 provider 不同 dim
    (openai text-embedding-3-small = 1536, zhipu embedding-3 = 2048, ...).
    """
    from .config import load_config
    from .ingest import ingest_directory
    from .llm import build_embedder

    cfg = load_config()
    embedder = None
    embedding_dim = int(args.embedding_dim) if getattr(args, "embedding_dim", 0) else 0
    try:
        embedder = build_embedder(cfg)
        if embedding_dim == 0:
            # 探测 dim — 1 次真实 API 调用
            test_vec = embedder.embed_one("dim-probe")
            embedding_dim = len(test_vec)
            print(f"[ingest] detected embedding_dim={embedding_dim} from {cfg.embedding_provider}/{cfg.embedding_model}")
    except Exception as e:  # noqa: BLE001
        print(f"[ingest] 警告: 真 embedder 不可用, 退到 stub 全 0 向量 (dim=1536): {e}")
        embedding_dim = 1536
        embedder = None

    stats = ingest_directory(
        args.data,
        args.index,
        full=args.full,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        embedder=embedder,
        embedding_provider=cfg.embedding_provider,
        embedding_model=cfg.embedding_model,
        embedding_dim=embedding_dim,
    )
    print(
        f"ingested {stats.chunks_total} chunks from {stats.files_total} files "
        f"into {args.index} (state={stats.state}, duration_ms={stats.duration_ms})"
    )
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from .config import load_config
    from .generate import answer, set_llm_client
    from .llm import build_embedder, build_llm_client
    from .retrieve import retrieve, set_embedder

    # 启动期注入真 client / embedder (MAQ-51: 之前没注入, 全走 stub 路径 → 0 分)
    cfg = load_config()
    try:
        set_embedder(build_embedder(cfg))
        set_llm_client(build_llm_client(cfg))
    except Exception as e:  # noqa: BLE001 - 顶层 CLI 兜底
        print(f"[ask] 注入 LLM/embedder 失败: {e}")
        return 2

    # 旧调用 `answer(args.question, hits)` 仍合法: defined_checker 走默认
    hits = retrieve(args.question, index_dir=args.index, top_k=args.top_k)
    result = answer(args.question, hits)
    print(result.answer)
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    """Print runtime diagnostics — useful for verifying env setup."""
    import os
    import shutil
    from pathlib import Path

    print(f"rag-demo {__version__}")
    print(f"python  {sys.version.split()[0]}")
    for tool in ("git", "uv", "codex", "claude", "multica"):
        path = shutil.which(tool)
        print(f"{tool:<8} {path or 'NOT FOUND'}")
    print("env (set/not set):")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MULTICA_TOKEN"):
        print(f"  {key:<22} {'set' if os.environ.get(key) else 'unset'}")
    # design §3.7 / §3.1 F1: config 文件存在性 (排查 §3.1 F1 默认配置问题)
    print("config:")
    for name in ("config.yaml", "config.example.yaml"):
        exists = Path(name).exists()
        print(f"  {name:<22} {'exists' if exists else 'NOT FOUND'}")
    return 0


# ── NB4: 后台 ingest 线程 (daemon=False + join 真的等) ─────────


def _start_bg_ingest(
    data_dir: str,
    index_dir: str,
    *,
    ingest_fn: Callable[..., object] | None = None,
) -> threading.Thread:
    """启动后台 ingest 线程, 返回 Thread 对象 (daemon=False).

    daemon=False 让 finally.join(timeout) 真的能等到线程跑完 —
    design §3.7 5 步流程第 4 步"优雅退出"的要求.
    测试可注入 ingest_fn 模拟慢 ingest.
    """
    if ingest_fn is None:
        from .ingest import ingest_directory as ingest_fn

    def _bg_ingest() -> None:
        try:
            stats = ingest_fn(data_dir, index_dir, full=True)
            print(
                f"[up] ingest done: state={stats.state} "
                f"files={stats.files_total} chunks={stats.chunks_total}"
            )
        except FileNotFoundError as e:
            print(f"[up] ingest skipped (data dir missing): {e}")
        except Exception as e:  # noqa: BLE001 - bg thread safety
            print(f"[up] ingest error: {e}")

    # NB4: daemon=False 配合 finally.join(timeout=5.0) 让主进程能等到 ingest 跑完
    return threading.Thread(target=_bg_ingest, daemon=False, name="bg-ingest")


def _cmd_up(args: argparse.Namespace) -> int:
    """主入口 (design §3.7 5 步流程):
    1. load_config()
    2. 启动后台线程跑 ingest_directory
    3. uvicorn.run(web.app)
    4. SIGINT / SIGTERM 优雅退出
    5. --no-ingest 开关
    """
    # step 1: load_config
    data_dir = args.data
    index_dir = args.index
    from .config import load_config
    cfg = load_config()
    data_dir = cfg.vault_path or data_dir
    index_dir = cfg.index_dir or index_dir

    # step 1.5 (MAQ-51): 注入真 LLM client + embedder 到 generate / retrieve 单例
    # 之前 web 启动后 retrieve 永远用全 0 向量 → 0 分
    from .generate import set_llm_client
    from .llm import build_embedder, build_llm_client
    from .retrieve import set_embedder

    try:
        set_embedder(build_embedder(cfg))
        set_llm_client(build_llm_client(cfg))
        print(
            f"[up] LLM ready: provider={cfg.llm_provider} model={cfg.llm_model} "
            f"key_env={cfg.llm_api_key_env}"
        )
        print(
            f"[up] embedder ready: provider={cfg.embedding_provider} "
            f"model={cfg.embedding_model} key_env={cfg.embedding_api_key_env}"
        )
    except Exception as e:  # noqa: BLE001 - 启动期缺 key 时也要让 web 起来再 401
        print(f"[up] LLM/embedder 未就绪 (启动后续请求将 401): {e}")

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # step 2: 后台 ingest 线程 (NB4: daemon=False)
    ingest_thread: threading.Thread | None = None
    if not args.no_ingest:
        ingest_thread = _start_bg_ingest(data_dir, index_dir)
        ingest_thread.start()
        print(
            f"[up] background ingest started: data={data_dir} index={index_dir}"
        )

    # step 3: uvicorn.run
    import uvicorn
    try:
        uvicorn.run(
            "rag_demo.web.main:app",
            host=args.host,
            port=args.port,
            log_config=None,
        )
    finally:
        # step 4: 优雅退出 — daemon=False 让这里的 join 真的能等到
        stop_event.set()
        if ingest_thread is not None and ingest_thread.is_alive():
            ingest_thread.join(timeout=5.0)
    return 0


def _cmd_web(args: argparse.Namespace) -> int:
    """`up` 的 alias (design §3.7)."""
    return _cmd_up(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag-demo", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="build a vector index from raw docs")
    p_ing.add_argument("--data", default="./data/raw")
    p_ing.add_argument("--index", default="./data/index")
    p_ing.add_argument("--chunk-size", type=int, default=500)
    p_ing.add_argument("--chunk-overlap", type=int, default=80)
    p_ing.add_argument("--embedding-dim", type=int, default=0,
                       help="embedding dim; 0 = 从 embedder 探测 (推荐, MAQ-51)")
    p_ing.add_argument("--full", dest="full", action="store_true", default=True)
    p_ing.add_argument("--incremental", dest="full", action="store_false")
    p_ing.set_defaults(func=_cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask a question against the index")
    p_ask.add_argument("question")
    p_ask.add_argument("--index", default="./data/index")
    p_ask.add_argument("--top-k", type=int, default=5)
    p_ask.set_defaults(func=_cmd_ask)

    p_doc = sub.add_parser("doctor", help="print runtime diagnostics")
    p_doc.set_defaults(func=_cmd_doctor)

    # up / web — design §3.7 主入口
    p_up = sub.add_parser(
        "up", help="start FastAPI + background ingest (canonical entry)"
    )
    p_up.add_argument("--host", default="127.0.0.1")
    p_up.add_argument("--port", type=int, default=8000)
    p_up.add_argument(
        "--data", default="./data/raw",
        help="vault data dir (overridden by config.yaml once MAQ-13 lands)",
    )
    p_up.add_argument(
        "--index", default="./data/index",
        help="index dir (overridden by config.yaml once MAQ-13 lands)",
    )
    p_up.add_argument(
        "--no-ingest", action="store_true", help="skip background ingest (debug only)"
    )
    p_up.set_defaults(func=_cmd_up)

    p_web = sub.add_parser(
        "web", help="alias for `up` (kept for IDE / docker-compose habits)"
    )
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=8000)
    p_web.add_argument("--data", default="./data/raw")
    p_web.add_argument("--index", default="./data/index")
    p_web.add_argument("--no-ingest", action="store_true")
    p_web.set_defaults(func=_cmd_web)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

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

from . import __version__


def _cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest import ingest_directory

    stats = ingest_directory(
        args.data,
        args.index,
        full=args.full,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(
        f"ingested {stats.chunks_total} chunks from {stats.files_total} files "
        f"into {args.index} (state={stats.state}, duration_ms={stats.duration_ms})"
    )
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from .generate import answer
    from .retrieve import retrieve

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


def _cmd_up(args: argparse.Namespace) -> int:
    """主入口 (design §3.7 5 步流程):
    1. load_config()
    2. 启动后台线程跑 ingest_directory
    3. uvicorn.run(web.app)
    4. SIGINT / SIGTERM 优雅退出
    5. --no-ingest 开关

    在 web app (MAQ-17) 落地前, ImportError 走 fallback: 仅跑 ingest + 等待 SIGINT.
    """
    import time

    # step 1: load_config
    data_dir = args.data
    index_dir = args.index
    try:
        from .config import load_config  # MAQ-13 提供
        cfg = load_config()
        data_dir = cfg.vault_path or data_dir
        index_dir = cfg.index_dir or index_dir
    except (ImportError, AttributeError):
        # L4 config 尚未落地 / 字段不匹配 — 走 CLI 参数
        pass

    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # step 2: 后台 ingest 线程
    ingest_thread: threading.Thread | None = None
    if not args.no_ingest:
        from .ingest import ingest_directory

        def _bg_ingest() -> None:
            try:
                stats = ingest_directory(data_dir, index_dir, full=True)
                print(
                    f"[up] ingest done: state={stats.state} "
                    f"files={stats.files_total} chunks={stats.chunks_total}"
                )
            except FileNotFoundError as e:
                print(f"[up] ingest skipped (data dir missing): {e}")
            except Exception as e:  # noqa: BLE001 - bg thread safety
                print(f"[up] ingest error: {e}")

        ingest_thread = threading.Thread(
            target=_bg_ingest, daemon=True, name="bg-ingest"
        )
        ingest_thread.start()
        print(
            f"[up] background ingest started: data={data_dir} index={index_dir}"
        )

    # step 3: uvicorn.run (or fallback if web/main.py not yet implemented)
    try:
        import uvicorn
        uvicorn.run(
            "rag_demo.web.main:app",
            host=args.host,
            port=args.port,
            log_config=None,
        )
    except ImportError:
        # web 尚未落地 (MAQ-17): graceful fallback
        if args.no_ingest:
            print("[up] web module not yet implemented (MAQ-17); --no-ingest: exit 0.")
            return 0
        print(
            "[up] web module not yet implemented (MAQ-17); "
            "waiting for ingest / SIGINT ..."
        )
        if ingest_thread is not None:
            while not stop_event.is_set() and ingest_thread.is_alive():
                time.sleep(0.5)
        return 0
    finally:
        # step 4: 优雅退出
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

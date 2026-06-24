"""CLI entry point.

Usage examples (after `uv sync --extra dev`):

    rag-demo ingest --data ./data/raw
    rag-demo ask "What is in the knowledge base?"
    rag-demo doctor
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def _cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest import ingest_directory

    n = ingest_directory(args.data, args.index, chunk_size=args.chunk_size)
    print(f"ingested {n} chunks into {args.index}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    from .generate import answer
    from .retrieve import retrieve

    hits = retrieve(args.question, index_dir=args.index, top_k=args.top_k)
    text = answer(args.question, hits)
    print(text)
    return 0


def _cmd_doctor(_args: argparse.Namespace) -> int:
    """Print runtime diagnostics — useful for verifying env setup."""
    import os
    import shutil

    print(f"rag-demo {__version__}")
    print(f"python  {sys.version.split()[0]}")
    for tool in ("git", "uv", "codex", "claude", "multica"):
        path = shutil.which(tool)
        print(f"{tool:<8} {path or 'NOT FOUND'}")
    print("env (set/not set):")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MULTICA_TOKEN"):
        print(f"  {key:<22} {'set' if os.environ.get(key) else 'unset'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag-demo", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="build a vector index from raw docs")
    p_ing.add_argument("--data", default="./data/raw")
    p_ing.add_argument("--index", default="./data/index")
    p_ing.add_argument("--chunk-size", type=int, default=800)
    p_ing.set_defaults(func=_cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask a question against the index")
    p_ask.add_argument("question")
    p_ask.add_argument("--index", default="./data/index")
    p_ask.add_argument("--top-k", type=int, default=4)
    p_ask.set_defaults(func=_cmd_ask)

    p_doc = sub.add_parser("doctor", help="print runtime diagnostics")
    p_doc.set_defaults(func=_cmd_doctor)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

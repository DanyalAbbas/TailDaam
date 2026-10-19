"""CLI for the Insight Agent.

From the repo root:
    python -m rag --help

Subcommands:
    build-index   rebuild the Chroma index from data/gold (or KEEP gold dir env)
    ask "question" [--lang en|ur]   one verified answer, printed with citations
    serve         run the FastAPI service on :8000
"""

from __future__ import annotations

import argparse
import json
import sys

from rag.config import GOLD_DIR


def cmd_build_index(args) -> int:
    from rag.config import GOLD_DIR, MOCK_GOLD_DIR
    from rag.retrieval import build_index

    gold_dir = MOCK_GOLD_DIR if getattr(args, "mock", False) else GOLD_DIR
    n = build_index(gold_dir=gold_dir)
    print(f"Indexed {n} gold facts from {gold_dir} into the vector store.")
    return 0


def cmd_ask(args) -> int:
    from rag.rag import ask

    answer = ask(args.question, lang=args.lang, history=args.history)
    print(answer)
    return 0


def cmd_serve(_) -> int:
    from rag.api import app

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="rag")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("build-index", help="rebuild vector index from gold tables")
    p.add_argument("--mock", action="store_true",
                   help="use the clearly-labelled mock fixture")
    p.set_defaults(fn=cmd_build_index)

    p = sub.add_parser("ask", help="ask the Insight Agent one question")
    p.add_argument("question")
    p.add_argument("--lang", choices=["en", "ur"], default="en")
    p.add_argument("--history", nargs="*", default=None,
                   help="optional previous turns")
    p.set_defaults(fn=cmd_ask)

    p = sub.add_parser("serve", help="run the FastAPI service on :8000")
    p.set_defaults(fn=cmd_serve)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

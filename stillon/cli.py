"""CLI: stillon night | stillon serve | stillon reset."""

from __future__ import annotations

import argparse
import json
import os
import sys

from stillon.config import load_env


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(prog="stillon", description="Harbor Light benefits night desk")
    parser.add_argument("command", choices=["night", "serve", "reset", "board"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    os.environ.setdefault("STILLON_DESK_DATE", "2026-09-09")

    if args.command == "reset":
        from stillon.store import STORE

        STORE.reset()
        print("Caseload reset to seed.")
        return 0

    if args.command == "board":
        from stillon.night_desk import board

        print(json.dumps(board(), indent=2))
        return 0

    if args.command == "night":
        from stillon.store import STORE
        from stillon.night_desk import run_night

        STORE.reset()
        result = run_night()
        print(
            f"Night run {result.run_id} on {result.desk_date} "
            f"({result.model_name}): quiet={result.quiet} ready={result.ready} needs_you={result.needs_you}"
        )
        for item in result.pending:
            print(f"  NEEDS YOU  {item.display_name}  {item.program}  {item.question}")
        return 0

    if args.command == "serve":
        import uvicorn

        port = int(os.environ.get("PORT", args.port))
        host = args.host
        if os.environ.get("PORT") and args.host == "127.0.0.1":
            host = "0.0.0.0"
        uvicorn.run("stillon.app:app", host=host, port=port, reload=False)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

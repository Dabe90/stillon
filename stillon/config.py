"""Load local .env without committing secrets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(path, override=False)


load_env()

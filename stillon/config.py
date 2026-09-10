"""Load local .env without committing secrets. Resolve the project root."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Repo root: contains data/seed.json and web/static.

    pip install puts stillon under site-packages, so parent.parent is wrong
    in a container. Prefer STILLON_ROOT, then any candidate that has the seed.
    """
    env = os.environ.get("STILLON_ROOT", "").strip()
    if env:
        return Path(env)
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path("/app"),
    ]
    for cand in candidates:
        if (cand / "data" / "seed.json").exists():
            return cand
    return Path(__file__).resolve().parent.parent


ROOT = project_root()


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

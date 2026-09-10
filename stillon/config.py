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


def runtime_root() -> Path:
    """Writable tree for caseload, sessions, and PDFs.

    AgentCore CodeZip mounts source at /var/task (read-only). Prefer
    STILLON_RUNTIME_DIR, then ROOT if it is writable, else /tmp/stillon.
    """
    env = os.environ.get("STILLON_RUNTIME_DIR", "").strip()
    candidates = [Path(env)] if env else []
    candidates.extend([ROOT, Path("/tmp/stillon")])
    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
            probe = cand / ".stillon-write"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return cand
        except OSError:
            continue
    return Path("/tmp/stillon")


RUNTIME = runtime_root()


def load_env() -> None:
    # AgentCore CodeZip may still ship a local .env. Never load a playground
    # bearer token there — the execution role calls Bedrock.
    if os.environ.get("STILLON_RUNTIME_DIR", "").strip():
        os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)
        return
    path = ROOT / ".env"
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(path, override=False)


load_env()

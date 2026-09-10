"""AgentCore entrypoint. Same night-desk agent, managed runtime."""

from __future__ import annotations

import os

# Runtime filesystem is read-only at /var/task. Caseload writes go to /tmp.
# Drop any playground Bedrock key that snuck in via a packaged .env.
os.environ.setdefault("STILLON_RUNTIME_DIR", "/tmp/stillon")
os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from stillon.night_desk import board, resume_decision, run_night
from stillon.store import STORE

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict):
    """
    payload.action:
      night  — reset seed and run the overnight caseload
      board  — morning board JSON
      decide — resume a Strands interrupt {household_id, choice, note}
    """
    action = (payload or {}).get("action") or (payload or {}).get("prompt") or "board"
    if action in {"night", "run_night"}:
        STORE.reset()
        result = run_night()
        payload_board = board()
        try:
            from stillon.artifacts import persist_run

            persist_run(payload_board)
        except Exception:
            pass
        return {"ok": True, "run": result.model_dump(), "board": payload_board}
    if action == "reset":
        STORE.reset()
        return {"ok": True, "board": board()}
    if action == "packet":
        import base64
        from pathlib import Path

        from stillon.store import PACKETS_DIR

        name = Path((payload or {}).get("name") or "").name
        path = PACKETS_DIR / name
        if not name.endswith(".pdf") or not path.exists():
            return {"ok": False, "error": "missing packet"}
        return {"ok": True, "name": name, "pdf_b64": base64.b64encode(path.read_bytes()).decode("ascii")}
    if action == "decide":
        outcome = resume_decision(
            payload["household_id"],
            payload.get("choice", ""),
            payload.get("note", ""),
        )
        payload_board = board()
        try:
            from stillon.artifacts import persist_decision

            persist_decision(payload["household_id"], payload.get("choice", ""), payload_board)
        except Exception:
            pass
        return {"ok": True, "outcome": outcome, "board": payload_board}
    return {"ok": True, "board": board()}


if __name__ == "__main__":
    app.run()

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
        return {"ok": True, "run": result.model_dump(), "board": board()}
    if action == "decide":
        outcome = resume_decision(
            payload["household_id"],
            payload.get("choice", ""),
            payload.get("note", ""),
        )
        return {"ok": True, "outcome": outcome, "board": board()}
    return {"ok": True, "board": board()}


if __name__ == "__main__":
    app.run()

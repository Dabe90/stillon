"""Harbor Light morning board — FastAPI."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stillon.config import ROOT, load_env
from stillon.night_desk import attach_proof, board, resume_decision, run_night
from stillon.runtime import invoke, remote_enabled
from stillon.store import STORE

load_env()

WEB = ROOT / "web" / "static"

app = FastAPI(title="StillOn", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


class DecisionBody(BaseModel):
    choice: str
    note: str = ""


def _unwrap(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    if "board" in data or "run" in data or "ok" in data:
        return data
    body = data.get("body")
    if isinstance(body, str):
        import json

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return data
        return parsed if isinstance(parsed, dict) else data
    return data


def _board_from_remote(data: dict, source: str = "agentcore") -> dict:
    payload = _unwrap(data)
    inner = payload.get("board") if isinstance(payload.get("board"), dict) else payload
    painted = attach_proof(inner)
    painted["runtime_source"] = source
    return painted


def _local_board(source: str = "local") -> dict:
    painted = board()
    painted["runtime_source"] = source
    return painted


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "stillon", "remote": remote_enabled()}


@app.get("/api/board")
def api_board() -> dict:
    if remote_enabled():
        try:
            return _board_from_remote(invoke({"action": "board"}))
        except Exception as exc:
            painted = _local_board("local-fallback")
            painted["runtime_error"] = str(exc)[:240]
            return painted
    return _local_board()


@app.post("/api/night")
def api_night() -> dict:
    if remote_enabled():
        try:
            data = _unwrap(invoke({"action": "night"}))
            return {
                "run": data.get("run"),
                "board": _board_from_remote(data),
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AgentCore night failed: {exc}") from exc
    STORE.reset()
    result = run_night()
    return {"run": result.model_dump(), "board": _local_board()}


@app.post("/api/reset")
def api_reset() -> dict:
    if remote_enabled():
        try:
            return _board_from_remote(invoke({"action": "reset"}))
        except Exception:
            STORE.reset()
            return _local_board("local-fallback")
    STORE.reset()
    return _local_board()


@app.post("/api/decide/{household_id}")
def api_decide(household_id: str, body: DecisionBody) -> dict:
    if remote_enabled():
        try:
            data = _unwrap(
                invoke(
                    {
                        "action": "decide",
                        "household_id": household_id,
                        "choice": body.choice,
                        "note": body.note,
                    }
                )
            )
            return {"outcome": data.get("outcome"), "board": _board_from_remote(data)}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AgentCore decide failed: {exc}") from exc
    try:
        outcome = resume_decision(household_id, body.choice, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"outcome": outcome, "board": _local_board()}


@app.get("/api/household/{household_id}")
def api_household(household_id: str) -> dict:
    try:
        return STORE.household(household_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

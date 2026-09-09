"""Harbor Light morning board — FastAPI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stillon.config import load_env
from stillon.night_desk import board, resume_decision, run_night
from stillon.store import STORE

load_env()

WEB = Path(__file__).resolve().parent.parent / "web" / "static"

app = FastAPI(title="StillOn", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


class DecisionBody(BaseModel):
    choice: str
    note: str = ""


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "stillon"}


@app.get("/api/board")
def api_board() -> dict:
    return board()


@app.post("/api/night")
def api_night() -> dict:
    STORE.reset()
    result = run_night()
    return {"run": result.model_dump(), "board": board()}


@app.post("/api/reset")
def api_reset() -> dict:
    STORE.reset()
    return board()


@app.post("/api/decide/{household_id}")
def api_decide(household_id: str, body: DecisionBody) -> dict:
    try:
        outcome = resume_decision(household_id, body.choice, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"outcome": outcome, "board": board()}


@app.get("/api/household/{household_id}")
def api_household(household_id: str) -> dict:
    try:
        return STORE.household(household_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

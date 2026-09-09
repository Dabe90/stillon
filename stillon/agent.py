"""Build the Strands night-desk agent."""

from __future__ import annotations

import os
from pathlib import Path

from strands import Agent
from strands.session.file_session_manager import FileSessionManager

from .config import load_env
from .demo_model import NightDeskModel
from .hooks import CaseworkerGate
from .tools import (
    draft_packet,
    escalate_decision,
    get_household,
    get_priority_queue,
    match_documents,
    submit_packet,
)

SYSTEM_PROMPT = """You are StillOn, the overnight benefits desk at Harbor Light Food Bank.

You work one household at a time. Your job is to keep people on SNAP, Medicaid, or LIHEAP they already qualified for — not to chat, and not to invent documents.

Rules:
- Today is in the user prompt. Deadlines come from tools, never from your memory.
- Call get_household, then match_documents.
- If match_documents.complete is true and the household has not dropped, call draft_packet and stop. Do not submit.
- If anything needs a human (missing proof, stale proof, income change, unsigned packet, already dropped), call escalate_decision with a short question and two or three options. options_json MUST be a JSON array of objects like [{"id":"wait_for_docs","label":"Wait for the household"},{"id":"file_with_income_note","label":"File what we have"}]. Never wrap that array in another object. That is the only time a caseworker is woken.
- If the caseworker chooses a wait/hold option, stop. Do not draft.
- Never call submit_packet overnight.
- Never claim you filed with the state. This desk drafts packets and waits.
"""

SESSION_DIR = Path(__file__).resolve().parent.parent / "sessions"

load_env()


def bedrock_api_key() -> str:
    return os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()


def use_bedrock() -> bool:
    if bedrock_api_key():
        return True
    return os.environ.get("STILLON_USE_BEDROCK", "").strip() in {"1", "true", "yes"}


def build_model():
    if use_bedrock():
        try:
            from strands.models import BedrockModel
        except ImportError:
            from strands.models.bedrock import BedrockModel

        region = os.environ.get("AWS_REGION", "us-east-2")
        model_id = os.environ.get("STILLON_MODEL_ID", "amazon.nova-lite-v1:0")
        key = bedrock_api_key() or None
        return BedrockModel(model_id=model_id, region_name=region, api_key=key)
    return NightDeskModel()


def model_name() -> str:
    if use_bedrock():
        return os.environ.get("STILLON_MODEL_ID", "amazon.nova-lite-v1:0")
    return "stillon-night-desk-local"


def build_agent(session_id: str) -> Agent:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    session_manager = FileSessionManager(session_id=session_id, storage_dir=str(SESSION_DIR))
    return Agent(
        agent_id="stillon-night-desk",
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_priority_queue,
            get_household,
            match_documents,
            draft_packet,
            escalate_decision,
            submit_packet,
        ],
        hooks=[CaseworkerGate()],
        session_manager=session_manager,
        callback_handler=None,
    )

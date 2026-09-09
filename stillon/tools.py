"""Narrow tools. The model composes them; Python owns deadlines, matching, and files."""

from __future__ import annotations

import json

from strands import tool

from .clock import desk_date
from .deadlines import active_notice
from .matching import match_notice
from .packet import build_packet
from .store import STORE


@tool
def get_priority_queue() -> str:
    """Return the caseload ranked by drop date. Quiet households are included so you can skip them."""
    rows = []
    pending_ids = {p.household_id for p in STORE.pending()}
    ready_ids = {p.household_id for p in STORE.packets() if p.status == "drafted"}
    for case in STORE.ranked():
        rows.append(
            {
                **case.model_dump(),
                "already_pending": case.household_id in pending_ids,
                "packet_ready": case.household_id in ready_ids,
            }
        )
    return json.dumps({"desk_date": desk_date().isoformat(), "cases": rows})


@tool
def get_household(household_id: str) -> str:
    """Load one household file: people, enrollments, documents, notices."""
    hh = STORE.household(household_id)
    return hh.model_dump_json()


@tool
def match_documents(household_id: str, program: str) -> str:
    """Match the file against the latest notice. Deadlines and freshness are computed in code, not guessed."""
    hh = STORE.household(household_id)
    notice = active_notice(hh, program)
    if notice is None:
        return json.dumps({"error": "No notice on file for that program.", "complete": True, "gaps": []})
    report = match_notice(hh, notice)
    ranked = next(c for c in STORE.ranked() if c.household_id == household_id and c.program == program)
    payload = report.model_dump()
    if ranked.days_until_drop < 0:
        payload["human_reasons"] = list(payload.get("human_reasons") or []) + [
            "Benefits already dropped. Expedited re-application may be needed."
        ]
        payload["complete"] = False
    payload["drop_on"] = ranked.drop_on
    payload["days_until_drop"] = ranked.days_until_drop
    payload["display_name"] = hh.display_name
    payload["notice_id"] = notice.notice_id
    payload["band"] = ranked.band.value
    return json.dumps(payload)


@tool
def draft_packet(household_id: str, program: str, decision_note: str = "") -> str:
    """Assemble a recertification PDF from matched evidence. Safe to run without a human. Does not file."""
    hh = STORE.household(household_id)
    notice = active_notice(hh, program)
    if notice is None:
        return json.dumps({"error": "No notice to packetize."})
    packet = build_packet(hh, notice, decision_note=decision_note)
    STORE.add_packet(packet)
    return packet.model_dump_json()


@tool
def escalate_decision(
    household_id: str,
    program: str,
    question: str,
    why_human: str,
    options_json: str,
    chosen: str = "",
    note: str = "",
) -> str:
    """Ping a caseworker with a real decision. Use only when the packet cannot be completed safely without a human choice. options_json is a JSON list of {id, label}. Leave chosen empty; the night desk fills it after a human answers."""
    if not chosen:
        return json.dumps(
            {
                "status": "awaiting_caseworker",
                "household_id": household_id,
                "program": program,
                "question": question,
                "why_human": why_human,
                "options": json.loads(options_json),
            }
        )
    STORE.apply_decision_side_effects(household_id, chosen)
    STORE.clear_pending(household_id)
    return json.dumps(
        {
            "status": "decided",
            "choice": chosen,
            "note": note,
            "household_id": household_id,
            "program": program,
        }
    )


@tool
def submit_packet(household_id: str, note: str = "") -> str:
    """File a drafted packet. Irreversible in this demo. Only after a caseworker chooses to submit."""
    packet = STORE.mark_submitted(household_id, note=note)
    return packet.model_dump_json()

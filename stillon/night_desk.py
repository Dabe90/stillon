"""Run the overnight caseload. Quiet households are skipped."""

from __future__ import annotations

import json
import uuid
from typing import Any

from .agent import build_agent, model_name
from .clock import desk_date
from .deadlines import active_notice
from .hooks import normalize_options
from .models import DecisionOption, NightRunResult, PendingDecision, UrgencyBand
from .store import STORE, utc_now


def _interrupt_payload(interrupt) -> dict[str, Any]:
    reason = interrupt.reason
    if isinstance(reason, str):
        try:
            reason = json.loads(reason)
        except json.JSONDecodeError:
            reason = {"question": reason}
    return reason if isinstance(reason, dict) else {"question": str(reason)}


def _work_prompt(household_id: str, program: str) -> str:
    hh = STORE.household(household_id)
    ranked = next(c for c in STORE.ranked() if c.household_id == household_id and c.program == program)
    notice = active_notice(hh, program)
    notice_line = f"Notice {notice.notice_id} due {notice.due_on}." if notice else "No notice on file."
    return (
        f"Work this household overnight. Today is {desk_date().isoformat()}. "
        f"household_id {household_id} {hh.display_name} program {program}. "
        f"Drop date {ranked.drop_on} ({ranked.days_until_drop} days, band {ranked.band.value}). "
        f"{notice_line} "
        "Assemble a packet if you can. Escalate only if a human must choose. Do not submit."
    )


def _should_work(case) -> bool:
    if case.band is UrgencyBand.DROPPED:
        return True
    if case.why_human:
        return True
    return case.days_until_drop <= 12


def run_night() -> NightRunResult:
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    ranked = STORE.ranked()
    work = [c for c in ranked if _should_work(c)]
    quiet = [c for c in ranked if c not in work]
    briefs: list[dict[str, Any]] = []
    pending: list[PendingDecision] = []

    # Fresh night: drop leftover pending from a previous demo unless already answered.
    for old in STORE.pending():
        STORE.clear_pending(old.household_id)

    for case in work:
        session_id = f"{run_id}-{case.household_id}-{case.program}"
        agent = build_agent(session_id)
        try:
            result = agent(_work_prompt(case.household_id, case.program))
        except Exception as exc:
            briefs.append(
                {
                    "household_id": case.household_id,
                    "program": case.program,
                    "status": "error",
                    "session_id": session_id,
                    "error": str(exc)[:300],
                }
            )
            continue
        stop = getattr(result, "stop_reason", None)
        if stop == "interrupt":
            for interrupt in result.interrupts:
                reason = _interrupt_payload(interrupt)
                decision = PendingDecision(
                    interrupt_id=interrupt.id,
                    interrupt_name=interrupt.name,
                    household_id=reason.get("household_id") or case.household_id,
                    display_name=reason.get("display_name") or case.display_name,
                    program=reason.get("program") or case.program,
                    drop_on=reason.get("drop_on") or case.drop_on,
                    days_until_drop=int(reason.get("days_until_drop") or case.days_until_drop),
                    question=reason.get("question") or "A caseworker decision is required.",
                    options=[DecisionOption.model_validate(o) for o in normalize_options(reason.get("options"))],
                    why_human=reason.get("why_human") or "",
                    tool=reason.get("tool") or "escalate_decision",
                    run_id=run_id,
                    created_at=utc_now(),
                )
                STORE.save_pending(decision)
                pending.append(decision)
                briefs.append(
                    {
                        "household_id": case.household_id,
                        "program": case.program,
                        "status": "needs_you",
                        "session_id": session_id,
                        "interrupt_id": interrupt.id,
                    }
                )
        else:
            packet = next((p for p in STORE.packets() if p.household_id == case.household_id), None)
            briefs.append(
                {
                    "household_id": case.household_id,
                    "program": case.program,
                    "status": "ready" if packet else "worked",
                    "session_id": session_id,
                    "packet": packet.path if packet else None,
                }
            )

    summary = NightRunResult(
        run_id=run_id,
        desk_date=desk_date().isoformat(),
        quiet=len(quiet),
        ready=sum(1 for b in briefs if b["status"] == "ready"),
        needs_you=len(pending),
        dropped=sum(1 for c in ranked if c.band is UrgencyBand.DROPPED),
        briefs=briefs,
        pending=pending,
        model_name=model_name(),
    )
    STORE.record_run(
        {
            **summary.model_dump(),
            "sessions": {b["household_id"] + ":" + b["program"]: b["session_id"] for b in briefs},
        }
    )
    return summary


def resume_decision(household_id: str, choice: str, note: str = "") -> dict[str, Any]:
    latest = STORE.latest_run()
    if not latest:
        raise RuntimeError("No night run to resume.")
    pending = next((p for p in STORE.pending() if p.household_id == household_id), None)
    if not pending:
        raise KeyError(household_id)
    session_id = latest.get("sessions", {}).get(f"{household_id}:{pending.program}")
    if not session_id:
        # fallback: search briefs
        for brief in latest.get("briefs", []):
            if brief.get("household_id") == household_id:
                session_id = brief.get("session_id")
                break
    if not session_id:
        raise RuntimeError("Could not find the paused Strands session.")

    agent = build_agent(session_id)
    responses = [
        {
            "interruptResponse": {
                "interruptId": pending.interrupt_id,
                "response": json.dumps({"choice": choice, "note": note}),
            }
        }
    ]
    result = agent(responses)
    packet = next((p for p in STORE.packets() if p.household_id == household_id), None)
    still = next((p for p in STORE.pending() if p.household_id == household_id), None)
    return {
        "stop_reason": getattr(result, "stop_reason", None),
        "packet": packet.model_dump() if packet else None,
        "still_pending": still.model_dump() if still else None,
        "choice": choice,
    }


def _named_packets(packets) -> list[dict[str, Any]]:
    named = []
    for p in packets:
        dump = p.model_dump()
        try:
            dump["display_name"] = STORE.household(p.household_id).display_name
        except KeyError:
            dump["display_name"] = p.household_id
        named.append(dump)
    return named


def board() -> dict[str, Any]:
    ranked = STORE.ranked()
    pending = STORE.pending()
    packets = STORE.packets()
    pending_ids = {p.household_id for p in pending}
    packet_by_hh = {p.household_id: p for p in packets}
    quiet = [c for c in ranked if not _should_work(c)]
    ready_packets = _named_packets([p for p in packets if p.status == "drafted"])
    return {
        "org": STORE.org(),
        "desk_date": desk_date().isoformat(),
        "model_name": model_name(),
        "last_run": STORE.latest_run(),
        "counts": {
            "caseload": len(ranked),
            "quiet": len(quiet),
            "needs_you": len(pending),
            "ready": len(ready_packets),
            "submitted": sum(1 for p in packets if p.status == "submitted"),
            "dropped": sum(1 for c in ranked if c.band is UrgencyBand.DROPPED),
        },
        "needs_you": [p.model_dump() for p in pending],
        "ready": ready_packets,
        "submitted": _named_packets([p for p in packets if p.status == "submitted"]),
        "caseload": [
            {
                **c.model_dump(),
                "pending": c.household_id in pending_ids,
                "packet": packet_by_hh.get(c.household_id).model_dump() if c.household_id in packet_by_hh else None,
            }
            for c in ranked
        ],
    }

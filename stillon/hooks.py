"""Human authority sits outside the model. Gated tools pause via Strands interrupts."""

from __future__ import annotations

import json
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry

from .deadlines import active_notice
from .matching import match_notice
from .policy import suggested_escalation
from .store import STORE

GATED = {"escalate_decision", "submit_packet"}


def normalize_options(raw: Any) -> list[dict[str, str]]:
    """Nova sometimes sends labels, a JSON string, or a dict instead of [{id, label}]."""
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
            raw = parts
    if isinstance(raw, dict):
        if "id" in raw and "label" in raw:
            raw = [raw]
        elif "options" in raw:
            return normalize_options(raw["options"])
        elif "options_json" in raw:
            return normalize_options(raw["options_json"])
        else:
            raw = [{"id": str(k), "label": str(v)} for k, v in raw.items()]
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            oid = str(item.get("id") or item.get("value") or item.get("label") or f"option_{len(out)+1}")
            label = str(item.get("label") or item.get("text") or oid)
            out.append({"id": oid, "label": label})
        elif isinstance(item, str) and item.strip() and item.strip().lower() != "options":
            slug = (
                item.lower()
                .replace(" ", "_")
                .replace("-", "_")
            )
            slug = "".join(ch for ch in slug if ch.isalnum() or ch == "_")[:40] or f"option_{len(out)+1}"
            out.append({"id": slug, "label": item.strip()})
    if not out:
        out = [
            {"id": "file_with_income_note", "label": "File what we have"},
            {"id": "wait_for_docs", "label": "Wait for the household"},
        ]
    return out[:4]


def question_looks_broken(question: str) -> bool:
    text = (question or "").strip()
    if len(text) < 20:
        return True
    return text.startswith("{") or text.startswith("[")


def options_look_broken(options: list[dict[str, str]]) -> bool:
    if len(options) < 2:
        return True
    for opt in options:
        label = str(opt.get("label") or "")
        oid = str(opt.get("id") or "").lower()
        if oid in {"options", "options_json"}:
            return True
        if any(ch in label for ch in "{[]}"):
            return True
        if label.strip().lower() in {"options", "option"}:
            return True
        if len(label) > 90:
            return True
    return False


def policy_copy(household_id: str, program: str, display: str) -> dict[str, Any] | None:
    """Buttons and fallback copy come from Python, not the model."""
    try:
        hh = STORE.household(household_id)
    except KeyError:
        return None
    ranked = next(
        (c for c in STORE.ranked() if c.household_id == household_id and (not program or c.program == program)),
        None,
    )
    use_program = program or (ranked.program if ranked else "")
    if not use_program:
        return None
    notice = active_notice(hh, use_program)
    if notice is None:
        return None
    report = match_notice(hh, notice)
    if ranked and ranked.days_until_drop < 0:
        report.human_reasons = list(report.human_reasons) + ["Benefits already dropped."]
    return suggested_escalation(
        report,
        drop_on=ranked.drop_on if ranked else notice.drop_on,
        days=ranked.days_until_drop if ranked else 0,
        display_name=display,
    )


def _parse_response(response: Any) -> dict:
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"choice": response}
    return {"choice": str(response)}


class CaseworkerGate(HookProvider):
    """Pause before a caseworker-only tool. On resume, inject the chosen option into the tool input."""

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.gate)

    def gate(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        if name not in GATED:
            return

        payload = dict(event.tool_use.get("input") or {})
        household_id = payload.get("household_id", "")
        try:
            display = STORE.household(household_id).display_name
        except KeyError:
            display = household_id

        program = payload.get("program", "")
        ranked = next(
            (
                c
                for c in STORE.ranked()
                if c.household_id == household_id and (not program or c.program == program)
            ),
            None,
        )

        options_raw = payload.get("options_json") or payload.get("options") or "[]"
        options = normalize_options(options_raw)
        question = payload.get("question") or f"Submit the packet for {display}?"
        why_human = payload.get("why_human") or "Filing is a caseworker act."
        if name == "submit_packet":
            options = [
                {"id": "submit", "label": "Submit this packet"},
                {"id": "hold", "label": "Hold — do not file yet"},
            ]
        else:
            suggestion = policy_copy(household_id, program or (ranked.program if ranked else ""), display)
            if suggestion:
                options = suggestion["options"]
                if question_looks_broken(question):
                    question = suggestion["question"]
                why_human = why_human if not question_looks_broken(why_human) else suggestion["why_human"]
            elif options_look_broken(options):
                options = [
                    {"id": "file_with_income_note", "label": "File what we have"},
                    {"id": "wait_for_docs", "label": "Wait for the household"},
                ]

        reason = {
            "tool": name,
            "household_id": household_id,
            "display_name": display,
            "program": program or (ranked.program if ranked else ""),
            "drop_on": ranked.drop_on if ranked else "",
            "days_until_drop": ranked.days_until_drop if ranked else 0,
            "question": question,
            "why_human": why_human,
            "options": options,
        }

        response = event.interrupt(f"stillon-{name}", reason=reason)
        parsed = _parse_response(response)
        choice = parsed.get("choice", "")
        note = parsed.get("note", "")

        if name == "submit_packet" and choice != "submit":
            event.cancel_tool = "Caseworker held the packet."
            return

        event.tool_use.setdefault("input", {})
        event.tool_use["input"]["chosen"] = choice
        event.tool_use["input"]["note"] = note
        if name == "submit_packet":
            event.tool_use["input"]["approved"] = True

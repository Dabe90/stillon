"""Local model so the night desk runs before Bedrock is enabled.

This is a real Strands Model provider. It streams tool-use events the same
way Bedrock does. Swap it for BedrockModel without changing tools or hooks.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterable
from typing import Any, Optional
from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

from .matching import match_notice
from .deadlines import active_notice
from .policy import suggested_escalation
from .store import STORE


def _text_of(messages: Messages) -> str:
    chunks: list[str] = []
    for message in messages:
        for block in message.get("content", []):
            if "text" in block:
                chunks.append(block["text"])
    return "\n".join(chunks)


def _called(messages: Messages) -> list[str]:
    names: list[str] = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            tool = block.get("toolUse")
            if tool:
                names.append(tool["name"])
    return names


def _last_tool_result_json(messages: Messages, name: str) -> dict | None:
    use_ids = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            tool = block.get("toolUse")
            if tool and tool["name"] == name:
                use_ids.append(tool["toolUseId"])
    if not use_ids:
        return None
    want = use_ids[-1]
    for message in messages:
        for block in message.get("content", []):
            result = block.get("toolResult")
            if not result or result.get("toolUseId") != want:
                continue
            parts = []
            for item in result.get("content", []):
                if "text" in item:
                    parts.append(item["text"])
            raw = "".join(parts)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
    return None


def _ids_from_text(text: str) -> tuple[str, str]:
    household_id = ""
    program = ""
    for token in text.replace("\n", " ").split():
        if token.startswith("hh-"):
            household_id = token.strip(".,;:")
        if token in {"SNAP", "MEDICAID", "LIHEAP"}:
            program = token
    return household_id, program


def _plan(messages: Messages) -> tuple[str, dict] | tuple[str, str]:
    text = _text_of(messages)
    called = _called(messages)
    household_id, program = _ids_from_text(text)
    if not household_id:
        return ("text", "No household_id in the prompt. Call get_priority_queue if you need the full board.")

    if "get_household" not in called:
        return ("get_household", {"household_id": household_id})

    if "match_documents" not in called:
        if not program:
            hh = STORE.household(household_id)
            program = hh.enrollments[0].program
        return ("match_documents", {"household_id": household_id, "program": program})

    report = _last_tool_result_json(messages, "match_documents") or {}
    complete = bool(report.get("complete"))
    if not complete and "escalate_decision" not in called:
        hh = STORE.household(household_id)
        notice = active_notice(hh, report.get("program") or program)
        from .models import MatchReport

        parsed = MatchReport.model_validate(
            {k: report[k] for k in ("household_id", "program", "complete", "gaps", "matched", "human_reasons") if k in report}
            if report
            else match_notice(hh, notice).model_dump()
            if notice
            else {
                "household_id": household_id,
                "program": program or "SNAP",
                "complete": False,
                "gaps": [],
                "matched": [],
                "human_reasons": ["Needs a caseworker."],
            }
        )
        suggestion = suggested_escalation(
            parsed,
            drop_on=str(report.get("drop_on", "")),
            days=int(report.get("days_until_drop") or 0),
            display_name=str(report.get("display_name") or hh.display_name),
        )
        return (
            "escalate_decision",
            {
                "household_id": household_id,
                "program": parsed.program,
                "question": suggestion["question"],
                "why_human": suggestion["why_human"],
                "options_json": json.dumps(suggestion["options"]),
            },
        )

    if "draft_packet" not in called:
        choice = ""
        esc = _last_tool_result_json(messages, "escalate_decision") or {}
        if esc.get("choice"):
            choice = f"Caseworker chose {esc['choice']}. {esc.get('note') or ''}".strip()
        wait_choices = {"wait_for_docs", "wait_for_household", "text_for_current", "hold_for_confirmation", "home_visit"}
        if esc.get("choice") in wait_choices:
            return (
                "text",
                f"Night desk parked {household_id}. Caseworker chose to wait: {esc.get('choice')}.",
            )
        use_program = report.get("program") or program
        return (
            "draft_packet",
            {
                "household_id": household_id,
                "program": use_program,
                "decision_note": choice,
            },
        )

    return ("text", f"Night work for {household_id} is finished. Packet drafted or waiting on a human.")


def _tool_events(name: str, arguments: dict) -> list[StreamEvent]:
    tool_use_id = f"tool-{uuid.uuid4().hex[:12]}"
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"toolUse": {"toolUseId": tool_use_id, "name": name}}}},
        {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(arguments)}}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "tool_use"}},
    ]


def _text_events(text: str) -> list[StreamEvent]:
    return [
        {"messageStart": {"role": "assistant"}},
        {"contentBlockStart": {"start": {"text": ""}}},
        {"contentBlockDelta": {"delta": {"text": text}}},
        {"contentBlockStop": {}},
        {"messageStop": {"stopReason": "end_turn"}},
    ]


class NightDeskModel(Model):
    """Scripted Strands model used when Bedrock credentials are not configured."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {"model_id": "stillon-night-desk-local"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        if False:
            yield {}
        raise NotImplementedError("StillOn night desk does not use structured_output")

    async def stream(
        self,
        messages: Messages,
        tool_specs: Optional[list[ToolSpec]] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        action = _plan(messages)
        if action[0] == "text":
            events = _text_events(str(action[1]))
        else:
            events = _tool_events(action[0], action[1])  # type: ignore[arg-type]
        for event in events:
            yield event

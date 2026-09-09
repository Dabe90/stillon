"""Suggested caseworker questions. Used by the local demo model; Bedrock writes its own."""

from __future__ import annotations

from .models import MatchReport


def suggested_escalation(report: MatchReport, drop_on: str, days: int, display_name: str) -> dict:
    if any("already dropped" in r.lower() or "dropped" in r.lower() for r in report.human_reasons):
        return {
            "question": (
                f"{display_name} SNAP already closed. Open an expedited re-application today, "
                "or wait for the household to come to the pantry?"
            ),
            "why_human": "Benefits already lapsed. Filing vs waiting is a caseworker call.",
            "options": [
                {"id": "expedited_reapply", "label": "Start expedited SNAP re-application"},
                {"id": "wait_for_household", "label": "Wait — they need to walk in"},
            ],
        }

    if any("income" in r.lower() for r in report.human_reasons):
        return {
            "question": (
                f"{display_name} reported more income. File with an income-change addendum, "
                "or hold the packet until the household confirms the new hours are permanent?"
            ),
            "why_human": "An income change can change eligibility. The agent cannot decide that.",
            "options": [
                {"id": "file_with_income_note", "label": "File with income-change addendum"},
                {"id": "hold_for_confirmation", "label": "Hold until household confirms hours"},
            ],
        }

    if any(g.doc_type.value == "signature" for g in report.gaps):
        return {
            "question": (
                f"{display_name} Medicaid packet is otherwise complete. Signature is missing. "
                f"Drop date is {drop_on} ({days} days). Text Denise to come sign, or send a worker out?"
            ),
            "why_human": "A signature is a legal act. The agent cannot sign.",
            "options": [
                {"id": "collect_signature", "label": "Text her to come sign today"},
                {"id": "home_visit", "label": "Schedule a home visit for the signature"},
            ],
        }

    pay_gap = next((g for g in report.gaps if g.doc_type.value == "paystub"), None)
    if pay_gap and pay_gap.have_instead:
        return {
            "question": (
                f"{display_name} SNAP is due {drop_on} ({days} days). "
                f"We have {pay_gap.have_instead}, not a current stub. "
                "File with a gap note, or text for the August stub?"
            ),
            "why_human": "Stale wages can trigger a denial. A human chooses the risk.",
            "options": [
                {"id": "accept_stale_paystub", "label": "File the stale stub with a gap note"},
                {"id": "text_for_current", "label": "Text for the current stub and wait"},
            ],
        }

    if pay_gap and not pay_gap.have_instead:
        return {
            "question": (
                f"{display_name} has no paystubs. The notice says a Social Security award letter can stand in. "
                "Use the award letter on file, or wait for new proof?"
            ),
            "why_human": "Substituting an award letter for wages is a judgment call.",
            "options": [
                {"id": "use_award_letter", "label": "Use SSA award letter as income proof"},
                {"id": "wait_for_docs", "label": "Wait — do not file incomplete"},
            ],
        }

    bill_gap = next(
        (g for g in report.gaps if g.doc_type.value in {"utility_bill", "proof_of_address"}),
        None,
    )
    if bill_gap:
        return {
            "question": (
                f"{display_name} is missing current {bill_gap.doc_type.value.replace('_', ' ')}. "
                f"On file: {bill_gap.have_instead or 'nothing'}. Waive freshness, or wait for a new bill?"
            ),
            "why_human": "Waiving a document requirement is a caseworker call.",
            "options": [
                {"id": "accept_stale_bill", "label": "Waive freshness and file"},
                {"id": "wait_for_docs", "label": "Wait for a current bill"},
            ],
        }

    return {
        "question": f"{display_name} needs a caseworker look before filing. Drop date {drop_on}.",
        "why_human": "; ".join(report.human_reasons) or "Unspecified gap.",
        "options": [
            {"id": "file_with_income_note", "label": "File what we have"},
            {"id": "wait_for_docs", "label": "Wait"},
        ],
    }

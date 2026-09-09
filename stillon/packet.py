"""Assemble a recertification packet PDF. This is real work, not a chat reply."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .clock import desk_date
from .matching import match_notice
from .models import Household, Notice, PacketRecord
from .store import PACKETS_DIR, utc_now


def build_packet(household: Household, notice: Notice, decision_note: str = "") -> PacketRecord:
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    packet_id = f"{household.household_id}-{notice.program.lower()}-{desk_date().isoformat()}"
    path = PACKETS_DIR / f"{packet_id}.pdf"
    report = match_notice(household, notice)

    styles = getSampleStyleSheet()
    title = ParagraphStyle("DeskTitle", parent=styles["Heading1"], fontSize=16, spaceAfter=8)
    h2 = ParagraphStyle("DeskH2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("DeskBody", parent=styles["Normal"], fontSize=10, leading=14)

    story = [
        Paragraph("Harbor Light Food Bank — StillOn night desk", title),
        Paragraph(f"Recertification packet · {notice.program} · desk date {desk_date().isoformat()}", body),
        Spacer(1, 0.15 * inch),
        Paragraph("Household", h2),
        Paragraph(f"<b>{household.display_name}</b> · {household.city} · {household.phone}", body),
        Paragraph("Members: " + ", ".join(f"{p.name} ({p.role})" for p in household.members), body),
        Paragraph("Notice", h2),
        Paragraph(f"Notice {notice.notice_id} due {notice.due_on}. Drop date {notice.drop_on}.", body),
        Paragraph(notice.summary, body),
        Paragraph("Matched evidence", h2),
    ]
    if report.matched:
        for label in report.matched:
            story.append(Paragraph(f"• {label}", body))
    else:
        story.append(Paragraph("None matched.", body))

    if report.gaps:
        story.append(Paragraph("Gaps / waivers", h2))
        for gap in report.gaps:
            extra = f" (on file: {gap.have_instead})" if gap.have_instead else ""
            story.append(Paragraph(f"• {gap.reason}{extra}", body))

    if decision_note:
        story.append(Paragraph("Caseworker decision", h2))
        story.append(Paragraph(decision_note, body))

    story.append(Paragraph("Filing note", h2))
    story.append(
        Paragraph(
            "This packet was assembled overnight by StillOn (Strands Agents SDK) for a human "
            "caseworker to review. It is a demo packet, not a state filing.",
            body,
        )
    )

    doc = SimpleDocTemplate(str(path), pagesize=letter, title=f"StillOn {notice.program} packet")
    doc.build(story)

    rel = f"/static/packets/{path.name}"
    return PacketRecord(
        packet_id=packet_id,
        household_id=household.household_id,
        program=notice.program,
        path=rel,
        created_at=utc_now(),
        status="drafted",
        decision_note=decision_note,
    )

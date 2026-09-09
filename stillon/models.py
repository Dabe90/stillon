"""Caseload types. These are application records, not model output."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


Program = Literal["SNAP", "MEDICAID", "LIHEAP"]


class UrgencyBand(str, Enum):
    DROPPED = "dropped"
    TODAY = "today"
    THIS_WEEK = "this_week"
    WINDOW = "window"
    QUIET = "quiet"


class DocType(str, Enum):
    PHOTO_ID = "photo_id"
    PAYSTUB = "paystub"
    PROOF_OF_ADDRESS = "proof_of_address"
    UTILITY_BILL = "utility_bill"
    SSN_CARD = "ssn_card"
    BIRTH_CERTIFICATE = "birth_certificate"
    SIGNATURE = "signature"


class Document(BaseModel):
    doc_id: str
    doc_type: DocType
    label: str
    issued_on: str
    notes: str = ""
    current_enough: bool = True


class Person(BaseModel):
    name: str
    role: str
    age: int | None = None


class Notice(BaseModel):
    notice_id: str
    program: Program
    received_on: str
    due_on: str
    drop_on: str
    required_documents: list[DocType]
    summary: str
    source: str = "mailroom"


class Enrollment(BaseModel):
    program: Program
    case_number: str
    next_recert_on: str
    last_submitted_on: str | None = None
    income_changed: bool = False
    signature_on_file: bool = True


class Household(BaseModel):
    household_id: str
    display_name: str
    members: list[Person]
    city: str
    phone: str
    language: str = "en"
    notes: str = ""
    enrollments: list[Enrollment]
    documents: list[Document]
    notices: list[Notice]
    assigned_caseworker: str = "Jordan Hale"


class MatchGap(BaseModel):
    doc_type: DocType
    reason: str
    have_instead: str | None = None


class MatchReport(BaseModel):
    household_id: str
    program: Program
    complete: bool
    gaps: list[MatchGap] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)
    human_reasons: list[str] = Field(default_factory=list)


class RankedCase(BaseModel):
    household_id: str
    display_name: str
    program: Program
    notice_id: str | None = None
    drop_on: str
    days_until_drop: int
    band: UrgencyBand
    human_needed: bool
    why_human: list[str] = Field(default_factory=list)
    quiet_reason: str | None = None


class DecisionOption(BaseModel):
    id: str
    label: str


class PendingDecision(BaseModel):
    interrupt_id: str
    interrupt_name: str
    household_id: str
    display_name: str
    program: Program
    drop_on: str
    days_until_drop: int
    question: str
    options: list[DecisionOption]
    why_human: str
    tool: str
    run_id: str
    created_at: str


class PacketRecord(BaseModel):
    packet_id: str
    household_id: str
    program: Program
    path: str
    created_at: str
    status: Literal["drafted", "submitted"] = "drafted"
    decision_note: str = ""


class NightRunResult(BaseModel):
    run_id: str
    desk_date: str
    quiet: int
    ready: int
    needs_you: int
    dropped: int
    briefs: list[dict[str, Any]] = Field(default_factory=list)
    pending: list[PendingDecision] = Field(default_factory=list)
    model_name: str = ""

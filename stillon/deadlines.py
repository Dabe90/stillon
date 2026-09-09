"""
Deterministic recertification calendar.

The model does not compute drop dates. These windows are encoded from
typical SNAP, Medicaid, and LIHEAP recertification practice so a caseworker
can trust the ranking even when the LLM is wrong about the story.

Sources (plain-language, not legal advice):
- SNAP recertification packets are commonly due 10 days from the notice,
  with certification periods often 6 months for many households.
- Medicaid renewals are typically annual, with a ~90 day renewal window
  and a response deadline printed on the notice.
- LIHEAP is seasonal; a missed packet means the household waits until the
  next fuel season.
"""

from __future__ import annotations

from .clock import days_until, parse_date
from .models import Enrollment, Household, Notice, RankedCase, UrgencyBand


RESPONSE_DAYS = {
    "SNAP": 10,
    "MEDICAID": 30,
    "LIHEAP": 15,
}

RECERT_CYCLE_DAYS = {
    "SNAP": 182,
    "MEDICAID": 365,
    "LIHEAP": 120,
}


def band_for(days: int) -> UrgencyBand:
    if days < 0:
        return UrgencyBand.DROPPED
    if days <= 1:
        return UrgencyBand.TODAY
    if days <= 7:
        return UrgencyBand.THIS_WEEK
    if days <= 21:
        return UrgencyBand.WINDOW
    return UrgencyBand.QUIET


def drop_date_for(enrollment: Enrollment, notice: Notice | None) -> str:
    if notice:
        return notice.drop_on
    return enrollment.next_recert_on


def active_notice(household: Household, program: str) -> Notice | None:
    matches = [n for n in household.notices if n.program == program]
    if not matches:
        return None
    return sorted(matches, key=lambda n: n.due_on, reverse=True)[0]


def rank_enrollment(household: Household, enrollment: Enrollment, today) -> RankedCase:
    notice = active_notice(household, enrollment.program)
    drop_on = drop_date_for(enrollment, notice)
    days = days_until(parse_date(drop_on), today)
    band = band_for(days)
    why: list[str] = []
    if enrollment.income_changed:
        why.append("Reported income change may change eligibility.")
    if not enrollment.signature_on_file:
        why.append("A wet signature is still required.")
    if band is UrgencyBand.DROPPED:
        why.append("Benefits already dropped. Expedited re-application may be needed.")

    human_needed = bool(why) or band in {
        UrgencyBand.DROPPED,
        UrgencyBand.TODAY,
        UrgencyBand.THIS_WEEK,
    }

    quiet_reason = None
    if band is UrgencyBand.QUIET and not why:
        quiet_reason = f"Next recert is {days} days out. No overnight work."
        human_needed = False

    return RankedCase(
        household_id=household.household_id,
        display_name=household.display_name,
        program=enrollment.program,
        notice_id=notice.notice_id if notice else None,
        drop_on=drop_on,
        days_until_drop=days,
        band=band,
        human_needed=human_needed,
        why_human=why,
        quiet_reason=quiet_reason,
    )


def rank_households(households: list[Household], today) -> list[RankedCase]:
    ranked: list[RankedCase] = []
    for hh in households:
        for enrollment in hh.enrollments:
            ranked.append(rank_enrollment(hh, enrollment, today))
    ranked.sort(key=lambda c: (c.days_until_drop, c.display_name))
    return ranked

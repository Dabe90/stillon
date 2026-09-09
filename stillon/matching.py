"""Match household files to what a notice actually asks for."""

from __future__ import annotations

from .clock import desk_date, parse_date
from .models import DocType, Household, MatchGap, MatchReport, Notice


PAYSTUB_FRESH_DAYS = 45
ADDRESS_FRESH_DAYS = 90


def _fresh(issued_on: str, max_age: int, today) -> bool:
    age = (today - parse_date(issued_on)).days
    return 0 <= age <= max_age


def match_notice(household: Household, notice: Notice, today=None) -> MatchReport:
    today = today or desk_date()
    gaps: list[MatchGap] = []
    matched: list[str] = []
    human: list[str] = []

    enrollment = next((e for e in household.enrollments if e.program == notice.program), None)
    if enrollment and enrollment.income_changed:
        human.append("Income changed since the last packet. A caseworker must decide whether to file as-is.")
    if enrollment and not enrollment.signature_on_file:
        human.append("Signature page is unsigned.")
        gaps.append(
            MatchGap(
                doc_type=DocType.SIGNATURE,
                reason="Notice requires a signed last page. None on file.",
            )
        )

    for required in notice.required_documents:
        if required == DocType.SIGNATURE:
            continue
        candidates = [d for d in household.documents if d.doc_type == required]
        if not candidates:
            gaps.append(MatchGap(doc_type=required, reason=f"No {required.value.replace('_', ' ')} in the file."))
            continue

        if required == DocType.PAYSTUB:
            current = [d for d in candidates if _fresh(d.issued_on, PAYSTUB_FRESH_DAYS, today)]
            if current:
                matched.extend(d.label for d in current)
            else:
                newest = max(candidates, key=lambda d: d.issued_on)
                gaps.append(
                    MatchGap(
                        doc_type=required,
                        reason=f"Paystub on file is from {newest.issued_on}, older than {PAYSTUB_FRESH_DAYS} days.",
                        have_instead=newest.label,
                    )
                )
                human.append("Stale paystub. File with a gap note, or wait for the current stub.")
            continue

        if required in {DocType.PROOF_OF_ADDRESS, DocType.UTILITY_BILL}:
            current = [d for d in candidates if _fresh(d.issued_on, ADDRESS_FRESH_DAYS, today)]
            if current:
                matched.extend(d.label for d in current)
            else:
                newest = max(candidates, key=lambda d: d.issued_on)
                label = "Address proof" if required == DocType.PROOF_OF_ADDRESS else "Utility bill"
                gaps.append(
                    MatchGap(
                        doc_type=required,
                        reason=f"{label} from {newest.issued_on} is older than {ADDRESS_FRESH_DAYS} days.",
                        have_instead=newest.label,
                    )
                )
            continue

        matched.extend(d.label for d in candidates)

    if gaps:
        human.append("Packet is incomplete until missing proof is waived or supplied.")

    # Deduplicate human reasons while keeping order
    seen: set[str] = set()
    unique_human = []
    for item in human:
        if item not in seen:
            seen.add(item)
            unique_human.append(item)

    return MatchReport(
        household_id=household.household_id,
        program=notice.program,
        complete=not gaps and not unique_human,
        gaps=gaps,
        matched=matched,
        human_reasons=unique_human,
    )

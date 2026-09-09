from datetime import date

from stillon.deadlines import active_notice
from stillon.matching import match_notice
from stillon.store import STORE


def test_stale_paystub_is_a_gap():
    STORE.reset()
    hh = STORE.household("hh-santos")
    notice = active_notice(hh, "SNAP")
    report = match_notice(hh, notice, today=date(2026, 9, 9))
    assert not report.complete
    assert any(g.doc_type.value == "paystub" for g in report.gaps)


def test_complete_medicaid_packet():
    STORE.reset()
    hh = STORE.household("hh-okonkwo")
    notice = active_notice(hh, "MEDICAID")
    report = match_notice(hh, notice, today=date(2026, 9, 9))
    assert report.complete
    assert not report.gaps


def test_income_change_forces_human():
    STORE.reset()
    hh = STORE.household("hh-whitaker")
    notice = active_notice(hh, "LIHEAP")
    report = match_notice(hh, notice, today=date(2026, 9, 9))
    assert not report.complete
    assert any("income" in r.lower() for r in report.human_reasons)

"""Prove the real Strands Agent loop, interrupt, and resume — no Bedrock required."""

from stillon.night_desk import resume_decision, run_night
from stillon.store import STORE


def test_night_desk_interrupts_only_for_real_decisions():
    STORE.reset()
    result = run_night()
    assert result.needs_you >= 4
    assert result.ready >= 1
    ids = {p.household_id for p in result.pending}
    assert "hh-santos" in ids
    assert "hh-okonkwo" not in ids
    assert "hh-vega" not in ids


def test_caseworker_resume_finishes_packet():
    STORE.reset()
    run_night()
    pending = next(p for p in STORE.pending() if p.household_id == "hh-santos")
    assert pending.interrupt_id
    outcome = resume_decision("hh-santos", "accept_stale_paystub", "File with gap note")
    assert outcome["choice"] == "accept_stale_paystub"
    packets = [p for p in STORE.packets() if p.household_id == "hh-santos"]
    assert packets, outcome

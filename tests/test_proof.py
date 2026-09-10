from stillon.models import UrgencyBand
from stillon.night_desk import board
from stillon.store import STORE


def test_fraser_is_quiet_before_any_night_run():
    STORE.reset()
    payload = board()
    assert payload["last_run"] is None or payload.get("last_run") in (None, {})

    fraser = next(c for c in payload["caseload"] if c["household_id"] == "hh-fraser")
    assert fraser["band"] is UrgencyBand.QUIET or fraser["band"] == UrgencyBand.QUIET.value
    assert fraser["days_until_drop"] == 60
    assert fraser["quiet_reason"] == "Next recert is 60 days out. No overnight work."
    assert not fraser["pending"]
    assert fraser["packet"] is None

    proof = payload["proof"]
    assert proof["household_id"] == "hh-fraser"
    assert proof["days_until_drop"] == 60
    assert proof["source"] == "deadlines.py"
    assert "Fraser" in proof["headline"]
    assert "model never opened" in proof["detail"].lower()


def test_fraser_stays_quiet_after_local_night():
    from stillon.night_desk import run_night

    STORE.reset()
    result = run_night()
    assert result.quiet >= 1
    payload = board()
    fraser = next(c for c in payload["caseload"] if c["household_id"] == "hh-fraser")
    assert fraser["band"] in {UrgencyBand.QUIET, UrgencyBand.QUIET.value, "quiet"}
    ids = {row["household_id"] for row in payload["needs_you"]}
    assert "hh-fraser" not in ids
    assert payload["proof"]["household_id"] == "hh-fraser"

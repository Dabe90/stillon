from datetime import date

from stillon.clock import days_until
from stillon.deadlines import band_for, rank_households
from stillon.models import UrgencyBand
from stillon.store import STORE


def test_band_edges():
    assert band_for(-1) is UrgencyBand.DROPPED
    assert band_for(0) is UrgencyBand.TODAY
    assert band_for(7) is UrgencyBand.THIS_WEEK
    assert band_for(8) is UrgencyBand.WINDOW
    assert band_for(40) is UrgencyBand.QUIET


def test_santos_is_this_week():
    STORE.reset()
    today = date(2026, 9, 9)
    ranked = rank_households(STORE.households(), today)
    santos = next(c for c in ranked if c.household_id == "hh-santos")
    assert santos.days_until_drop == days_until(date(2026, 9, 13), today)
    assert santos.band is UrgencyBand.THIS_WEEK
    hale = next(c for c in ranked if c.household_id == "hh-hale")
    assert hale.band is UrgencyBand.DROPPED

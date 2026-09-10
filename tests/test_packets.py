from stillon.artifacts import packet_bytes, parse_packet_name
from stillon.store import STORE


def test_packet_name_parse():
    assert parse_packet_name("hh-vega-snap-2026-09-09.pdf") == ("hh-vega", "SNAP")
    assert parse_packet_name("hh-okonkwo-medicaid-2026-09-09.pdf") == ("hh-okonkwo", "MEDICAID")


def test_rebuild_ready_pdf_from_seed():
    STORE.reset()
    raw = packet_bytes("hh-vega-snap-2026-09-09.pdf")
    assert raw[:4] == b"%PDF"
    assert len(raw) > 400

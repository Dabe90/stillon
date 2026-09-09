from stillon.hooks import normalize_options, options_look_broken, policy_copy, question_looks_broken
from stillon.store import STORE


def test_normalize_json_string_list():
    raw = '[{"id": "wait_for_docs", "label": "Wait"}, {"id": "file_with_income_note", "label": "File"}]'
    out = normalize_options(raw)
    assert [o["id"] for o in out] == ["wait_for_docs", "file_with_income_note"]


def test_normalize_nova_options_wrapper():
    raw = {"options": '[{"id": "a", "label": "Hold"}, {"id": "b", "label": "File"}]'}
    out = normalize_options(raw)
    assert [o["id"] for o in out] == ["a", "b"]


def test_broken_question_and_options():
    assert question_looks_broken("{not a question}")
    assert question_looks_broken("short")
    assert options_look_broken([{"id": "options", "label": "options"}])
    assert not options_look_broken(
        [
            {"id": "wait_for_docs", "label": "Wait for the household"},
            {"id": "file_with_income_note", "label": "File what we have"},
        ]
    )


def test_policy_buttons_for_stale_paystub():
    STORE.reset()
    copy = policy_copy("hh-santos", "SNAP", "Santos")
    assert copy
    ids = {o["id"] for o in copy["options"]}
    assert "accept_stale_paystub" in ids
    assert "text_for_current" in ids

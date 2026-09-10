import json

import pytest

from coach import tools


@pytest.fixture(autouse=True)
def isolated_deck(tmp_path, monkeypatch):
    monkeypatch.setenv("COACH_DATA_DIR", str(tmp_path))
    tools._deck = None
    yield
    tools._deck = None


def test_tool_schemas_are_generated():
    for tool in tools.TOOLS:
        schema = tool.to_dict()
        assert schema["name"]
        assert schema["description"]
        assert schema["input_schema"]["type"] == "object"


def test_flashcard_flow():
    added = json.loads(tools.add_flashcard.call({"word": "猫", "reading": "ねこ", "meaning": "cat"}))
    assert added["already_existed"] is False

    due = json.loads(tools.list_due_cards.call({"limit": 5}))
    assert due["count"] == 1
    card_id = due["cards"][0]["card_id"]

    reviewed = json.loads(tools.record_review.call({"card_id": card_id, "grade": 5}))
    assert reviewed["interval_days"] == 1

    assert json.loads(tools.list_due_cards.call({}))["count"] == 0
    assert json.loads(tools.deck_stats.call({}))["total"] == 1


def test_record_review_bad_id():
    result = json.loads(tools.record_review.call({"card_id": "nope", "grade": 3}))
    assert "error" in result

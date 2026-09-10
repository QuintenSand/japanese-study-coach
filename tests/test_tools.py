import json

from coach import tools
from coach.history import History
from coach.srs import Deck
from coach.store import LocalStore


def _local(tmp_path):
    store = LocalStore(Deck(tmp_path / "deck.json"))
    tools.configure(store=store, history=History(tmp_path / "history.jsonl"))
    return store


def test_tool_schemas_are_generated():
    for tool in tools.TOOLS:
        schema = tool.to_dict()
        assert schema["name"]
        assert schema["description"]
        assert schema["input_schema"]["type"] == "object"


def test_flashcard_flow(tmp_path):
    _local(tmp_path)
    added = json.loads(tools.add_flashcard.call({"word": "猫", "reading": "ねこ", "meaning": "cat", "jlpt": "N5"}))
    assert added["already_existed"] is False
    assert added["backend"] == "local"

    due = json.loads(tools.list_due_cards.call({"limit": 5}))
    assert due["count"] == 1
    card_id = due["cards"][0]["card_id"]

    reviewed = json.loads(tools.record_review.call({"card_id": card_id, "grade": 5}))
    assert reviewed["interval_days"] == 1

    assert json.loads(tools.list_due_cards.call({}))["count"] == 0
    assert json.loads(tools.deck_stats.call({}))["total"] == 1

    kinds = [e["kind"] for e in tools.get_history().entries()]
    assert kinds == ["card_added", "review"]


def test_record_review_bad_id(tmp_path):
    _local(tmp_path)
    result = json.loads(tools.record_review.call({"card_id": "nope", "grade": 3}))
    assert "error" in result


def test_default_store_falls_back_to_local_when_anki_is_down(tmp_path, monkeypatch):
    from coach.config import Settings

    Settings(backend="auto", anki_url="http://127.0.0.1:1").save()
    assert tools.get_store().name == "local"

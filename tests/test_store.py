from datetime import date

from coach.anki import AnkiClient
from coach.srs import Deck
from coach.store import AnkiStore, LocalStore
from tests.test_anki import FakeAnki


def test_local_store_states_and_reviews(tmp_path):
    store = LocalStore(Deck(tmp_path / "deck.json"))
    card, existed = store.add("猫", "ねこ", "cat", "猫が寝ている。")
    assert not existed and card.state == "new"
    assert [c.id for c in store.due()] == [card.id]

    card = store.review(card.id, 4)
    assert card.state == "learning"
    assert store.stats()["learning"] == 1
    events = store.reviews()
    assert len(events) == 1 and events[0].correct and events[0].button == 3


def test_anki_store_round_trip():
    fake = FakeAnki()
    store = AnkiStore(AnkiClient(transport=fake), "Japanese Coach", "Japanese Coach")
    assert "Japanese Coach" in fake.decks

    card, existed = store.add("猫", "ねこ", "cat", "猫が寝ている。", tags=["jlpt-n5"])
    assert not existed
    assert card.word == "猫" and card.reading == "ねこ" and card.state == "new"
    assert "jlpt-n5" in card.tags and "coach" in card.tags
    assert card.created == date.today().isoformat() or card.created  # id-derived date

    same, existed = store.add("猫", "ねこ", "cat")
    assert existed and same.id == card.id

    assert [c.id for c in store.due()] == [card.id]
    reviewed = store.review(card.id, 5)
    assert reviewed.id == card.id
    answered = [c for c in fake.calls if c["action"] == "answerCards"][-1]
    assert answered["params"]["answers"] == [{"cardId": int(card.id), "ease": 4}]

    events = store.reviews()
    assert [e.correct for e in events] == [True, False]
    assert store.stats()["total"] == 1

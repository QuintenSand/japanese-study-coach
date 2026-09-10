from datetime import date, timedelta

from coach.srs import Card, Deck


def test_new_card_is_due_today():
    c = Card(word="猫", reading="ねこ", meaning="cat")
    assert c.is_due()


def test_good_reviews_grow_interval():
    c = Card(word="猫", reading="ねこ", meaning="cat")
    day = date(2026, 1, 1)
    c.review(4, on=day)
    assert c.interval_days == 1
    c.review(4, on=day + timedelta(days=1))
    assert c.interval_days == 6
    c.review(4, on=day + timedelta(days=7))
    assert c.interval_days > 6
    assert not c.is_due(on=day + timedelta(days=8))


def test_lapse_resets_interval():
    c = Card(word="猫", reading="ねこ", meaning="cat", interval_days=30, reps=5)
    c.review(1, on=date(2026, 1, 1))
    assert c.interval_days == 1
    assert c.reps == 0
    assert c.lapses == 1


def test_invalid_grade():
    c = Card(word="猫", reading="ねこ", meaning="cat")
    try:
        c.review(7)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_deck_roundtrip(tmp_path):
    path = tmp_path / "deck.json"
    deck = Deck(path)
    card = deck.add("勉強", "べんきょう", "study", "毎日勉強します。")
    assert deck.add("勉強", "x", "y").id == card.id  # no duplicates

    deck.review(card.id, 5, on=date(2026, 1, 1))
    reloaded = Deck(path)
    assert reloaded.cards[card.id].due == "2026-01-02"
    assert reloaded.stats(on=date(2026, 1, 1))["due_today"] == 0
    assert reloaded.stats(on=date(2026, 1, 2))["due_today"] == 1

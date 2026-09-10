from datetime import date, datetime, timedelta

from coach import analytics
from coach.store import CardView, ReviewEvent


def _card(i, state="new", interval=0, created=None, tags=()):
    return CardView(id=str(i), word=f"w{i}", reading="", meaning="", state=state, interval_days=interval,
                    created=(created or date.today()).isoformat(), tags=list(tags))


def test_state_and_interval_breakdowns():
    cards = [_card(1), _card(2, "young", 5), _card(3, "mature", 40), _card(4, "learning", 1)]
    states = analytics.state_breakdown(cards).set_index("state")["cards"].to_dict()
    assert states == {"new": 1, "learning": 1, "young": 1, "mature": 1}
    hist = analytics.interval_histogram(cards).set_index("interval")["cards"].to_dict()
    assert hist["≤1 day"] == 1 and hist["2-6 days"] == 1 and hist["3 weeks-3 months"] == 1


def test_jlpt_breakdown():
    cards = [_card(1, tags=["coach", "jlpt-n5"]), _card(2, tags=["jlpt-n3"]), _card(3)]
    df = analytics.jlpt_breakdown(cards).set_index("level")["cards"]
    assert df["N5"] == 1 and df["N3"] == 1 and df["Unknown"] == 1


def test_reviews_by_day_and_retention():
    now = datetime.now()
    reviews = [
        ReviewEvent(now, "1", True, 3, 60000),
        ReviewEvent(now, "2", False, 1, 30000),
        ReviewEvent(now - timedelta(days=1), "1", True, 4, 0),
        ReviewEvent(now - timedelta(days=100), "1", True, 4, 0),
    ]
    df = analytics.reviews_by_day(reviews, 30)
    assert len(df) == 2
    today = df[df["day"] == datetime.combine(now.date(), datetime.min.time())].iloc[0]
    assert today["reviews"] == 2 and today["accuracy"] == 0.5 and today["minutes"] == 1.5
    assert analytics.retention(reviews, 30) == 2 / 3
    assert analytics.retention(reviews, None) == 0.75
    assert analytics.retention([], 30) is None


def test_streak():
    today = date(2026, 9, 10)
    days = {today, today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=5)}
    assert analytics.streak(days, today) == 3
    assert analytics.streak(days - {today}, today) == 2  # yesterday still counts
    assert analytics.streak(set(), today) == 0


def test_history_frames():
    entries = [
        {"ts": datetime.now().isoformat(), "kind": "sentence", "text": "猫"},
        {"ts": datetime.now().isoformat(), "kind": "lookup", "word": "猫"},
        {"ts": datetime.now().isoformat(), "kind": "lookup", "word": "猫"},
        {"ts": datetime.now().isoformat(), "kind": "lookup", "word": "犬"},
    ]
    assert analytics.sentences_by_day(entries)["sentences"].sum() == 1
    top = analytics.top_lookups(entries)
    assert list(top["word"]) == ["猫", "犬"] and list(top["lookups"]) == [2, 1]


def test_empty_inputs_do_not_crash():
    assert analytics.cards_added_by_week([]).empty
    assert analytics.reviews_by_day([]).empty
    assert analytics.sentences_by_day([]).empty
    assert analytics.top_lookups([]).empty

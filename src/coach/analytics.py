"""Progress metrics computed from the flashcard store and the study history.

Everything here is a pure function over plain lists so it can be tested
without Anki, Streamlit, or the API.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

import pandas as pd

from .store import CardView, ReviewEvent

STATE_ORDER = ["new", "learning", "young", "mature"]
INTERVAL_BINS = [(0, 1, "≤1 day"), (2, 6, "2-6 days"), (7, 20, "1-3 weeks"), (21, 89, "3 weeks-3 months"), (90, 10**9, "3+ months")]


def state_breakdown(cards: list[CardView]) -> pd.DataFrame:
    counts = Counter(c.state for c in cards)
    return pd.DataFrame({"state": STATE_ORDER, "cards": [counts.get(s, 0) for s in STATE_ORDER]})


def interval_histogram(cards: list[CardView]) -> pd.DataFrame:
    labels = [label for _, _, label in INTERVAL_BINS]
    counts = Counter()
    for c in cards:
        if c.state == "new":
            continue
        for lo, hi, label in INTERVAL_BINS:
            if lo <= c.interval_days <= hi:
                counts[label] += 1
                break
    return pd.DataFrame({"interval": labels, "cards": [counts.get(l, 0) for l in labels]})


def cards_added_by_week(cards: list[CardView]) -> pd.DataFrame:
    if not cards:
        return pd.DataFrame({"week": pd.Series(dtype="datetime64[ns]"), "cards": pd.Series(dtype="int")})
    df = pd.DataFrame({"created": pd.to_datetime([c.created for c in cards if c.created])})
    df["week"] = df["created"].dt.to_period("W").dt.start_time
    out = df.groupby("week").size().rename("cards").reset_index()
    return out


def jlpt_breakdown(cards: list[CardView]) -> pd.DataFrame:
    levels = ["N5", "N4", "N3", "N2", "N1", "Unknown"]
    counts = Counter()
    for c in cards:
        tag = next((t for t in c.tags if t.lower().startswith("jlpt-n")), None)
        counts[tag[-2:].upper() if tag else "Unknown"] += 1
    return pd.DataFrame({"level": levels, "cards": [counts.get(l, 0) for l in levels]})


def reviews_by_day(reviews: list[ReviewEvent], days: int | None = 30) -> pd.DataFrame:
    if not reviews:
        return pd.DataFrame({"day": pd.Series(dtype="datetime64[ns]"), "reviews": [], "correct": [], "accuracy": [], "minutes": []})
    df = pd.DataFrame(
        {"day": [r.ts.date() for r in reviews], "correct": [int(r.correct) for r in reviews], "ms": [r.duration_ms for r in reviews]}
    )
    if days:
        cutoff = date.today() - timedelta(days=days - 1)
        df = df[df["day"] >= cutoff]
    out = df.groupby("day").agg(reviews=("correct", "size"), correct=("correct", "sum"), ms=("ms", "sum")).reset_index()
    out["accuracy"] = (out["correct"] / out["reviews"]).round(3)
    out["minutes"] = (out["ms"] / 60000).round(1)
    out["day"] = pd.to_datetime(out["day"])
    return out.drop(columns="ms")


def retention(reviews: list[ReviewEvent], days: int | None = 30) -> float | None:
    """Share of reviews answered correctly in the window, or None if no reviews."""
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        reviews = [r for r in reviews if r.ts >= cutoff]
    if not reviews:
        return None
    return sum(r.correct for r in reviews) / len(reviews)


def streak(active_days: set[date], today: date | None = None) -> int:
    """Consecutive days (ending today or yesterday) with activity."""
    today = today or date.today()
    day = today if today in active_days else today - timedelta(days=1)
    n = 0
    while day in active_days:
        n += 1
        day -= timedelta(days=1)
    return n


def sentences_by_day(entries: list[dict], days: int | None = 30) -> pd.DataFrame:
    days_list = [datetime.fromisoformat(e["ts"]).date() for e in entries if e.get("kind") == "sentence"]
    if days:
        cutoff = date.today() - timedelta(days=days - 1)
        days_list = [d for d in days_list if d >= cutoff]
    if not days_list:
        return pd.DataFrame({"day": pd.Series(dtype="datetime64[ns]"), "sentences": pd.Series(dtype="int")})
    counts = Counter(days_list)
    out = pd.DataFrame({"day": pd.to_datetime(sorted(counts)), "sentences": [counts[d] for d in sorted(counts)]})
    return out


def top_lookups(entries: list[dict], n: int = 15) -> pd.DataFrame:
    counts = Counter(e["word"] for e in entries if e.get("kind") == "lookup" and e.get("word"))
    rows = counts.most_common(n)
    return pd.DataFrame({"word": [w for w, _ in rows], "lookups": [c for _, c in rows]})


def active_days(reviews: list[ReviewEvent], entries: list[dict]) -> set[date]:
    days = {r.ts.date() for r in reviews}
    days |= {datetime.fromisoformat(e["ts"]).date() for e in entries if e.get("kind") in {"sentence", "review", "card_added"}}
    return days

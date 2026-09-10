"""Tools the coach agent can call.

Each function is decorated with ``@beta_tool`` so the Anthropic SDK builds the
JSON schema from the signature and docstring. Every tool returns a string;
JSON is used so Claude gets structured data back.
"""

from __future__ import annotations

import json
import urllib.error

from anthropic import beta_tool

from . import dictionary
from .srs import Deck, default_deck_path

_deck: Deck | None = None


def get_deck() -> Deck:
    global _deck
    if _deck is None:
        _deck = Deck(default_deck_path())
    return _deck


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


@beta_tool
def lookup_word(word: str) -> str:
    """Look up a Japanese word or phrase in the dictionary.

    Accepts kanji, kana, or romaji. Returns up to three matching entries with
    readings, English meanings, parts of speech, JLPT level, and whether the
    word is common. Use this whenever you need to confirm a reading or meaning
    rather than guessing.

    Args:
        word: The word to look up, e.g. 勉強, べんきょう, or benkyou.
    """
    try:
        entries = dictionary.lookup(word)
    except (urllib.error.URLError, TimeoutError) as e:
        return _json({"error": f"dictionary unavailable: {e}"})
    if not entries:
        return _json({"error": f"no dictionary entries for {word!r}"})
    return _json({"entries": entries})


@beta_tool
def add_flashcard(word: str, reading: str, meaning: str, example: str = "") -> str:
    """Save a word to the learner's spaced-repetition deck.

    Only add words the learner has asked to save or has clearly struggled
    with. If the word already exists, the existing card is returned unchanged.

    Args:
        word: The word as written, e.g. 勉強.
        reading: The reading in hiragana or katakana, e.g. べんきょう.
        meaning: A short English meaning, e.g. "study".
        example: An example sentence using the word, ideally the one the
            learner encountered.
    """
    deck = get_deck()
    existed = deck.find(word) is not None
    card = deck.add(word=word, reading=reading, meaning=meaning, example=example)
    return _json({"card_id": card.id, "word": card.word, "already_existed": existed})


@beta_tool
def list_due_cards(limit: int = 10) -> str:
    """List flashcards that are due for review today, oldest first.

    Use this to start a quiz session. Each card includes its id, which you
    must pass to record_review after the learner answers.

    Args:
        limit: Maximum number of cards to return.
    """
    cards = get_deck().due(limit=limit)
    return _json(
        {
            "count": len(cards),
            "cards": [
                {
                    "card_id": c.id,
                    "word": c.word,
                    "reading": c.reading,
                    "meaning": c.meaning,
                    "example": c.example,
                    "reps": c.reps,
                }
                for c in cards
            ],
        }
    )


@beta_tool
def record_review(card_id: str, grade: int) -> str:
    """Record how well the learner recalled a card and reschedule it.

    Grade scale: 0 = no idea, 1 = wrong but recognized it, 2 = wrong but close,
    3 = correct with difficulty, 4 = correct after a pause, 5 = instant recall.
    Grades below 3 reset the card's interval.

    Args:
        card_id: The id returned by list_due_cards or add_flashcard.
        grade: Recall quality from 0 to 5.
    """
    try:
        card = get_deck().review(card_id, grade)
    except (KeyError, ValueError) as e:
        return _json({"error": str(e)})
    return _json({"card_id": card.id, "word": card.word, "next_due": card.due, "interval_days": card.interval_days})


@beta_tool
def deck_stats() -> str:
    """Summarize the learner's deck: total cards, due today, new, and mature."""
    return _json(get_deck().stats())


TOOLS = [lookup_word, add_flashcard, list_due_cards, record_review, deck_stats]

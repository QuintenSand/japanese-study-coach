"""Tools the coach agent can call.

Each function is decorated with ``@beta_tool`` so the Anthropic SDK builds the
JSON schema from the signature and docstring. Every tool returns a JSON string.
"""

from __future__ import annotations

import json
import urllib.error

from anthropic import beta_tool

from . import dictionary
from .anki import AnkiError
from .config import data_dir
from .history import History
from .store import FlashcardStore, open_store

_store: FlashcardStore | None = None
_history: History | None = None


def configure(store: FlashcardStore | None = None, history: History | None = None) -> None:
    """Inject the store and history (used by the UI and tests)."""
    global _store, _history
    _store, _history = store, history


def get_store() -> FlashcardStore:
    global _store
    if _store is None:
        _store, _ = open_store()
    return _store


def get_history() -> History:
    global _history
    if _history is None:
        _history = History(data_dir() / "history.jsonl")
    return _history


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def _card(c) -> dict:
    return {
        "card_id": c.id, "word": c.word, "reading": c.reading, "meaning": c.meaning, "example": c.example,
        "state": c.state, "interval_days": c.interval_days, "reps": c.reps,
    }


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
    get_history().log("lookup", word=word, found=bool(entries))
    if not entries:
        return _json({"error": f"no dictionary entries for {word!r}"})
    return _json({"entries": entries})


@beta_tool
def add_flashcard(word: str, reading: str, meaning: str, example: str = "", jlpt: str = "") -> str:
    """Save a word to the learner's flashcard deck (Anki when connected, otherwise local).

    Only add words the learner has asked to save or has clearly struggled
    with. If the word already exists, the existing card is returned unchanged.
    The result says which backend stored it; mention that briefly.

    Args:
        word: The word as written, e.g. 勉強.
        reading: The reading in hiragana or katakana, e.g. べんきょう.
        meaning: A short English meaning, e.g. "study".
        example: An example sentence using the word, ideally the one the
            learner encountered.
        jlpt: JLPT level from the dictionary result if known, e.g. "N5".
    """
    tags = []
    level = jlpt.strip().lower().replace("jlpt-", "")
    if level in {"n1", "n2", "n3", "n4", "n5"}:
        tags.append(f"jlpt-{level}")
    store = get_store()
    try:
        card, existed = store.add(word=word, reading=reading, meaning=meaning, example=example, tags=tags)
    except AnkiError as e:
        return _json({"error": f"Anki rejected the card: {e}"})
    if not existed:
        get_history().log("card_added", word=word, backend=store.name)
    return _json({**_card(card), "backend": store.name, "already_existed": existed})


@beta_tool
def list_due_cards(limit: int = 10) -> str:
    """List flashcards that are due for review now (including new cards).

    Use this to start a quiz session. Each card includes its id, which you
    must pass to record_review after the learner answers.

    Args:
        limit: Maximum number of cards to return.
    """
    try:
        cards = get_store().due(limit=limit)
    except AnkiError as e:
        return _json({"error": str(e)})
    return _json({"count": len(cards), "backend": get_store().name, "cards": [_card(c) for c in cards]})


@beta_tool
def record_review(card_id: str, grade: int) -> str:
    """Record how well the learner recalled a card and reschedule it.

    Grade scale: 0 = no idea, 1 = wrong but recognized it, 2 = wrong but close,
    3 = correct with difficulty, 4 = correct after a pause, 5 = instant recall.
    Grades below 3 count as a lapse. In Anki this maps to Again/Hard/Good/Easy.

    Args:
        card_id: The id returned by list_due_cards or add_flashcard.
        grade: Recall quality from 0 to 5.
    """
    try:
        card = get_store().review(card_id, grade)
    except (KeyError, ValueError, AnkiError) as e:
        return _json({"error": str(e)})
    get_history().log("review", word=card.word, grade=grade, correct=grade >= 3)
    return _json({"card_id": card.id, "word": card.word, "state": card.state, "interval_days": card.interval_days, "next_due": card.due})


@beta_tool
def deck_stats() -> str:
    """Summarize the learner's deck: total, due now, new, learning, young, mature."""
    try:
        return _json({**get_store().stats(), "backend": get_store().name})
    except AnkiError as e:
        return _json({"error": str(e)})


TOOLS = [lookup_word, add_flashcard, list_due_cards, record_review, deck_stats]

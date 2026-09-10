"""Flashcard storage behind one interface, backed by Anki or the local deck.

The agent's tools talk to a FlashcardStore and never care which one is active.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from .anki import AnkiClient, AnkiUnavailable, NOTE_FIELDS
from .config import Settings, data_dir
from .srs import Deck

MATURE_DAYS = 21

# Coach grade (0-5) -> Anki ease button (1 Again, 2 Hard, 3 Good, 4 Easy)
GRADE_TO_EASE = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3, 5: 4}


@dataclass
class CardView:
    id: str
    word: str
    reading: str
    meaning: str
    example: str = ""
    state: str = "new"  # new | learning | young | mature
    interval_days: int = 0
    reps: int = 0
    lapses: int = 0
    created: str = ""  # ISO date
    due: str = ""  # ISO date when known (local only)
    tags: list[str] = field(default_factory=list)


@dataclass
class ReviewEvent:
    ts: datetime
    card_id: str
    correct: bool
    button: int  # 1-4 in Anki terms
    duration_ms: int = 0


class FlashcardStore(Protocol):
    name: str

    def add(self, word: str, reading: str, meaning: str, example: str = "", tags: list[str] | None = None) -> tuple[CardView, bool]: ...
    def due(self, limit: int = 10) -> list[CardView]: ...
    def review(self, card_id: str, grade: int) -> CardView: ...
    def all_cards(self) -> list[CardView]: ...
    def reviews(self) -> list[ReviewEvent]: ...
    def stats(self) -> dict: ...


def _stats(cards: list[CardView], due_count: int) -> dict:
    return {
        "total": len(cards),
        "due_today": due_count,
        "new": sum(c.state == "new" for c in cards),
        "learning": sum(c.state == "learning" for c in cards),
        "young": sum(c.state == "young" for c in cards),
        "mature": sum(c.state == "mature" for c in cards),
    }


# -- local --------------------------------------------------------------------


class LocalStore:
    name = "local"

    def __init__(self, deck: Deck):
        self.deck = deck

    @staticmethod
    def _view(card) -> CardView:
        if card.reps == 0:
            state = "new"
        elif card.interval_days <= 1:
            state = "learning"
        elif card.interval_days < MATURE_DAYS:
            state = "young"
        else:
            state = "mature"
        return CardView(
            id=card.id, word=card.word, reading=card.reading, meaning=card.meaning, example=card.example,
            state=state, interval_days=card.interval_days, reps=card.reps, lapses=card.lapses,
            created=card.created, due=card.due, tags=[],
        )

    def add(self, word, reading, meaning, example="", tags=None):
        existed = self.deck.find(word) is not None
        return self._view(self.deck.add(word, reading, meaning, example)), existed

    def due(self, limit=10):
        return [self._view(c) for c in self.deck.due(limit=limit)]

    def review(self, card_id, grade):
        return self._view(self.deck.review(card_id, grade))

    def all_cards(self):
        return [self._view(c) for c in self.deck.cards.values()]

    def reviews(self):
        return [
            ReviewEvent(ts=datetime.fromisoformat(r["ts"]), card_id=r["card_id"], correct=bool(r["correct"]),
                        button=GRADE_TO_EASE.get(int(r["grade"]), 1))
            for r in self.deck.reviews
        ]

    def stats(self):
        return _stats(self.all_cards(), len(self.deck.due()))


# -- anki ---------------------------------------------------------------------


class AnkiStore:
    name = "anki"

    def __init__(self, client: AnkiClient, deck: str, model: str):
        self.client = client
        self.deck = deck
        self.model = model
        self.client.ensure_setup(deck, model)

    def _deck_query(self, extra: str = "") -> str:
        from .anki import quote

        return f"deck:{quote(self.deck)} {extra}".strip()

    @staticmethod
    def _view(info: dict, tags: list[str] | None = None) -> CardView:
        f = {k: v.get("value", "") for k, v in info.get("fields", {}).items()}
        ctype, interval = info.get("type", 0), int(info.get("interval", 0))
        if ctype == 0:
            state = "new"
        elif ctype in (1, 3) or interval <= 0:
            state = "learning"
        elif interval < MATURE_DAYS:
            state = "young"
        else:
            state = "mature"
        # Anki card ids are creation timestamps in milliseconds.
        created = datetime.fromtimestamp(int(info["cardId"]) / 1000).date().isoformat()
        return CardView(
            id=str(info["cardId"]), word=f.get("Word", ""), reading=f.get("Reading", ""), meaning=f.get("Meaning", ""),
            example=f.get("Example", ""), state=state, interval_days=max(interval, 0), reps=int(info.get("reps", 0)),
            lapses=int(info.get("lapses", 0)), created=created, tags=tags or [],
        )

    def _views(self, card_ids: list[int]) -> list[CardView]:
        infos = self.client.cards_info(card_ids)
        note_ids = sorted({int(i["note"]) for i in infos})
        tags_by_note = {int(n["noteId"]): list(n.get("tags", [])) for n in self.client.notes_info(note_ids)}
        return [self._view(i, tags_by_note.get(int(i["note"]), [])) for i in infos]

    def add(self, word, reading, meaning, example="", tags=None):
        fields = dict(zip(NOTE_FIELDS, [word, reading, meaning, example, ""]))
        note_id, existed = self.client.add_note(self.deck, self.model, fields, ["coach", *(tags or [])])
        card_ids = self.client.find_cards(f"nid:{note_id}")
        views = self._views(card_ids[:1])
        return views[0], existed

    def due(self, limit=10):
        ids = self.client.find_cards(self._deck_query("(is:due OR is:new)"))
        return self._views(ids[:limit])

    def review(self, card_id, grade):
        if not 0 <= grade <= 5:
            raise ValueError("grade must be between 0 and 5")
        cid = int(card_id)
        ok = self.client.answer_cards([(cid, GRADE_TO_EASE[grade])])
        if not ok or not ok[0]:
            raise KeyError(f"no card with id {card_id!r}")
        return self._views([cid])[0]

    def all_cards(self):
        return self._views(self.client.find_cards(self._deck_query()))

    def reviews(self):
        rows = self.client.card_reviews(self.deck, 0)
        return [
            ReviewEvent(ts=datetime.fromtimestamp(r[0] / 1000), card_id=str(r[1]), correct=r[3] > 1, button=int(r[3]),
                        duration_ms=int(r[7]))
            for r in rows
        ]

    def stats(self):
        due = len(self.client.find_cards(self._deck_query("(is:due OR is:new)")))
        return _stats(self.all_cards(), due)


# -- factory ------------------------------------------------------------------


def open_store(settings: Settings | None = None) -> tuple[FlashcardStore, str | None]:
    """Open the configured store. Returns (store, warning) where warning explains a fallback."""
    settings = settings or Settings.load()
    local = lambda: LocalStore(Deck(data_dir() / "deck.json"))  # noqa: E731

    if settings.backend == "local":
        return local(), None

    client = AnkiClient(settings.anki_url)
    try:
        if settings.backend == "anki" or client.is_available():
            return AnkiStore(client, settings.anki_deck, settings.anki_model), None
    except AnkiUnavailable as e:
        if settings.backend == "anki":
            raise
        return local(), f"Anki is not reachable ({e}). Using the local deck instead."
    return local(), "Anki is not running. Using the local deck instead."

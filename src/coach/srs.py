"""Flashcard deck with a simplified SM-2 spaced-repetition scheduler.

The deck is a JSON file. Each card tracks an ease factor, an interval in days,
and a due date. Grades run 0 (blank) to 5 (instant recall); anything below 3
is a lapse and resets the interval.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path


def _today() -> str:
    return date.today().isoformat()


@dataclass
class Card:
    word: str
    reading: str
    meaning: str
    example: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created: str = field(default_factory=_today)
    due: str = field(default_factory=_today)
    interval_days: int = 0
    ease: float = 2.5
    reps: int = 0
    lapses: int = 0

    def is_due(self, on: date | None = None) -> bool:
        on = on or date.today()
        return date.fromisoformat(self.due) <= on

    def review(self, grade: int, on: date | None = None) -> None:
        """Apply an SM-2 style update for a grade from 0 to 5."""
        if not 0 <= grade <= 5:
            raise ValueError("grade must be between 0 and 5")
        on = on or date.today()
        if grade < 3:
            self.reps = 0
            self.lapses += 1
            self.interval_days = 1
        else:
            if self.reps == 0:
                self.interval_days = 1
            elif self.reps == 1:
                self.interval_days = 6
            else:
                self.interval_days = round(self.interval_days * self.ease)
            self.reps += 1
        # Standard SM-2 ease adjustment, floored at 1.3.
        self.ease = max(1.3, self.ease + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
        self.due = (on + timedelta(days=self.interval_days)).isoformat()


class Deck:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.cards: dict[str, Card] = {}
        self._load()

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.cards = {c["id"]: Card(**c) for c in raw.get("cards", [])}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": datetime.now().isoformat(timespec="seconds"),
            "cards": [asdict(c) for c in self.cards.values()],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- operations --------------------------------------------------------

    def find(self, word: str) -> Card | None:
        return next((c for c in self.cards.values() if c.word == word), None)

    def add(self, word: str, reading: str, meaning: str, example: str = "") -> Card:
        existing = self.find(word)
        if existing:
            return existing
        card = Card(word=word, reading=reading, meaning=meaning, example=example)
        self.cards[card.id] = card
        self.save()
        return card

    def due(self, limit: int | None = None, on: date | None = None) -> list[Card]:
        cards = sorted((c for c in self.cards.values() if c.is_due(on)), key=lambda c: c.due)
        return cards[:limit] if limit else cards

    def review(self, card_id: str, grade: int, on: date | None = None) -> Card:
        card = self.cards.get(card_id)
        if card is None:
            raise KeyError(f"no card with id {card_id!r}")
        card.review(grade, on)
        self.save()
        return card

    def stats(self, on: date | None = None) -> dict:
        on = on or date.today()
        due = [c for c in self.cards.values() if c.is_due(on)]
        return {
            "total": len(self.cards),
            "due_today": len(due),
            "new": sum(1 for c in self.cards.values() if c.reps == 0),
            "mature": sum(1 for c in self.cards.values() if c.interval_days >= 21),
        }


def default_deck_path() -> Path:
    data_dir = Path(os.environ.get("COACH_DATA_DIR", "data"))
    return data_dir / "deck.json"

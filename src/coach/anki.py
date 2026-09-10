"""Thin client for the AnkiConnect add-on (https://git.sr.ht/~foosoft/anki-connect).

AnkiConnect listens on localhost:8765 while Anki desktop is open. Every call is
a JSON POST with {"action", "version": 6, "params"} and returns
{"result", "error"}.

The default timeout is generous because macOS App Nap can stall a backgrounded
Anki for several seconds per request. A closed Anki still fails instantly
(connection refused), so the long timeout only costs time when Anki is napping.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

Transport = Callable[[dict], dict]

NOTE_FIELDS = ["Word", "Reading", "Meaning", "Example", "Notes"]

CARD_CSS = """.card { font-family: "Hiragino Sans", "Noto Sans JP", sans-serif; font-size: 22px; text-align: center; color: #222; background: #fff; }
.word { font-size: 44px; margin: 12px 0; }
.reading { color: #555; font-size: 24px; }
.meaning { margin-top: 12px; }
.example { margin-top: 18px; font-size: 20px; color: #444; }
.notes { margin-top: 12px; font-size: 16px; color: #777; }
"""

CARD_TEMPLATES = [
    {
        "Name": "Recognition",
        "Front": '<div class="word">{{Word}}</div>',
        "Back": (
            '<div class="word">{{Word}}</div><div class="reading">{{Reading}}</div>'
            '<hr id="answer"><div class="meaning">{{Meaning}}</div>'
            '{{#Example}}<div class="example">{{Example}}</div>{{/Example}}'
            '{{#Notes}}<div class="notes">{{Notes}}</div>{{/Notes}}'
        ),
    }
]


class AnkiError(Exception):
    """AnkiConnect returned an error for a request."""


class AnkiUnavailable(AnkiError):
    """Anki is not running or AnkiConnect is not installed."""


def _http_transport(url: str, timeout: float) -> Transport:
    def send(payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise AnkiUnavailable(f"cannot reach AnkiConnect at {url}: {e}") from e

    return send


def quote(value: str) -> str:
    """Quote a value for Anki's search syntax."""
    return '"' + value.replace('"', "") + '"'


class AnkiClient:
    def __init__(self, url: str = "http://127.0.0.1:8765", timeout: float = 20.0, transport: Transport | None = None):
        self.url = url
        self._send = transport or _http_transport(url, timeout)

    def invoke(self, action: str, **params: Any) -> Any:
        payload: dict[str, Any] = {"action": action, "version": 6}
        if params:
            payload["params"] = params
        response = self._send(payload)
        if response.get("error"):
            raise AnkiError(response["error"])
        return response.get("result")

    # -- availability ------------------------------------------------------

    def is_available(self) -> bool:
        try:
            self.invoke("version")
            return True
        except AnkiError:
            return False

    # -- decks and note types ---------------------------------------------

    def deck_names(self) -> list[str]:
        return self.invoke("deckNames")

    def model_names(self) -> list[str]:
        return self.invoke("modelNames")

    def ensure_setup(self, deck: str, model: str) -> dict:
        """Create the deck and note type if they do not exist yet."""
        created = {"deck": False, "model": False}
        if deck not in self.deck_names():
            self.invoke("createDeck", deck=deck)
            created["deck"] = True
        if model not in self.model_names():
            self.invoke(
                "createModel",
                modelName=model,
                inOrderFields=NOTE_FIELDS,
                css=CARD_CSS,
                isCloze=False,
                cardTemplates=CARD_TEMPLATES,
            )
            created["model"] = True
        return created

    # -- notes and cards ----------------------------------------------------

    def find_notes(self, query: str) -> list[int]:
        return self.invoke("findNotes", query=query)

    def find_cards(self, query: str) -> list[int]:
        return self.invoke("findCards", query=query)

    def cards_info(self, card_ids: list[int]) -> list[dict]:
        if not card_ids:
            return []
        return self.invoke("cardsInfo", cards=card_ids)

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        if not note_ids:
            return []
        return self.invoke("notesInfo", notes=note_ids)

    def add_note(self, deck: str, model: str, fields: dict[str, str], tags: list[str]) -> tuple[int, bool]:
        """Add a note. Returns (note_id, already_existed).

        Anki treats the first field (Word) as the duplicate key within the deck.
        """
        try:
            note_id = self.invoke(
                "addNote",
                note={
                    "deckName": deck,
                    "modelName": model,
                    "fields": fields,
                    "tags": tags,
                    "options": {"allowDuplicate": False, "duplicateScope": "deck"},
                },
            )
            return int(note_id), False
        except AnkiError as e:
            if "duplicate" not in str(e).lower():
                raise
        word = fields.get(NOTE_FIELDS[0], "")
        existing = self.find_notes(f"deck:{quote(deck)} {NOTE_FIELDS[0]}:{quote(word)}")
        if not existing:
            raise AnkiError(f"duplicate reported but no existing note found for {word!r}")
        return int(existing[0]), True

    def answer_cards(self, answers: list[tuple[int, int]]) -> list[bool]:
        """Answer cards with ease 1 (Again) to 4 (Easy)."""
        return self.invoke("answerCards", answers=[{"cardId": cid, "ease": ease} for cid, ease in answers])

    def card_reviews(self, deck: str, start_id: int = 0) -> list[list]:
        """Review log rows: (reviewTime, cardID, usn, buttonPressed, newInterval, previousInterval, newFactor, reviewDuration, reviewType)."""
        return self.invoke("cardReviews", deck=deck, startID=start_id)

    def sync(self) -> None:
        self.invoke("sync")

import pytest

from coach.anki import AnkiClient, AnkiError, NOTE_FIELDS, quote


class FakeAnki:
    """Minimal in-memory AnkiConnect for tests."""

    def __init__(self):
        self.decks = ["Default"]
        self.models = ["Basic"]
        self.notes = {}  # note_id -> dict(deck, fields, tags)
        self.calls = []
        self.next_id = 1000

    def __call__(self, payload):
        self.calls.append(payload)
        action, params = payload["action"], payload.get("params", {})
        try:
            return {"result": getattr(self, action)(**params), "error": None}
        except AnkiError as e:
            return {"result": None, "error": str(e)}

    def version(self):
        return 6

    def deckNames(self):
        return list(self.decks)

    def modelNames(self):
        return list(self.models)

    def createDeck(self, deck):
        self.decks.append(deck)
        return 1

    def createModel(self, modelName, inOrderFields, cardTemplates, css="", isCloze=False):
        assert inOrderFields == NOTE_FIELDS
        self.models.append(modelName)
        return {"name": modelName}

    def addNote(self, note):
        word = note["fields"]["Word"]
        for nid, n in self.notes.items():
            if n["deck"] == note["deckName"] and n["fields"]["Word"] == word:
                raise AnkiError("cannot create note because it is a duplicate")
        self.next_id += 1
        self.notes[self.next_id] = {"deck": note["deckName"], "fields": note["fields"], "tags": note["tags"]}
        return self.next_id

    def findNotes(self, query):
        return [nid for nid, n in self.notes.items() if quote(n["fields"]["Word"]) in query]

    def findCards(self, query):
        if query.startswith("nid:"):
            return [int(query[4:]) * 10]
        return [nid * 10 for nid in self.notes]

    def cardsInfo(self, cards):
        return [
            {
                "cardId": cid, "note": cid // 10, "type": 0, "interval": 0, "reps": 0, "lapses": 0, "deckName": "x",
                "fields": {k: {"value": v, "order": i} for i, (k, v) in enumerate(self.notes[cid // 10]["fields"].items())},
            }
            for cid in cards
        ]

    def notesInfo(self, notes):
        return [{"noteId": nid, "tags": self.notes[nid]["tags"]} for nid in notes]

    def answerCards(self, answers):
        return [a["cardId"] // 10 in self.notes for a in answers]

    def cardReviews(self, deck, startID):
        return [[1757500000000, 10010, -1, 3, 4, 1, 2500, 6157, 1], [1757500100000, 10010, -1, 1, 1, 4, 2300, 4846, 1]]


@pytest.fixture
def fake():
    return FakeAnki()


@pytest.fixture
def client(fake):
    return AnkiClient(transport=fake)


def test_quote_strips_double_quotes():
    assert quote('Japa"nese') == '"Japanese"'


def test_ensure_setup_creates_missing_deck_and_model(client, fake):
    created = client.ensure_setup("Japanese Coach", "Japanese Coach")
    assert created == {"deck": True, "model": True}
    assert "Japanese Coach" in fake.decks and "Japanese Coach" in fake.models
    assert client.ensure_setup("Japanese Coach", "Japanese Coach") == {"deck": False, "model": False}


def test_add_note_and_duplicate(client):
    fields = dict(zip(NOTE_FIELDS, ["猫", "ねこ", "cat", "", ""]))
    nid, existed = client.add_note("Japanese Coach", "Japanese Coach", fields, ["coach"])
    assert existed is False
    nid2, existed2 = client.add_note("Japanese Coach", "Japanese Coach", fields, ["coach"])
    assert existed2 is True and nid2 == nid


def test_error_surfaces_as_exception(client):
    with pytest.raises(AnkiError):
        client.invoke("addNote", note={"deckName": "d", "modelName": "m", "fields": {"Word": "x"}, "tags": []})
        client.invoke("addNote", note={"deckName": "d", "modelName": "m", "fields": {"Word": "x"}, "tags": []})


def test_unavailable_when_nothing_listens():
    client = AnkiClient("http://127.0.0.1:1", timeout=0.5)
    assert client.is_available() is False

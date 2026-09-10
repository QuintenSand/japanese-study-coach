"""Settings page: backend, Anki connection, model."""

from __future__ import annotations

import streamlit as st

from coach.anki import AnkiClient, AnkiError
from coach.ui import common

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
BACKENDS = {"auto": "Auto (Anki when running, else local)", "anki": "Anki only", "local": "Local deck only"}


def render() -> None:
    common.backend_caption()
    s = common.settings()
    st.title("Settings")

    st.subheader("Flashcards")
    backend = st.selectbox("Backend", list(BACKENDS), index=list(BACKENDS).index(s.backend), format_func=BACKENDS.get)
    anki_url = st.text_input("AnkiConnect URL", s.anki_url)
    anki_deck = st.text_input("Anki deck", s.anki_deck)
    anki_model = st.text_input("Anki note type", s.anki_model, help="Created automatically with Word, Reading, Meaning, Example, Notes fields.")

    col1, col2 = st.columns(2)
    if col1.button("Test Anki connection", use_container_width=True):
        client = AnkiClient(anki_url)
        try:
            version = client.invoke("version")
            decks = client.deck_names()
            st.success(f"Connected. AnkiConnect v{version}. {len(decks)} decks: {', '.join(decks[:8])}{'…' if len(decks) > 8 else ''}")
        except AnkiError as e:
            st.error(f"{e}\n\nIs Anki open, and is the AnkiConnect add-on (code 2055492159) installed?")
    if col2.button("Create deck and note type", use_container_width=True):
        try:
            created = AnkiClient(anki_url).ensure_setup(anki_deck, anki_model)
            st.success(f"Deck {'created' if created['deck'] else 'exists'}, note type {'created' if created['model'] else 'exists'}.")
        except AnkiError as e:
            st.error(str(e))

    st.subheader("Model")
    model = st.text_input("Model id", s.model)
    effort = st.select_slider("Effort", EFFORTS, value=s.effort if s.effort in EFFORTS else "medium")

    if st.button("Save settings", type="primary"):
        s.backend, s.anki_url, s.anki_deck, s.anki_model, s.model, s.effort = backend, anki_url, anki_deck, anki_model, model, effort
        s.save()
        common.reset_runtime()
        st.success("Saved. The coach and deck were reloaded with the new settings.")

    st.caption("Settings are stored in data/settings.json. The API key comes from ANTHROPIC_API_KEY in your shell.")

"""Deck page: browse cards, add words by hand, manage the Anki link."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from coach import dictionary
from coach.anki import AnkiError
from coach.ui import common


def _cards_frame(cards) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "word": c.word, "reading": c.reading, "meaning": c.meaning, "example": c.example, "state": c.state,
                "interval (days)": c.interval_days, "reps": c.reps, "lapses": c.lapses, "added": c.created,
                "tags": ", ".join(t for t in c.tags if t != "coach"),
            }
            for c in cards
        ]
    )


def _add_by_hand(store) -> None:
    with st.expander("Add a word by hand"):
        col1, col2 = st.columns([3, 1])
        word = col1.text_input("Word", placeholder="勉強")
        if col2.button("Look up", use_container_width=True) and word:
            try:
                st.session_state.deck_lookup = dictionary.lookup(word)
            except Exception as e:  # network errors surface to the user
                st.error(f"Dictionary lookup failed: {e}")
        for i, entry in enumerate(st.session_state.get("deck_lookup", [])):
            with st.container(border=True):
                meanings = "; ".join(m for s in entry["senses"] for m in s["meanings"][:3])
                level = next((j[-2:].upper() for j in entry["jlpt"]), "")
                st.markdown(f"**{entry['word']}** 【{entry['reading']}】 {meanings}" + (f" · {level}" if level else ""))
                example = st.text_input("Example sentence", key=f"deck_ex_{i}")
                if st.button("Add to deck", key=f"deck_add_{i}"):
                    tags = [f"jlpt-{level.lower()}"] if level else []
                    try:
                        card, existed = store.add(entry["word"], entry["reading"], meanings, example, tags)
                    except AnkiError as e:
                        st.error(str(e))
                    else:
                        common.history().log("card_added", word=card.word, backend=store.name) if not existed else None
                        st.success("Already in the deck." if existed else f"Added {card.word} to the {store.name} deck.")


def render() -> None:
    common.backend_caption()
    store = common.store()
    st.title("Deck")

    try:
        cards = store.all_cards()
        stats = store.stats()
    except AnkiError as e:
        st.error(f"Could not read the deck from Anki: {e}")
        return

    cols = st.columns(6)
    for col, key in zip(cols, ["total", "due_today", "new", "learning", "young", "mature"]):
        col.metric(key.replace("_", " ").title(), stats.get(key, 0))

    if store.name == "anki":
        with st.sidebar:
            if st.button("Sync Anki (AnkiWeb)", use_container_width=True):
                try:
                    store.client.sync()
                    st.success("Sync started.")
                except AnkiError as e:
                    st.error(str(e))

    _add_by_hand(store)

    st.subheader("Cards")
    if not cards:
        st.info("No cards yet. Ask the coach to save a word, or add one by hand above.")
        return
    df = _cards_frame(cards)
    query = st.text_input("Filter", placeholder="word, reading, meaning, or tag")
    if query:
        mask = df.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)
        df = df[mask]
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} of {len(cards)} cards")

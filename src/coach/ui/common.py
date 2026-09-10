"""Session-scoped objects shared by the Streamlit pages."""

from __future__ import annotations

import streamlit as st

from coach import tools
from coach.agent import Coach
from coach.config import Settings, data_dir
from coach.history import History
from coach.store import FlashcardStore, open_store

# Categorical / sequential colors from the reference data-viz palette (light mode).
BLUE = "#2a78d6"
BLUE_STEPS = {"new": "#86b6ef", "learning": "#5598e7", "young": "#2a78d6", "mature": "#184f95"}
GRAY = "#9a9a96"


def settings() -> Settings:
    if "settings" not in st.session_state:
        st.session_state.settings = Settings.load()
    return st.session_state.settings


def history() -> History:
    if "history" not in st.session_state:
        st.session_state.history = History(data_dir() / "history.jsonl")
    return st.session_state.history


def store() -> FlashcardStore:
    if "store" not in st.session_state:
        s, warning = open_store(settings())
        st.session_state.store = s
        st.session_state.store_warning = warning
        tools.configure(store=s, history=history())
    return st.session_state.store


def store_warning() -> str | None:
    store()
    return st.session_state.get("store_warning")


def coach() -> Coach:
    if "coach" not in st.session_state:
        s = settings()
        st.session_state.coach = Coach(model=s.model, effort=s.effort)
    return st.session_state.coach


def has_credentials() -> bool:
    client = coach().client
    return bool(client.api_key or client.auth_token or client.credentials)


def reset_runtime() -> None:
    """Drop cached store and coach so new settings take effect."""
    for key in ("store", "store_warning", "coach", "transcript"):
        st.session_state.pop(key, None)
    tools.configure(None, None)


def backend_caption() -> None:
    s = store()
    if s.name == "anki":
        st.sidebar.success(f"Anki · deck “{settings().anki_deck}”", icon="🔗")
    else:
        st.sidebar.info("Local deck", icon="💾")
    if store_warning():
        st.sidebar.caption(store_warning())
        if st.sidebar.button("Retry Anki", use_container_width=True):
            reset_runtime()
            st.rerun()

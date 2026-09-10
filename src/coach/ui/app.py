"""Streamlit entry point. Run with `uv run coach ui` or `streamlit run src/coach/ui/app.py`."""

import streamlit as st

from coach.ui import chat, deck, progress, settings_page

st.set_page_config(page_title="Japanese Study Coach", page_icon="📚", layout="wide")

st.navigation(
    [
        st.Page(chat.render, title="Coach", icon="💬", default=True),
        st.Page(deck.render, title="Deck", icon="🗂️", url_path="deck"),
        st.Page(progress.render, title="Progress", icon="📈", url_path="progress"),
        st.Page(settings_page.render, title="Settings", icon="⚙️", url_path="settings"),
    ]
).run()

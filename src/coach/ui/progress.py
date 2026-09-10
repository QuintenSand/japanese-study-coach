"""Progress page: charts of reviews, retention, deck growth, and study activity."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from coach import analytics
from coach.anki import AnkiError
from coach.ui import common

RANGES = {"Last 30 days": 30, "Last 90 days": 90, "Last year": 365, "All time": None}


def _bar(df: pd.DataFrame, x: str, y: str, *, x_title: str, y_title: str, temporal: bool = False, color=None, horizontal=False) -> alt.Chart:
    """Thin bars, rounded at the data end, one hue unless an explicit ordinal color map is given."""
    mark = {"cornerRadiusEnd": 4}
    if not temporal:
        mark["size"] = 28
    elif not df.empty:
        # Size bars to the number of time slots in view so a month of days and a year of weeks both read well.
        dates = pd.to_datetime(df[x]).sort_values()
        step = int(dates.diff().dt.days.dropna().min() or 1) if len(dates) > 1 else 1
        slots = (dates.iloc[-1] - dates.iloc[0]).days // max(step, 1) + 1
        mark["size"] = max(3, min(24, int(520 / slots * 0.6)))
    if not isinstance(color, dict):
        mark["color"] = color or common.BLUE
    x_enc = alt.X(f"{x}:{'T' if temporal else 'N'}", title=x_title, sort=None, axis=alt.Axis(labelAngle=0, grid=False))
    y_enc = alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(tickMinStep=1, gridColor="#eeeeeb"))
    enc = {"tooltip": list(df.columns)}
    if horizontal:
        enc.update(x=y_enc, y=alt.Y(f"{x}:N", title=x_title, sort=None))
    else:
        enc.update(x=x_enc, y=y_enc)
    if isinstance(color, dict):
        enc["color"] = alt.Color(f"{x}:N", scale=alt.Scale(domain=list(color), range=list(color.values())), legend=None)
    return alt.Chart(df).mark_bar(**mark).encode(**enc).properties(height=240)


def _show(title: str, chart: alt.Chart, df: pd.DataFrame, empty_msg: str) -> None:
    st.markdown(f"**{title}**")
    if df.empty or (df.select_dtypes("number").sum().sum() == 0):
        st.caption(empty_msg)
        return
    st.altair_chart(chart, use_container_width=True)
    with st.expander("Data", expanded=False):
        st.dataframe(df, hide_index=True, use_container_width=True)


def render() -> None:
    common.backend_caption()
    store = common.store()
    st.title("Progress")

    col_range, col_refresh = st.columns([3, 1])
    days = RANGES[col_range.selectbox("Range", list(RANGES), label_visibility="collapsed")]
    if col_refresh.button("Refresh", use_container_width=True):
        st.rerun()

    try:
        cards = store.all_cards()
        reviews = store.reviews()
        stats = store.stats()
    except AnkiError as e:
        st.error(f"Could not read from Anki: {e}")
        return
    entries = common.history().entries()

    ret = analytics.retention(reviews, days)
    active = analytics.active_days(reviews, entries)
    tiles = st.columns(5)
    tiles[0].metric("Cards", stats["total"])
    tiles[1].metric("Due now", stats["due_today"])
    tiles[2].metric("Mature", stats["mature"])
    tiles[3].metric("Retention", f"{ret:.0%}" if ret is not None else "–")
    tiles[4].metric("Streak", f"{analytics.streak(active)} d")

    left, right = st.columns(2)
    with left:
        df = analytics.reviews_by_day(reviews, days)
        _show("Reviews per day", _bar(df, "day", "reviews", x_title="", y_title="reviews", temporal=True), df,
              "No reviews in this range yet. Ask the coach for a quiz.")
    with right:
        df = analytics.reviews_by_day(reviews, days)
        acc = df[["day", "accuracy"]] if not df.empty else df
        chart = (
            alt.Chart(acc).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60), color=common.BLUE)
            .encode(x=alt.X("day:T", title="", axis=alt.Axis(grid=False)),
                    y=alt.Y("accuracy:Q", title="accuracy", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                    tooltip=["day", alt.Tooltip("accuracy", format=".0%")])
            .properties(height=240)
        )
        _show("Accuracy per day", chart, acc, "Accuracy appears once you have reviewed cards.")

    left, right = st.columns(2)
    with left:
        df = analytics.cards_added_by_week(cards)
        _show("Cards added per week", _bar(df, "week", "cards", x_title="", y_title="cards", temporal=True), df,
              "No cards yet.")
    with right:
        df = analytics.state_breakdown(cards)
        _show("Cards by stage", _bar(df, "state", "cards", x_title="", y_title="cards", color=common.BLUE_STEPS, horizontal=True), df,
              "No cards yet.")

    left, right = st.columns(2)
    with left:
        df = analytics.interval_histogram(cards)
        _show("Review intervals", _bar(df, "interval", "cards", x_title="", y_title="cards"), df,
              "Intervals appear after the first reviews.")
    with right:
        df = analytics.jlpt_breakdown(cards)
        colors = {"N5": "#86b6ef", "N4": "#6da7ec", "N3": "#5598e7", "N2": "#2a78d6", "N1": "#184f95", "Unknown": common.GRAY}
        _show("Cards by JLPT level", _bar(df, "level", "cards", x_title="", y_title="cards", color=colors), df, "No cards yet.")

    left, right = st.columns(2)
    with left:
        df = analytics.sentences_by_day(entries, days)
        _show("Sentences studied per day", _bar(df, "day", "sentences", x_title="", y_title="sentences", temporal=True), df,
              "Paste a sentence in the chat to start the log.")
    with right:
        st.markdown("**Most looked-up words**")
        df = analytics.top_lookups(entries)
        if df.empty:
            st.caption("Dictionary lookups the coach makes will show up here.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)

"""Chat page: talk to the coach, drop screenshots, get quizzed."""

from __future__ import annotations

import anthropic
import streamlit as st

from coach.history import contains_japanese
from coach.ui import common

QUIZ_PROMPT = "Quiz me on my due flashcards, one at a time."
IMAGE_TYPES = ["png", "jpg", "jpeg", "webp", "gif"]


def _tool_summary(name: str, inp: dict) -> str:
    if name == "lookup_word":
        return f"Looked up **{inp.get('word', '')}**"
    if name == "add_flashcard":
        return f"Saved flashcard **{inp.get('word', '')}**"
    if name == "list_due_cards":
        return "Fetched due cards"
    if name == "record_review":
        return f"Recorded review (grade {inp.get('grade', '?')})"
    if name == "deck_stats":
        return "Read deck stats"
    return name


def _render_transcript() -> None:
    for entry in st.session_state.transcript:
        with st.chat_message(entry["role"]):
            if entry.get("image"):
                st.image(entry["image"], width=320)
            if entry.get("tools"):
                with st.expander(f"{len(entry['tools'])} tool call(s)", expanded=False):
                    for line in entry["tools"]:
                        st.markdown(f"- {line}")
            st.markdown(entry["text"])


def _handle(text: str, image: tuple[bytes, str] | None) -> None:
    coach = common.coach()
    history = common.history()

    st.session_state.transcript.append({"role": "user", "text": text, "image": image[0] if image else None})
    with st.chat_message("user"):
        if image:
            st.image(image[0], width=320)
        st.markdown(text)

    if contains_japanese(text) or image:
        history.log("sentence", text=text[:300], has_image=bool(image))

    with st.chat_message("assistant"):
        status = st.status("Thinking…", expanded=False)
        box = st.empty()
        buf: list[str] = []
        tool_lines: list[str] = []

        def on_delta(fragment: str) -> None:
            buf.append(fragment)
            box.markdown("".join(buf) + " ▌")

        def on_tool(name: str, inp: dict) -> None:
            line = _tool_summary(name, inp)
            tool_lines.append(line)
            status.update(label=line.replace("**", ""))
            status.write(line)
            if buf and not "".join(buf).endswith("\n"):
                buf.append("\n\n")

        error = None
        try:
            coach.send(text, image_bytes=image, on_text=None, on_delta=on_delta, on_tool=on_tool)
        except anthropic.RateLimitError:
            error = "Rate limited by the API. Wait a moment and try again."
        except anthropic.AuthenticationError:
            error = "Invalid API key. Set ANTHROPIC_API_KEY and restart."
        except anthropic.APIStatusError as e:
            error = f"API error {e.status_code}: {e.message}"
        except anthropic.APIConnectionError:
            error = "Could not reach the Anthropic API. Check your connection."
        except TypeError as e:
            # The SDK raises TypeError at request time when no credentials resolve.
            if "authentication" not in str(e).lower():
                raise
            error = "No Anthropic credentials found. Export ANTHROPIC_API_KEY before running `uv run coach ui`."

        status.update(label="Done" if not error else "Failed", state="complete" if not error else "error")
        final = "".join(buf).strip()
        if error:
            st.error(error)
            final = final or f"_{error}_"
        box.markdown(final)
        st.session_state.transcript.append({"role": "assistant", "text": final, "tools": tool_lines})


def render() -> None:
    st.session_state.setdefault("transcript", [])
    common.backend_caption()

    with st.sidebar:
        st.markdown("### Quick actions")
        if st.button("Quiz me on due cards", use_container_width=True):
            st.session_state.pending_prompt = QUIZ_PROMPT
        if st.button("Deck summary", use_container_width=True):
            st.session_state.pending_prompt = "How is my deck doing? Give me the stats and one suggestion."
        if st.button("New conversation", use_container_width=True, type="secondary"):
            common.coach().reset()
            st.session_state.transcript = []
            st.rerun()
        st.caption(f"Model: {common.settings().model} · effort {common.settings().effort}")

    st.title("Japanese Study Coach")
    if not common.has_credentials():
        st.error(
            "No Anthropic credentials found. Export `ANTHROPIC_API_KEY` in the shell that runs `uv run coach ui`, "
            "then restart the app."
        )
        return
    if not st.session_state.transcript:
        st.caption("Paste a sentence, drop a screenshot, or ask for a quiz. Readings, grammar, and flashcards happen here.")

    _render_transcript()

    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        _handle(pending, None)
        return

    prompt = st.chat_input("Paste Japanese text or drop a screenshot…", accept_file=True, file_type=IMAGE_TYPES)
    if prompt:
        files = getattr(prompt, "files", None) or []
        text = (getattr(prompt, "text", "") or "").strip()
        image = (files[0].getvalue(), files[0].type or "image/png") if files else None
        if not text and image:
            text = "Explain the Japanese in this screenshot."
        if text:
            _handle(text, image)

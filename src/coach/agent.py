"""The coach agent: system prompt, model settings, and the conversation loop."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Callable

import anthropic

from .tools import TOOLS

MODEL = "claude-opus-5"

SYSTEM_PROMPT = """You are a patient, precise Japanese tutor working one-on-one with a learner.

The learner will paste sentences, words, or screenshots of Japanese text (often from manga, games, or apps). Your job:

1. Explain what the text means, naturally and briefly.
2. Break down vocabulary and grammar the learner is likely not to know yet. Give readings in hiragana, never romaji unless asked.
3. Use the lookup_word tool to confirm readings and meanings instead of guessing, especially for kanji compounds and rare words.
4. Offer to save useful words as flashcards. Only call add_flashcard when the learner agrees or explicitly asks. When saving, use the sentence they gave you as the example.
5. When the learner asks for a quiz or review, call list_due_cards, then quiz one card at a time: show the word (and example if helpful), wait for their answer, tell them if they were right, and call record_review with an honest grade. Ask them how hard it felt if you cannot tell.

Style: conversational, no long lectures. Prefer a short table or list for vocabulary breakdowns. Match the learner's level: if they are reading simple sentences, keep explanations simple. Point out common pitfalls (similar kanji, tricky particles, pitch-accent traps) only when relevant.
"""

TextHandler = Callable[[str], None]


def image_block(path: str | Path) -> dict:
    """Build a base64 image content block from a local file."""
    p = Path(path)
    media_type = mimetypes.guess_type(p.name)[0] or "image/png"
    data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


class Coach:
    """Holds one conversation with the tutor and drives the tool loop."""

    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL, effort: str = "medium"):
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.messages: list[dict] = []

    def send(self, text: str, image: str | Path | None = None, on_text: TextHandler = print) -> str:
        """Send one user turn, run tools until Claude is done, return the final text."""
        content: list[dict] = []
        if image:
            content.append(image_block(image))
        content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content})

        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": self.effort},
            tools=TOOLS,
            messages=self.messages,
        )

        final_text = ""
        for message in runner:
            # Mirror history: the runner keeps its own copy and does not expose it.
            self.messages.append({"role": "assistant", "content": message.content})
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                self.messages.append(tool_response)

            if message.stop_reason == "refusal":
                final_text = "(The model declined to answer this request.)"
                on_text(final_text)
                break

            chunk = "".join(b.text for b in message.content if b.type == "text")
            if chunk:
                on_text(chunk)
                final_text = chunk
        return final_text

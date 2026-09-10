"""The coach agent: system prompt, model settings, and the conversation loop."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Callable

import anthropic

from .tools import TOOLS

MODEL = "claude-opus-5"
MAX_TOOL_ITERATIONS = 12

SYSTEM_PROMPT = """You are a patient, precise Japanese tutor working one-on-one with a learner.

The learner will paste sentences, words, or screenshots of Japanese text (often from manga, games, or apps). Your job:

1. Explain what the text means, naturally and briefly.
2. Break down vocabulary and grammar the learner is likely not to know yet. Give readings in hiragana, never romaji unless asked.
3. Use the lookup_word tool to confirm readings and meanings instead of guessing, especially for kanji compounds and rare words.
4. Offer to save useful words as flashcards. Only call add_flashcard when the learner agrees or explicitly asks. When saving, use the sentence they gave you as the example and pass the JLPT level from the dictionary result if there was one. The tool result says whether the card went to Anki or the local deck; mention it in a few words.
5. When the learner asks for a quiz or review, call list_due_cards, then quiz one card at a time: show the word (and example if helpful), wait for their answer, tell them if they were right, and call record_review with an honest grade. Ask them how hard it felt if you cannot tell. Never reveal the reading or meaning before they answer.

Style: conversational, no long lectures. Prefer a short table or list for vocabulary breakdowns. Match the learner's level: if they are reading simple sentences, keep explanations simple. Point out common pitfalls (similar kanji, tricky particles, pitch-accent traps) only when relevant.
"""

TextHandler = Callable[[str], None]
ToolHandler = Callable[[str, dict], None]


def image_block(path: str | Path) -> dict:
    """Build a base64 image content block from a local file."""
    p = Path(path)
    media_type = mimetypes.guess_type(p.name)[0] or "image/png"
    return image_block_from_bytes(p.read_bytes(), media_type)


def image_block_from_bytes(data: bytes, media_type: str = "image/png") -> dict:
    encoded = base64.standard_b64encode(data).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}}


class Coach:
    """Holds one conversation with the tutor and drives the tool loop."""

    def __init__(self, client: anthropic.Anthropic | None = None, model: str = MODEL, effort: str = "medium"):
        self.client = client or anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.messages: list[dict] = []

    def reset(self) -> None:
        self.messages = []

    def send(
        self,
        text: str,
        image: str | Path | None = None,
        image_bytes: tuple[bytes, str] | None = None,
        on_text: TextHandler | None = print,
        on_delta: TextHandler | None = None,
        on_tool: ToolHandler | None = None,
    ) -> str:
        """Send one user turn, run tools until Claude is done, return the final text.

        on_delta receives streamed text fragments as they arrive; on_text receives
        each complete assistant text chunk; on_tool is called for each tool call.
        """
        content: list[dict] = []
        if image:
            content.append(image_block(image))
        if image_bytes:
            content.append(image_block_from_bytes(*image_bytes))
        content.append({"type": "text", "text": text})
        self.messages.append({"role": "user", "content": content})

        runner = self.client.beta.messages.tool_runner(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": self.effort},
            tools=TOOLS,
            messages=self.messages,
            max_iterations=MAX_TOOL_ITERATIONS,
            stream=True,
        )

        final_text = ""
        for stream in runner:
            for fragment in stream.text_stream:
                if on_delta:
                    on_delta(fragment)
            message = stream.get_final_message()

            # Mirror history: the runner keeps its own copy and does not expose it.
            self.messages.append({"role": "assistant", "content": message.content})

            if message.stop_reason == "refusal":
                final_text = "(The model declined to answer this request.)"
                if on_text:
                    on_text(final_text)
                break

            chunk = "".join(b.text for b in message.content if b.type == "text")
            if chunk:
                final_text = chunk
                if on_text:
                    on_text(chunk)

            for block in message.content:
                if block.type == "tool_use" and on_tool:
                    on_tool(block.name, dict(block.input))

            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                self.messages.append(tool_response)
        return final_text

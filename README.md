# Japanese Study Coach

A small Claude agent that tutors you through Japanese text. Paste a sentence or a screenshot, and it explains the meaning, breaks down vocabulary and grammar, confirms readings against a dictionary, and saves words you want to keep into a spaced-repetition deck it can quiz you on later.

## How it works

The agent is a plain tool-use loop built on the Anthropic Python SDK's tool runner. Claude decides when to call these tools:

| Tool | What it does |
| --- | --- |
| `lookup_word` | Queries the Jisho dictionary API (JMdict) for readings and meanings |
| `add_flashcard` | Saves a word to `data/deck.json` |
| `list_due_cards` | Returns cards due for review |
| `record_review` | Grades a card 0-5 and reschedules it with SM-2 |
| `deck_stats` | Deck summary |

The code is split so each piece is easy to read on its own:

- `src/coach/agent.py` - system prompt, model settings, conversation loop
- `src/coach/tools.py` - the `@beta_tool` functions Claude can call
- `src/coach/dictionary.py` - Jisho lookup
- `src/coach/srs.py` - deck storage and scheduling
- `src/coach/cli.py` - command-line interface

## Setup

```bash
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
uv run coach                          # interactive chat
uv run coach "猫が寝ている。"           # start with a sentence
uv run coach --image screenshot.png   # explain a screenshot
uv run coach quiz                     # review due flashcards
uv run coach stats                    # deck summary, no API call
```

Add `--once` to answer and exit instead of staying in chat. `--effort low|medium|high` trades speed for thoroughness (default `medium`).

## Tests

```bash
uv run pytest
```

Tests cover the scheduler, dictionary parsing, and tool behavior without calling the API or the network.

## Ideas for next steps

- Feed OCR output from your Japanese OCR app straight into `coach.send()`
- Export the deck to Anki (`.apkg` or TSV)
- Add a `grammar_lookup` tool backed by a grammar reference
- Track which sentences each word was seen in

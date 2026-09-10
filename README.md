# Japanese Study Coach

A Claude agent that tutors you through Japanese text, with a Streamlit app, Anki integration, and a progress dashboard.

Paste a sentence or drop a screenshot. The coach explains the meaning, breaks down vocabulary and grammar, confirms readings against a dictionary, and saves the words you want to keep straight into Anki. Later it quizzes you on what is due and grades your answers into Anki's scheduler.

## Quick start

```bash
uv sync
export ANTHROPIC_API_KEY=sk-ant-...
uv run coach ui
```

The app opens at http://localhost:8501 with four pages:

| Page | What it does |
| --- | --- |
| **Coach** | Chat with the tutor. Streams answers, shows tool calls, accepts screenshots. Sidebar shortcuts start a quiz or a deck summary. |
| **Deck** | Browse every card with its stage and interval, filter, add words by hand from a dictionary lookup, trigger an AnkiWeb sync. |
| **Progress** | Reviews per day, accuracy, cards added per week, cards by stage, review intervals, JLPT breakdown, sentences studied, most looked-up words. |
| **Settings** | Choose Anki or the local deck, test the AnkiConnect link, create the deck and note type, pick the model and effort. |

The terminal client still works too:

```bash
uv run coach "猫が寝ている。"        # start a chat with a sentence
uv run coach --image screenshot.png  # explain a screenshot
uv run coach quiz                    # review due cards
uv run coach stats                   # deck summary, no API call
```

## Anki

The coach talks to Anki desktop through the [AnkiConnect](https://git.sr.ht/~foosoft/anki-connect) add-on.

1. In Anki: Tools → Add-ons → Get Add-ons, enter code `2055492159`, restart Anki.
2. Keep Anki open while you use the coach.
3. On first contact the coach creates a deck called **Japanese Coach** and a note type of the same name with fields Word, Reading, Meaning, Example, Notes. Both names are configurable in Settings.

What syncs:

- **Saving a word** adds a note to the deck, tagged `coach` plus its JLPT level. Duplicates within the deck are detected and reused.
- **Quizzing** pulls due and new cards from Anki and answers them through Anki's scheduler. Coach grades 0-2 map to Again, 3 to Hard, 4 to Good, 5 to Easy.
- **Progress** reads Anki's own review log for the deck, so reviews you do inside Anki count as well.

**macOS note.** App Nap suspends Anki when it is not the front window, which makes AnkiConnect slow or unresponsive. Disable it once:

```bash
defaults write net.ankiweb.dtop NSAppSleepDisabled -bool true
```

If Anki is not running, the coach falls back to a local JSON deck in `data/deck.json` with a simple SM-2 scheduler, and says so in the sidebar. Set the backend to "Anki only" in Settings to disable the fallback.

## How it works

The agent is a plain tool-use loop built on the Anthropic Python SDK's tool runner. Claude decides when to call these tools:

| Tool | What it does |
| --- | --- |
| `lookup_word` | Queries the Jisho dictionary API (JMdict) for readings, meanings, and JLPT level |
| `add_flashcard` | Saves a word to Anki or the local deck |
| `list_due_cards` | Returns cards due for review |
| `record_review` | Grades a card 0-5 and reschedules it |
| `deck_stats` | Deck summary |

Layout:

- `src/coach/agent.py` - system prompt, model settings, streaming conversation loop
- `src/coach/tools.py` - the `@beta_tool` functions Claude can call
- `src/coach/store.py` - one flashcard interface with Anki and local implementations
- `src/coach/anki.py` - AnkiConnect client
- `src/coach/srs.py` - local deck with SM-2 scheduling
- `src/coach/dictionary.py` - Jisho lookup
- `src/coach/history.py` - study log (sentences, lookups, cards, reviews)
- `src/coach/analytics.py` - progress metrics as pandas frames
- `src/coach/ui/` - Streamlit pages
- `src/coach/cli.py` - command-line interface

Settings live in `data/settings.json`; the study log in `data/history.jsonl`. The `data/` folder is gitignored.

## Tests

```bash
uv run pytest
```

Tests cover the scheduler, dictionary parsing, the AnkiConnect client and store (against an in-memory fake), analytics, history, and the tools. Nothing in the suite touches the API, the network, or a real Anki.

## Ideas for next steps

- Send OCR output from the Japanese OCR app straight into the coach
- Grammar point lookups backed by a grammar reference
- Sentence mining: keep every sentence a word was seen in on the Anki note
- Audio on cards via a pronunciation source

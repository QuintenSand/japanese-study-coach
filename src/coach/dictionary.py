"""Dictionary lookup against the public Jisho API (backed by JMdict).

No API key is needed. Results are trimmed to the fields a tutor actually
uses so the tool result stays small in Claude's context.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

JISHO_URL = "https://jisho.org/api/v1/search/words?keyword="


def parse_jisho(payload: dict, limit: int = 3) -> list[dict]:
    """Reduce a raw Jisho response to a compact list of entries."""
    entries = []
    for item in payload.get("data", [])[:limit]:
        forms = item.get("japanese") or [{}]
        senses = []
        for sense in item.get("senses", [])[:3]:
            senses.append(
                {
                    "meanings": sense.get("english_definitions", []),
                    "pos": sense.get("parts_of_speech", []),
                    "tags": sense.get("tags", []),
                }
            )
        entries.append(
            {
                "word": forms[0].get("word") or forms[0].get("reading", ""),
                "reading": forms[0].get("reading", ""),
                "other_forms": [f.get("word") for f in forms[1:4] if f.get("word")],
                "common": bool(item.get("is_common")),
                "jlpt": item.get("jlpt", []),
                "senses": senses,
            }
        )
    return entries


def lookup(word: str, limit: int = 3, timeout: float = 10.0) -> list[dict]:
    url = JISHO_URL + urllib.parse.quote(word)
    req = urllib.request.Request(url, headers={"User-Agent": "japanese-study-coach/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return parse_jisho(payload, limit=limit)

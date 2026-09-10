"""Append-only study log (JSON lines) for things the coach observed.

Kinds: sentence (text the learner studied), lookup (dictionary query),
card_added, review. This is coach-side data, independent of Anki.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

JAPANESE = re.compile(r"[぀-ヿ一-鿿]")


def contains_japanese(text: str) -> bool:
    return bool(JAPANESE.search(text))


class History:
    def __init__(self, path: Path):
        self.path = Path(path)

    def log(self, kind: str, **data) -> dict:
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind, **data}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

"""User settings, persisted as JSON in the data directory."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("COACH_DATA_DIR", "data"))


@dataclass
class Settings:
    backend: str = "auto"  # auto | anki | local
    anki_url: str = "http://127.0.0.1:8765"
    anki_deck: str = "Japanese Coach"
    anki_model: str = "Japanese Coach"
    model: str = "claude-opus-5"
    effort: str = "medium"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or data_dir() / "settings.json"
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

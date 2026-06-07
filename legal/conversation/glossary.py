from __future__ import annotations

import json
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_plain_language_glossary.json"


class Glossary:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.entries = {str(key): str(value) for key, value in (self.config.get("entries") or {}).items()}

    def lookup(self, term: str) -> str | None:
        return self.entries.get(term.lower())

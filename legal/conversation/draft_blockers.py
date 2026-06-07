from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_drafting_conversation_rules.json"


class DraftBlockerDetector:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    def detect(self, *, draft_type: str, payload: dict[str, Any], intake: dict[str, Any]) -> list[str]:
        blockers: list[str] = []
        if not intake.get("supported"):
            blockers.append("unsupported_draft_type")
        if intake.get("missing_required_fields"):
            blockers.append("missing_required_facts")
        if not payload.get("source_cards") and not payload.get("citations"):
            blockers.append("missing_verified_sources")
        text = " ".join(str(value) for value in payload.values()).lower()
        for phrase in self.config.get("bypass_phrases", []):
            if phrase in text:
                blockers.append("filing_ready_bypass_attempt")
        return list(dict.fromkeys(blockers))

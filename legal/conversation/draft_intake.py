from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_drafting_conversation_rules.json"


class DraftIntakeAnalyzer:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))

    def supported_draft_types(self) -> set[str]:
        return set(self.config.get("supported_draft_types") or {})

    def required_fields(self, draft_type: str) -> list[str]:
        return list((self.config.get("supported_draft_types") or {}).get(draft_type, []))

    def analyze(self, draft_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        required = self.required_fields(draft_type)
        provided = {key for key, value in payload.items() if value not in (None, "", [], {}, ())}
        return {
            "draft_type": draft_type,
            "supported": draft_type in self.supported_draft_types(),
            "missing_required_fields": [field for field in required if field not in provided],
            "provided_fields": sorted(provided),
            "review_required": True,
        }

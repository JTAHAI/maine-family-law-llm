from __future__ import annotations

import json
from pathlib import Path

from legal.conversation.source_card_presenter import STATUS_LABELS


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_ui_copy.json"


def stable_status_labels() -> dict[str, str]:
    return dict(STATUS_LABELS)


def blocked_state_explanations() -> dict[str, str]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in (payload.get("blocked_states") or {}).items()}

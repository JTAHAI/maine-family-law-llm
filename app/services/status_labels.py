from __future__ import annotations

import json
from pathlib import Path

from legal.conversation.source_card_presenter import STATUS_LABELS


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_ui_copy.json"


def stable_status_labels() -> dict[str, str]:
    labels = dict(STATUS_LABELS)
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    workbench_path = Path(__file__).resolve().parents[2] / "configs" / "maine_workbench_ui_copy.json"
    if workbench_path.is_file():
        workbench = json.loads(workbench_path.read_text(encoding="utf-8"))
        labels.update({str(key): str(value) for key, value in (workbench.get("status_labels") or {}).items()})
    labels.update({str(key): str(value) for key, value in (payload.get("blocked_states") or {}).items() if key not in labels})
    return labels


def blocked_state_explanations() -> dict[str, str]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    explanations = {str(key): str(value) for key, value in (payload.get("blocked_states") or {}).items()}
    workbench_path = Path(__file__).resolve().parents[2] / "configs" / "maine_workbench_ui_copy.json"
    if workbench_path.is_file():
        workbench = json.loads(workbench_path.read_text(encoding="utf-8"))
        explanations.update({str(key): str(value) for key, value in (workbench.get("blocked_explanations") or {}).items()})
    return explanations

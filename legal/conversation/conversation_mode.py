from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_conversation_modes.json"


@dataclass(frozen=True)
class ConversationMode:
    mode: str
    audiences: tuple[str, ...]
    description: str
    renderer: str
    tone_tags: tuple[str, ...]
    review_required_default: bool = True
    plain_language: bool = False

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "ConversationMode":
        return cls(
            mode=str(row["mode"]),
            audiences=tuple(str(item) for item in row.get("audiences") or ()),
            description=str(row.get("description") or ""),
            renderer=str(row.get("renderer") or "quick_answer"),
            tone_tags=tuple(str(item) for item in row.get("tone_tags") or ()),
            review_required_default=bool(row.get("review_required_default", True)),
            plain_language=bool(row.get("plain_language", False)),
        )


class ConversationModeCatalog:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._modes = {
            item.mode: item
            for item in (ConversationMode.from_dict(row) for row in self.config.get("modes", []))
        }

    def get(self, mode: str) -> ConversationMode:
        return self._modes[mode]

    def required_modes(self) -> set[str]:
        return set(self._modes)

    def default_mode_for_audience(self, audience: str) -> str:
        defaults = self.config.get("audience_defaults") or {}
        return str(defaults.get(audience) or self.config.get("default_mode") or "self_represented_plain_language")

    def route(
        self,
        *,
        audience: str,
        task_type: str,
        issue_labels: list[str] | None = None,
        explicit_mode: str | None = None,
    ) -> ConversationMode:
        if explicit_mode and explicit_mode in self._modes:
            return self._modes[explicit_mode]
        issue_overrides = self.config.get("issue_mode_overrides") or {}
        for label in issue_labels or []:
            if label in issue_overrides:
                return self._modes[str(issue_overrides[label])]
        audience_overrides = (self.config.get("task_overrides") or {}).get(audience) or {}
        if task_type in audience_overrides:
            return self._modes[str(audience_overrides[task_type])]
        task_defaults = self.config.get("task_type_defaults") or {}
        task_default = str(task_defaults.get(task_type) or "")
        default_mode = str(self.config.get("default_mode") or "self_represented_plain_language")
        if task_default and task_default != default_mode:
            return self._modes[task_default]
        mode_name = str(
            self.default_mode_for_audience(audience)
            or task_default
        )
        return self._modes[mode_name]

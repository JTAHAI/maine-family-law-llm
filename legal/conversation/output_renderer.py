from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_output_templates.json"


class OutputRenderer:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))

    def required_renderers(self) -> set[str]:
        return set(self.config.get("required_renderers", []))

    def render(self, response: dict[str, Any], renderer: str, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        template = (self.config.get("templates") or {}).get(renderer)
        if template is None:
            raise KeyError(f"Unknown renderer: {renderer}")
        sections = []
        for section_name in template.get("sections", []):
            sections.append(
                {
                    "section": section_name,
                    "value": self._section_value(response, section_name, extra or {}),
                }
            )
        return {
            "renderer": renderer,
            "title": template.get("title"),
            "sections": sections,
            "visible_blockers": list(response.get("filing_ready_blockers") or []),
            "review_required": bool(response.get("review_required", True)),
        }

    def _section_value(self, response: dict[str, Any], section_name: str, extra: dict[str, Any]) -> Any:
        if section_name == "source_status":
            return {
                "source_scope_status": response.get("source_scope_status"),
                "source_freshness_status": response.get("source_freshness_status"),
            }
        if section_name == "issue":
            return {
                "issue_labels": response.get("issue_labels"),
                "task_type": response.get("task_type"),
                "procedural_posture": response.get("procedural_posture"),
            }
        if section_name == "blockers":
            return response.get("filing_ready_blockers") or response.get("warnings") or []
        if section_name == "what_this_means":
            return extra.get("what_this_means") or response.get("short_answer")
        if section_name == "what_this_does_not_mean":
            return extra.get("what_this_does_not_mean") or response.get("limitations")
        if section_name == "analysis":
            return response.get("explanation")
        return response.get(section_name, extra.get(section_name))

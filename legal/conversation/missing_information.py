from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.conversation.intake_schema import IntakeSchemaCatalog


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_missing_information_rules.json"


@dataclass(frozen=True)
class MissingInformationItem:
    field: str
    severity: str
    reason: str
    audience_prompt: str
    category: str

    def as_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "severity": self.severity,
            "reason": self.reason,
            "audience_prompt": self.audience_prompt,
            "category": self.category,
        }


class MissingInformationEngine:
    def __init__(
        self,
        *,
        schema_catalog: IntakeSchemaCatalog | None = None,
        config_path: str | Path = CONFIG_PATH,
    ) -> None:
        self.schema_catalog = schema_catalog or IntakeSchemaCatalog()
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))

    def analyze(
        self,
        *,
        workflow: str,
        payload: dict[str, Any],
        audience: str,
        text: str = "",
    ) -> list[MissingInformationItem]:
        validation = self.schema_catalog.validate_payload(workflow, payload)
        items: list[MissingInformationItem] = []
        for field_name in validation.missing_required:
            prompt = self.schema_catalog.question_for(workflow, field_name, audience) or f"Please provide {field_name.replace('_', ' ')}."
            items.append(
                MissingInformationItem(
                    field=field_name,
                    severity="required",
                    reason="Required information is missing for this workflow.",
                    audience_prompt=prompt,
                    category="missing_required_information",
                )
            )
        for field_name in validation.missing_recommended:
            prompt = self.schema_catalog.question_for(workflow, field_name, audience) or f"If available, share {field_name.replace('_', ' ')}."
            items.append(
                MissingInformationItem(
                    field=field_name,
                    severity="recommended",
                    reason="This information is helpful but not always strictly required.",
                    audience_prompt=prompt,
                    category="missing_recommended_information",
                )
            )
        searchable = " ".join([text, *[str(value) for value in payload.values()]])
        low = searchable.lower()
        for row in self.config.get("rules", []):
            if any(keyword in low for keyword in row.get("keywords", [])):
                items.append(
                    MissingInformationItem(
                        field=str(row.get("rule_id") or "risk"),
                        severity=str(row.get("severity") or "warning"),
                        reason=str(row.get("message") or "Risk detected."),
                        audience_prompt=str(row.get("message") or "Risk detected."),
                        category="risk_signal",
                    )
                )
        return items

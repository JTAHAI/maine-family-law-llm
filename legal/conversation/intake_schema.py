from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_intake_schemas.json"


@dataclass(frozen=True)
class WorkflowSchema:
    workflow: str
    required_fields: tuple[str, ...]
    recommended_fields: tuple[str, ...]
    sensitive_fields: tuple[str, ...]
    questions: dict[str, dict[str, str]]


@dataclass
class IntakeValidationResult:
    workflow: str
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    provided_sensitive_fields: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "missing_required": self.missing_required,
            "missing_recommended": self.missing_recommended,
            "provided_sensitive_fields": self.provided_sensitive_fields,
            "unknown_fields": self.unknown_fields,
        }


class IntakeSchemaCatalog:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._workflows = {
            name: WorkflowSchema(
                workflow=name,
                required_fields=tuple(row.get("required_fields", [])),
                recommended_fields=tuple(row.get("recommended_fields", [])),
                sensitive_fields=tuple(row.get("sensitive_fields", [])),
                questions={str(key): dict(value) for key, value in (row.get("questions") or {}).items()},
            )
            for name, row in (self.config.get("workflows") or {}).items()
        }

    def get(self, workflow: str) -> WorkflowSchema:
        return self._workflows[workflow]

    def required_workflows(self) -> set[str]:
        return set(self._workflows)

    def validate_payload(self, workflow: str, payload: dict[str, Any]) -> IntakeValidationResult:
        schema = self.get(workflow)
        provided = {key for key, value in payload.items() if value not in (None, "", [], {}, ())}
        allowed = set(schema.required_fields) | set(schema.recommended_fields) | set(schema.sensitive_fields)
        return IntakeValidationResult(
            workflow=workflow,
            missing_required=[field for field in schema.required_fields if field not in provided],
            missing_recommended=[field for field in schema.recommended_fields if field not in provided],
            provided_sensitive_fields=[field for field in schema.sensitive_fields if field in provided],
            unknown_fields=sorted(field for field in provided if field not in allowed),
        )

    def question_for(self, workflow: str, field_name: str, audience: str) -> str | None:
        questions = self.get(workflow).questions.get(field_name) or {}
        return questions.get(audience) or questions.get("self_represented")

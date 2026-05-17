from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_GOLD_REQUIRED_FIELDS = {
    "source_id",
    "source_class",
    "jurisdiction",
    "text_span",
    "label",
    "annotator_or_generation_method",
    "confidence",
    "hash",
    "created_at",
    "review_status",
    "private_data_allowed_for_training",
}


@dataclass(frozen=True)
class JsonlDatasetSummary:
    path: str
    rows: int
    parse_errors: int
    schema_path: str | None = None
    schema_required_fields: list[str] = field(default_factory=list)
    schema_missing: bool = False
    schema_violations: int = 0
    private_training_rows: int = 0


class BenchmarkRunner:
    """Validate local evaluation assets without pretending they prove legal quality."""

    def __init__(self, eval_data_dir: str | Path = "eval_data") -> None:
        self.eval_data_dir = Path(eval_data_dir)

    def _relative_path(self, path: Path) -> str:
        return (
            path.relative_to(self.eval_data_dir.parent).as_posix()
            if path.is_relative_to(self.eval_data_dir.parent)
            else path.as_posix()
        )

    def _schema_for(self, path: Path) -> tuple[Path | None, set[str]]:
        schema_path = self.eval_data_dir / "schemas" / f"{path.stem}.schema.json"
        if not schema_path.exists():
            return None, set()
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return schema_path, set()
        return schema_path, set(schema.get("required") or ())

    def _summarize_jsonl(self, path: Path) -> JsonlDatasetSummary:
        rows = 0
        parse_errors = 0
        schema_violations = 0
        private_training_rows = 0
        schema_path, required_fields = self._schema_for(path)

        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                    rows += 1
                except json.JSONDecodeError:
                    parse_errors += 1
                    continue
                if required_fields and not required_fields <= set(row):
                    schema_violations += 1
                if row.get("private_data_allowed_for_training") is True:
                    private_training_rows += 1

        return JsonlDatasetSummary(
            path=self._relative_path(path),
            rows=rows,
            parse_errors=parse_errors,
            schema_path=self._relative_path(schema_path) if schema_path else None,
            schema_required_fields=sorted(required_fields),
            schema_missing=schema_path is None,
            schema_violations=schema_violations,
            private_training_rows=private_training_rows,
        )

    def run(self) -> dict[str, Any]:
        if not self.eval_data_dir.exists():
            return {
                "status": "fail",
                "reason": "eval_data_dir_missing",
                "datasets": [],
                "dataset_count": 0,
                "total_rows": 0,
                "parse_errors": 0,
            }

        summaries = [
            self._summarize_jsonl(path)
            for path in sorted(self.eval_data_dir.glob("*.jsonl"))
        ]
        total_rows = sum(summary.rows for summary in summaries)
        parse_errors = sum(summary.parse_errors for summary in summaries)
        schema_violations = sum(summary.schema_violations for summary in summaries)
        private_training_rows = sum(summary.private_training_rows for summary in summaries)
        schema_missing = sum(1 for summary in summaries if summary.schema_missing)
        pass_status = bool(summaries) and parse_errors == 0 and schema_violations == 0 and schema_missing == 0

        return {
            "status": "pass" if pass_status else "fail",
            "datasets": [summary.__dict__ for summary in summaries],
            "dataset_count": len(summaries),
            "total_rows": total_rows,
            "parse_errors": parse_errors,
            "schema_violations": schema_violations,
            "schemas_missing": schema_missing,
            "private_training_rows": private_training_rows,
            "base_required_fields": sorted(BASE_GOLD_REQUIRED_FIELDS),
            # These are explicitly not enterprise legal-quality metrics yet.
            "retrieval_accuracy": None,
            "citation_validity": None,
            "quote_span_accuracy": None,
            "hallucination_rate": None,
            "metric_basis": "schema_validated_synthetic_seed_only_not_attorney_gold",
        }

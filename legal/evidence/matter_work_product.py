from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from legal.matter.models import IntakeReport, MatterDocument


@dataclass(frozen=True)
class MatterWorkProduct:
    matter_id: str
    issue_tree: dict[str, Any]
    procedural_posture_summary: dict[str, Any]
    timeline: list[dict[str, Any]]
    evidence_map: list[dict[str, Any]]
    exhibit_index: list[dict[str, Any]]
    authority_matrix: list[dict[str, Any]]
    missing_record_checklist: list[str]
    missing_facts: list[dict[str, Any]]
    red_flags: list[str]
    warnings: list[str]
    review_required: bool = True
    export_status: str = "review_required"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MatterWorkProductBuilder:
    def build(
        self,
        report: IntakeReport,
        *,
        authorities: list[dict[str, Any]] | None = None,
    ) -> MatterWorkProduct:
        authority_rows = [self._authority_row(row) for row in authorities or []]
        unsupported = [item for item in report.evidence_map if item.get("support_status") != "supported"]
        missing_facts = [
            {
                "fact_id": item.get("fact_id"),
                "fact": item.get("fact"),
                "reason": "no_supporting_evidence_span_found",
            }
            for item in unsupported
        ]
        issue_tree = {
            "jurisdiction": report.matter.jurisdiction,
            "labels": report.issue_labels,
            "by_issue": {
                label: {
                    "facts": [
                        fact.text
                        for fact in self._all_report_facts(report.documents)
                        if label in fact.issue_labels
                    ],
                    "authority_count": sum(1 for row in authority_rows if label in row.get("issue_labels", [])),
                }
                for label in report.issue_labels
            },
        }
        posture_summary = {
            "procedural_posture": report.procedural_posture,
            "review_required": True,
            "known_limitations": [
                "procedural posture is deterministic/rule-based until attorney review",
                "matter documents are user-provided and not legal authority",
            ],
        }
        return MatterWorkProduct(
            matter_id=report.matter.matter_id,
            issue_tree=issue_tree,
            procedural_posture_summary=posture_summary,
            timeline=report.timeline,
            evidence_map=report.evidence_map,
            exhibit_index=self._build_exhibit_index(report.documents),
            authority_matrix=authority_rows,
            missing_record_checklist=report.missing_record_checklist,
            missing_facts=missing_facts,
            red_flags=report.red_flags,
            warnings=sorted(set(report.warnings)),
        )

    @staticmethod
    def _all_report_facts(documents: list[MatterDocument]):
        from legal.matter.document_ingestor import MatterDocumentIngestor

        ingestor = MatterDocumentIngestor()
        for document in documents:
            yield from ingestor.extract_facts(document)

    @staticmethod
    def _build_exhibit_index(documents: list[MatterDocument]) -> list[dict[str, Any]]:
        return [
            {
                "exhibit_id": f"exhibit_{index + 1:03d}",
                "document_id": document.document_id,
                "filename": document.filename,
                "document_type": document.classification.document_type,
                "sha256": document.sha256,
                "data_class": document.data_class,
                "retention_policy_id": document.retention_policy_id,
                "review_required": True,
            }
            for index, document in enumerate(documents)
        ]

    @staticmethod
    def _authority_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": row.get("source_id") or row.get("record_id"),
            "citation": row.get("citation"),
            "title": row.get("title"),
            "source_class": row.get("source_class"),
            "jurisdiction": row.get("jurisdiction", "maine"),
            "authority_status": row.get("authority_status", "stale_unknown"),
            "freshness_status": row.get("freshness_status", "unknown"),
            "issue_labels": row.get("issue_labels", []),
            "review_required": row.get("authority_status") not in {"verified_official_maine", "verified_maine_law_court"},
        }

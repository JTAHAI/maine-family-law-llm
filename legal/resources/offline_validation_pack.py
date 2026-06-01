from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


@dataclass(frozen=True)
class OfflineValidationPackReport:
    status: str
    data_root: str
    pack_root: str
    manifest_path: str
    parsed_store_root: str
    eval_store_root: str
    generated_at: str
    fixture_only: bool = True
    warnings: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "data_root": self.data_root,
            "pack_root": self.pack_root,
            "manifest_path": self.manifest_path,
            "parsed_store_root": self.parsed_store_root,
            "eval_store_root": self.eval_store_root,
            "generated_at": self.generated_at,
            "fixture_only": self.fixture_only,
            "warnings": list(self.warnings),
            "created_files": list(self.created_files),
        }


class OfflineValidationPackBuilder:
    """Create a tiny external fixture pack that proves local wiring without legal authority."""

    def __init__(self, data_root: str | Path) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.pack_root = self.data_root / "offline_validation_pack"
        self.official_root = self.data_root / "official_authority_store"
        self.parsed_root = self.data_root / "parsed_authority_store"
        self.eval_root = self.data_root / "eval_store"
        self.release_evidence_root = self.data_root / "release_evidence"

    def build(self) -> OfflineValidationPackReport:
        created: list[str] = []
        now = _utc_now()
        for root in [self.pack_root, self.official_root, self.parsed_root, self.eval_root, self.release_evidence_root]:
            root.mkdir(parents=True, exist_ok=True)

        snapshot_text = (
            "OFFLINE FIXTURE ONLY - NOT LEGAL AUTHORITY. "
            "Synthetic Maine family-law source used to test local wiring. "
            "Do not cite in legal work."
        )
        snapshot = self.pack_root / "fixture_official_source.html"
        snapshot.write_text(snapshot_text, encoding="utf-8")
        created.append(str(snapshot))
        digest = _sha256_bytes(snapshot.read_bytes())
        manifest = [
            {
                "source_id": "fixture-maine-family-law-source",
                "source_class": "offline_fixture",
                "jurisdiction": "maine",
                "source_url_or_path": "offline://fixture/maine-family-law-source",
                "snapshot_path": str(snapshot),
                "hash": digest,
                "retrieved_timestamp": now,
                "parser_status": "parsed_fixture_only",
                "freshness_status": "fixture_only_not_current_law",
                "fixture_only_not_legal_authority": True,
            }
        ]
        manifest_path = self.official_root / "source_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        created.append(str(manifest_path))

        base = {
            "source_id": "fixture-maine-family-law-source",
            "source_hash": digest,
            "jurisdiction": "maine",
            "freshness_status": "fixture_only_not_current_law",
            "parser_status": "parsed_fixture_only",
            "source_span": {"start_offset": 0, "end_offset": len(snapshot_text)},
            "source_url_or_path": "offline://fixture/maine-family-law-source",
            "fixture_only_not_legal_authority": True,
        }
        rows = {
            "statutes/offline_fixture_statutes.jsonl": [
                {
                    **base,
                    "record_id": "fixture-statute-19a-1653",
                    "source_class": "offline_fixture_statute",
                    "authority_kind": "fixture_statute_reference",
                    "title": "Fixture best-interest source",
                    "citation": "FIXTURE 19-A M.R.S. § 1653",
                    "text": "Fixture text about parental rights, contact, and best-interest factors.",
                    "issue_labels": ["parental_rights_responsibilities", "best_interest_factor_gap"],
                }
            ],
            "rules/offline_fixture_rules.jsonl": [
                {
                    **base,
                    "record_id": "fixture-rule-52",
                    "source_class": "offline_fixture_rule",
                    "authority_kind": "fixture_rule_reference",
                    "title": "Fixture findings rule",
                    "citation": "FIXTURE M.R. Civ. P. 52",
                    "text": "Fixture text about findings needed for review.",
                    "issue_labels": ["Rule_52_findings"],
                }
            ],
            "forms/offline_fixture_forms.jsonl": [
                {
                    **base,
                    "record_id": "fixture-form-fm-001",
                    "source_class": "offline_fixture_form",
                    "authority_kind": "fixture_form_reference",
                    "title": "Fixture Family Matter Form",
                    "citation": "FIXTURE FM-001",
                    "form_id": "FM-001-FIXTURE",
                    "version_date": "fixture",
                    "text": "Fixture form text for workflow tests only.",
                    "issue_labels": ["divorce"],
                }
            ],
            "opinions/offline_fixture_opinions.jsonl": [
                {
                    **base,
                    "record_id": "fixture-case-2026-me-1",
                    "source_class": "offline_fixture_opinion",
                    "authority_kind": "fixture_opinion_reference",
                    "title": "Fixture v. Fixture",
                    "citation": "FIXTURE 2026 ME 1",
                    "text": "Fixture Law Court text about remand and missing findings.",
                    "issue_labels": ["appeal_preservation", "Rule_52_findings"],
                }
            ],
        }
        for rel, rel_rows in rows.items():
            out = self.parsed_root / rel
            _write_jsonl(out, rel_rows)
            created.append(str(out))

        eval_row = {
            "query_id": "fixture-query-1",
            "query": "fixture parental rights findings",
            "expected_source_ids": ["fixture-maine-family-law-source"],
            "review_status": "fixture_only_not_attorney_reviewed",
            "private_data_allowed_for_training": False,
            "fixture_only_not_legal_authority": True,
            "created_at": now,
        }
        eval_path = self.eval_root / "offline_fixture_retrieval_gold.jsonl"
        _write_jsonl(eval_path, [eval_row])
        created.append(str(eval_path))

        evidence = {
            "status": "pass",
            "fixture_only": True,
            "generated_at": now,
            "warning": "Synthetic fixtures prove wiring only and must never satisfy production legal authority or attorney-reviewed eval gates.",
            "manifest_path": str(manifest_path),
        }
        evidence_path = self.release_evidence_root / "offline_validation_pack_evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        created.append(str(evidence_path))

        return OfflineValidationPackReport(
            status="pass",
            data_root=str(self.data_root),
            pack_root=str(self.pack_root),
            manifest_path=str(manifest_path),
            parsed_store_root=str(self.parsed_root),
            eval_store_root=str(self.eval_root),
            generated_at=now,
            fixture_only=True,
            warnings=["offline validation pack is synthetic and not legal authority"],
            created_files=created,
        )

    def write(self, output_path: str | Path) -> OfflineValidationPackReport:
        report = self.build()
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

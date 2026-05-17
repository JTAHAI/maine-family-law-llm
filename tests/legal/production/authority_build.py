from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from legal.data_boundaries import StoreName
from legal.data_boundaries.storage_layout import is_inside_project_repo


@dataclass(frozen=True)
class AuthorityManifestFinding:
    source_id: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class AuthoritySourceClassCoverage:
    source_class: str
    ingested: int
    minimum_required: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class AuthorityBuildReport:
    production_ready: bool
    status: str
    manifest_path: str | None
    data_root: str
    official_store: str
    total_records: int = 0
    parsed_records: int = 0
    snapshot_only_records: int = 0
    source_coverage: list[AuthoritySourceClassCoverage] = field(default_factory=list)
    findings: list[AuthorityManifestFinding] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    policy_version: str = "unknown"
    readiness: str = "authority_build_blocked_until_external_official_snapshots_are_ingested"

    def as_dict(self) -> dict[str, Any]:
        return {
            "production_ready": self.production_ready,
            "status": self.status,
            "readiness": self.readiness,
            "policy_version": self.policy_version,
            "data_root": self.data_root,
            "official_store": self.official_store,
            "manifest_path": self.manifest_path,
            "total_records": self.total_records,
            "parsed_records": self.parsed_records,
            "snapshot_only_records": self.snapshot_only_records,
            "source_coverage": [item.as_dict() for item in self.source_coverage],
            "findings": [item.as_dict() for item in self.findings],
            "blockers": sorted(set(self.blockers)),
        }


class AuthorityBuildAuditor:
    """Validate an external official-authority build.

    This audits the data product that lives outside the source ZIP. It checks that
    the source manifest is present, records have required metadata, official
    snapshots exist, hashes match snapshots, and required source classes are
    represented at production minimums.
    """

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.policy = policy or json.loads(
            (self.project_root / "configs" / "maine_authority_build_policy.json").read_text(
                encoding="utf-8"
            )
        )
        self.official_store = self.data_root / self.policy.get(
            "official_store_name", StoreName.OFFICIAL_AUTHORITY.value
        )
        self.manifest_path = self.official_store / self.policy.get(
            "manifest_filename", "source_manifest.json"
        )

    def run(self) -> AuthorityBuildReport:
        findings: list[AuthorityManifestFinding] = []
        blockers: list[str] = []

        if self.policy.get("external_data_root_required", True) and is_inside_project_repo(
            self.data_root, self.project_root
        ):
            blockers.append("external_data_root_inside_repo")
            findings.append(
                AuthorityManifestFinding(
                    source_id="__data_root__",
                    code="external_data_root_inside_repo",
                    message="Authority corpus data root must be outside the source repository.",
                )
            )

        records = self._load_manifest(findings, blockers)
        counts: dict[str, int] = {}
        parsed_records = 0
        snapshot_only_records = 0
        for record in records:
            source_id = str(record.get("source_id", "__missing_source_id__"))
            source_class = str(record.get("source_class", ""))
            if source_class:
                counts[source_class] = counts.get(source_class, 0) + 1
            parser_status = str(record.get("parser_status", ""))
            if parser_status == "parsed":
                parsed_records += 1
            if parser_status == "snapshot_only":
                snapshot_only_records += 1
            self._validate_record(record, findings, blockers)

        coverage = self._source_coverage(counts, blockers)
        minimum_ingested = int(self.policy.get("minimum_ingested_targets", 0))
        if len(records) < minimum_ingested:
            blockers.append("minimum_ingested_targets_not_met")
            findings.append(
                AuthorityManifestFinding(
                    source_id="__manifest__",
                    code="minimum_ingested_targets_not_met",
                    message=f"{len(records)} records found; {minimum_ingested} required.",
                )
            )

        production_ready = not blockers
        return AuthorityBuildReport(
            production_ready=production_ready,
            status="pass",
            manifest_path=str(self.manifest_path) if self.manifest_path.exists() else None,
            data_root=str(self.data_root),
            official_store=str(self.official_store),
            total_records=len(records),
            parsed_records=parsed_records,
            snapshot_only_records=snapshot_only_records,
            source_coverage=coverage,
            findings=findings,
            blockers=sorted(set(blockers)),
            policy_version=self.policy.get("version", "unknown"),
            readiness=(
                "authority_build_ready"
                if production_ready
                else "authority_build_blocked_until_external_official_snapshots_are_ingested"
            ),
        )

    def _load_manifest(
        self,
        findings: list[AuthorityManifestFinding],
        blockers: list[str],
    ) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            blockers.append("manifest_missing")
            findings.append(
                AuthorityManifestFinding(
                    source_id="__manifest__",
                    code="manifest_missing",
                    message=f"No source manifest found at {self.manifest_path}.",
                )
            )
            return []
        try:
            loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append("manifest_parse_error")
            findings.append(
                AuthorityManifestFinding(
                    source_id="__manifest__",
                    code="manifest_parse_error",
                    message=str(exc),
                )
            )
            return []
        if not isinstance(loaded, list):
            blockers.append("manifest_parse_error")
            findings.append(
                AuthorityManifestFinding(
                    source_id="__manifest__",
                    code="manifest_parse_error",
                    message="Manifest must be a JSON array of source records.",
                )
            )
            return []
        return [item for item in loaded if isinstance(item, dict)]

    def _validate_record(
        self,
        record: dict[str, Any],
        findings: list[AuthorityManifestFinding],
        blockers: list[str],
    ) -> None:
        source_id = str(record.get("source_id", "__missing_source_id__"))
        source_class = str(record.get("source_class", ""))
        required_fields = self.policy.get("required_manifest_fields", [])
        for field_name in required_fields:
            if field_name not in record or record.get(field_name) in (None, ""):
                blockers.append("missing_required_manifest_field")
                findings.append(
                    AuthorityManifestFinding(
                        source_id=source_id,
                        code="missing_required_manifest_field",
                        message=f"Missing required manifest field: {field_name}",
                    )
                )

        parser_status = str(record.get("parser_status", ""))
        acceptable = set(self.policy.get("acceptable_parser_statuses", []))
        if parser_status not in acceptable:
            blockers.append("parser_status_not_acceptable")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="parser_status_not_acceptable",
                    message=f"Parser status {parser_status!r} is not acceptable.",
                )
            )

        parsed_required = set(self.policy.get("parsed_status_required_for_classes", []))
        snapshot_classes = set(self.policy.get("snapshot_only_allowed_for_classes", []))
        if source_class in parsed_required and parser_status != "parsed":
            blockers.append("parsed_status_required")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="parsed_status_required",
                    message=f"{source_class} must be parsed, not {parser_status!r}.",
                )
            )
        if parser_status == "snapshot_only" and source_class not in snapshot_classes:
            blockers.append("parser_status_not_acceptable")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="snapshot_only_not_allowed_for_class",
                    message=f"snapshot_only is not allowed for {source_class}.",
                )
            )

        freshness = str(record.get("freshness_status", "")).lower()
        if not freshness or freshness in {"unknown", "stale_unknown", "retrieved_unparsed"}:
            blockers.append("freshness_unknown")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="freshness_unknown",
                    message=f"Freshness status must be known for production; got {freshness!r}.",
                )
            )

        if self.policy.get("require_snapshot_files_exist", True):
            self._validate_snapshot(record, findings, blockers)

    def _validate_snapshot(
        self,
        record: dict[str, Any],
        findings: list[AuthorityManifestFinding],
        blockers: list[str],
    ) -> None:
        source_id = str(record.get("source_id", "__missing_source_id__"))
        snapshot_value = record.get("snapshot_path")
        if not snapshot_value:
            blockers.append("snapshot_missing")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="snapshot_missing",
                    message="Manifest record does not include snapshot_path.",
                )
            )
            return

        snapshot_path = Path(str(snapshot_value)).expanduser()
        if not snapshot_path.is_absolute():
            snapshot_path = self.official_store / snapshot_path
        if not snapshot_path.exists():
            blockers.append("snapshot_missing")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="snapshot_missing",
                    message=f"Snapshot file not found: {snapshot_path}",
                )
            )
            return
        minimum_bytes = int(self.policy.get("minimum_snapshot_bytes", 1))
        if snapshot_path.stat().st_size < minimum_bytes:
            blockers.append("snapshot_missing")
            findings.append(
                AuthorityManifestFinding(
                    source_id=source_id,
                    code="snapshot_too_small",
                    message=f"Snapshot has fewer than {minimum_bytes} bytes.",
                )
            )
        if self.policy.get("require_manifest_hash_matches_snapshot", True):
            expected = str(record.get("hash", ""))
            actual = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            if expected and actual != expected:
                blockers.append("snapshot_hash_mismatch")
                findings.append(
                    AuthorityManifestFinding(
                        source_id=source_id,
                        code="snapshot_hash_mismatch",
                        message="Manifest hash does not match snapshot bytes.",
                    )
                )

    def _source_coverage(
        self,
        counts: dict[str, int],
        blockers: list[str],
    ) -> list[AuthoritySourceClassCoverage]:
        coverage: list[AuthoritySourceClassCoverage] = []
        for source_class, minimum in self.policy.get("required_source_class_minimums", {}).items():
            actual = counts.get(source_class, 0)
            status = "pass" if actual >= int(minimum) else "blocked_source_class_minimum"
            if status != "pass":
                blockers.append("source_class_minimum_not_met")
            coverage.append(
                AuthoritySourceClassCoverage(
                    source_class=source_class,
                    ingested=actual,
                    minimum_required=int(minimum),
                    status=status,
                )
            )
        return coverage

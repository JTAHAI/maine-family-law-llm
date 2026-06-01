from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.production.ga_pass_tracker import GAPassTracker


@dataclass(frozen=True)
class EvidenceArtifactRequirement:
    root: str
    glob: str
    status_values: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "EvidenceArtifactRequirement":
        return cls(
            root=str(row.get("root") or "data"),
            glob=str(row.get("glob") or ""),
            status_values=tuple(str(item) for item in row.get("status_values") or ()),
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"root": self.root, "glob": self.glob}
        if self.status_values:
            payload["status_values"] = list(self.status_values)
        return payload


@dataclass(frozen=True)
class GAPassEvidenceRequirement:
    pass_number: int
    required_artifacts: tuple[EvidenceArtifactRequirement, ...] = ()

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "GAPassEvidenceRequirement":
        return cls(
            pass_number=int(row["pass"]),
            required_artifacts=tuple(
                EvidenceArtifactRequirement.from_dict(item) for item in row.get("required_artifacts") or ()
            ),
        )


@dataclass
class EvidenceFinding:
    pass_number: int
    root: str
    glob: str
    status: str
    matches: list[str] = field(default_factory=list)
    blocker: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_number,
            "root": self.root,
            "glob": self.glob,
            "status": self.status,
            "matches": self.matches,
            "blocker": self.blocker,
        }


@dataclass
class GAPassEvidenceReport:
    status: str
    generated_at: str
    true_ga_completed_claimed: list[int]
    true_ga_remaining: int
    audited_completed_passes: list[int]
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    findings: list[EvidenceFinding] = field(default_factory=list)
    counting_rule: str = (
        "Completed true-GA pass rows must have required real evidence artifacts. "
        "Repo scaffolding, dry runs, fixtures, and docs/sample-evidence do not count."
    )

    @property
    def pass_evidence_valid(self) -> bool:
        return self.status == "pass"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "pass_evidence_valid": self.pass_evidence_valid,
            "true_ga_completed_claimed": self.true_ga_completed_claimed,
            "true_ga_remaining": self.true_ga_remaining,
            "audited_completed_passes": self.audited_completed_passes,
            "counting_rule": self.counting_rule,
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "findings": [item.as_dict() for item in self.findings],
        }


class GAPassEvidenceAuditor:
    """Audit evidence before allowing the true GA pass count to drop.

    The normal repo state has zero completed true-GA passes, so this audit passes with no
    external roots populated. If a pass is marked complete, the corresponding evidence
    requirements must exist in the declared external data/eval/security/pilot roots.
    """

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path | None = None,
        eval_root: str | Path | None = None,
        security_root: str | Path | None = None,
        pilot_root: str | Path | None = None,
        tracker_path: str | Path | None = None,
        requirements_path: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve() if data_root else None
        self.eval_root = Path(eval_root).expanduser().resolve() if eval_root else None
        self.security_root = Path(security_root).expanduser().resolve() if security_root else None
        self.pilot_root = Path(pilot_root).expanduser().resolve() if pilot_root else None
        self.tracker_path = Path(tracker_path).resolve() if tracker_path else None
        self.requirements_path = (
            Path(requirements_path).resolve()
            if requirements_path
            else self.project_root / "configs" / "maine_ga_pass_evidence_requirements.json"
        )

    def _root_path(self, alias: str) -> Path | None:
        alias = alias.lower().strip()
        if alias == "repo":
            return self.project_root
        if alias == "data":
            return self.data_root
        if alias == "eval":
            return self.eval_root
        if alias == "security":
            return self.security_root
        if alias == "pilot":
            return self.pilot_root
        return None

    def _load_requirements(self) -> dict[int, GAPassEvidenceRequirement]:
        raw = json.loads(self.requirements_path.read_text(encoding="utf-8"))
        return {
            int(item["pass"]): GAPassEvidenceRequirement.from_dict(item)
            for item in raw.get("passes", [])
        }

    def _load_tracker_report(self) -> dict[str, Any]:
        tracker = GAPassTracker(project_root=self.project_root)
        if self.tracker_path is not None:
            tracker.tracker_path = self.tracker_path
        return tracker.report().as_dict()

    def _load_json_payload(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def _json_status_ok(self, path: Path, allowed: tuple[str, ...]) -> bool:
        if not allowed:
            return True
        try:
            payload = self._load_json_payload(path)
        except Exception:
            return False
        if not isinstance(payload, dict):
            return False

        # Evidence reports often carry a human-readable top-level status plus
        # explicit gate fields.  Treat any explicit blocker or negative gate as
        # authoritative even when a legacy report still says ``status: pass``
        # for "the audit command ran successfully."  This prevents a blocked
        # authority build or release metric report from satisfying a true-GA
        # evidence requirement merely because the JSON was well-formed.
        blockers = payload.get("blockers")
        if isinstance(blockers, list) and blockers:
            return False
        if isinstance(blockers, dict) and blockers:
            return False
        for key in (
            "production_ready",
            "release_allowed",
            "safe_to_package",
            "safe_to_push",
            "signed",
            "pass_evidence_valid",
        ):
            value = payload.get(key)
            if value is False:
                return False

        terminal_negative_values = {
            "block",
            "blocked",
            "deny",
            "denied",
            "error",
            "fail",
            "failed",
            "failure",
            "incomplete",
            "no",
            "no_go",
            "no-go",
            "no_ship",
            "no-ship",
            "not_ready",
            "not-ready",
            "rejected",
        }
        candidates: list[str] = []
        for key in ("status", "readiness", "result"):
            value = payload.get(key)
            if isinstance(value, str):
                normalized = value.strip().lower()
                candidates.append(normalized)
                if normalized in terminal_negative_values:
                    return False
        for key in (
            "production_ready",
            "release_allowed",
            "safe_to_package",
            "safe_to_push",
            "signed",
            "pass_evidence_valid",
        ):
            value = payload.get(key)
            if isinstance(value, bool):
                candidates.append("pass" if value else "blocked")
        allowed_lower = {item.lower() for item in allowed}
        return any(item in allowed_lower for item in candidates)

    def _artifact_integrity_blocker(self, path: Path, *, root_path: Path | None = None) -> str | None:
        """Return a blocker code when a matched evidence artifact is only a shell.

        The pass evidence gate is intentionally stricter than a plain glob check.
        A completed true-GA pass must point at real machine-readable evidence, not
        an empty file, an empty directory, malformed JSON/JSONL placeholder, or
        a source manifest that only imitates production evidence.
        """
        if path.is_dir():
            has_child = any(child.exists() for child in path.iterdir())
            return None if has_child else "empty_artifact_directory"
        if not path.is_file():
            return "artifact_not_file_or_directory"
        if path.stat().st_size <= 0:
            return "empty_artifact_file"
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                payload = self._load_json_payload(path)
            except Exception:
                return "invalid_json_artifact"
            if path.name == "source_manifest.json":
                return self._source_manifest_integrity_blocker(payload, root_path=root_path)
            report_blocker = self._json_report_integrity_blocker(path, payload, root_path=root_path)
            if report_blocker:
                return report_blocker
        if suffix == ".jsonl":
            try:
                lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except Exception:
                return "invalid_jsonl_artifact"
            if not lines:
                return "empty_jsonl_artifact"
            try:
                for line in lines[:25]:
                    json.loads(line)
            except Exception:
                return "invalid_jsonl_artifact"
        return None


    def _json_report_integrity_blocker(
        self, path: Path, payload: Any, *, root_path: Path | None = None
    ) -> str | None:
        """Fail closed on skeletal JSON reports used as true-GA evidence.

        Status-only JSON such as ``{"status": "pass"}`` is useful for quick
        smoke tests but is not enough to close a true GA pass.  These named
        evidence reports must include the same readiness fields emitted by their
        corresponding audit builders, so a placeholder file cannot satisfy the
        formal pass evidence gate.
        """
        if not isinstance(payload, dict):
            return "json_report_not_object"
        blockers = payload.get("blockers")
        if isinstance(blockers, list) and blockers:
            return "json_report_has_blockers"
        if isinstance(blockers, dict) and blockers:
            return "json_report_has_blockers"

        name = path.name
        if name == "authority_build_audit.json":
            if payload.get("production_ready") is not True:
                return "authority_build_audit_not_production_ready"
            if str(payload.get("readiness") or "") != "authority_build_ready":
                return "authority_build_audit_readiness_not_ready"
            if int(payload.get("total_records") or 0) <= 0:
                return "authority_build_audit_missing_record_count"
            manifest_path = payload.get("manifest_path")
            if not manifest_path:
                return "authority_build_audit_missing_manifest_path"
            manifest = Path(str(manifest_path)).expanduser()
            if not manifest.is_absolute() and root_path is not None:
                manifest = root_path / manifest
            manifest = manifest.resolve()
            if self.project_root in (manifest, *manifest.parents):
                return "authority_build_audit_manifest_inside_repo"
            if root_path is not None and root_path.exists():
                try:
                    manifest.relative_to(root_path.resolve())
                except ValueError:
                    return "authority_build_audit_manifest_outside_evidence_root"
            if not manifest.exists():
                return "authority_build_audit_manifest_missing"

        if name == "gold_annotation_queue_audit.json":
            if str(payload.get("status") or "").lower() != "pass":
                return "gold_annotation_queue_audit_not_pass"
            rows = int(payload.get("rows") or 0)
            if rows <= 0:
                return "gold_annotation_queue_audit_empty"
            if int(payload.get("needs_attorney_review_rows") or -1) != rows:
                return "gold_annotation_queue_audit_not_all_attorney_review"
            if int(payload.get("private_training_rows") or 0) != 0:
                return "gold_annotation_queue_audit_private_training_rows"

        if name == "gold_eval_pack_audit.json":
            if payload.get("production_ready") is not True:
                return "gold_eval_pack_audit_not_production_ready"
            datasets = payload.get("datasets")
            if not isinstance(datasets, list) or not datasets:
                return "gold_eval_pack_audit_missing_datasets"

        if name == "release_metrics.json":
            if str(payload.get("readiness") or "") != "release_metrics_ready":
                return "release_metrics_not_release_ready"
            gate_report = payload.get("release_gate_report")
            if not isinstance(gate_report, dict) or gate_report.get("release_allowed") is not True:
                return "release_metrics_gate_not_allowed"
            metrics = payload.get("metrics")
            if not isinstance(metrics, list) or not metrics:
                return "release_metrics_missing_metrics"

        return None

    def _source_manifest_integrity_blocker(self, payload: Any, *, root_path: Path | None = None) -> str | None:
        if not isinstance(payload, list):
            return "source_manifest_not_array"
        if not payload:
            return "source_manifest_empty"
        seen_source_ids: set[str] = set()
        required_fields = {
            "source_id",
            "source_class",
            "jurisdiction",
            "retrieved_at",
            "hash",
            "parser_status",
            "freshness_status",
            "data_class",
            "source_url_or_path",
            "snapshot_path",
            "parser_audit",
        }
        for index, record in enumerate(payload[:250]):
            if not isinstance(record, dict):
                return "source_manifest_record_not_object"
            missing = [field for field in sorted(required_fields) if record.get(field) in (None, "")]
            if missing:
                return f"source_manifest_record_missing_{missing[0]}"
            source_id = str(record.get("source_id"))
            if source_id in seen_source_ids:
                return "source_manifest_duplicate_source_id"
            seen_source_ids.add(source_id)
            parser_audit = record.get("parser_audit")
            if not isinstance(parser_audit, dict):
                return "source_manifest_parser_audit_not_object"
            if parser_audit.get("status") and str(parser_audit.get("status")) != str(record.get("parser_status")):
                return "source_manifest_parser_audit_status_mismatch"
            if str(record.get("freshness_status", "")).lower() in {"", "unknown", "stale_unknown", "retrieved_unparsed"}:
                return "source_manifest_freshness_unknown"
            snapshot_value = Path(str(record.get("snapshot_path"))).expanduser()
            if not snapshot_value.is_absolute() and root_path is not None:
                snapshot_value = root_path / snapshot_value
            snapshot_path = snapshot_value.resolve()
            if self.project_root in (snapshot_path, *snapshot_path.parents):
                return "source_manifest_snapshot_inside_repo"
            if root_path is not None and root_path.exists():
                try:
                    snapshot_path.relative_to(root_path.resolve())
                except ValueError:
                    return "source_manifest_snapshot_outside_evidence_root"
            if not snapshot_path.exists():
                return "source_manifest_snapshot_missing"
            expected_hash = str(record.get("hash") or "")
            if expected_hash and len(expected_hash) >= 32:
                import hashlib

                actual_hash = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    return "source_manifest_snapshot_hash_mismatch"
        return None

    def _check_artifact(
        self,
        *,
        pass_number: int,
        requirement: EvidenceArtifactRequirement,
    ) -> EvidenceFinding:
        root_path = self._root_path(requirement.root)
        if root_path is None:
            return EvidenceFinding(
                pass_number=pass_number,
                root=requirement.root,
                glob=requirement.glob,
                status="blocked",
                blocker=f"missing_root:{requirement.root}",
            )
        matches = sorted(path for path in root_path.glob(requirement.glob) if path.exists())
        visible = [str(path.relative_to(root_path)) for path in matches[:25]]
        if not matches:
            return EvidenceFinding(
                pass_number=pass_number,
                root=requirement.root,
                glob=requirement.glob,
                status="blocked",
                blocker=f"missing_artifact:{requirement.root}:{requirement.glob}",
            )
        integrity_blockers = [self._artifact_integrity_blocker(path, root_path=root_path) for path in matches]
        integrity_blockers = [blocker for blocker in integrity_blockers if blocker]
        if integrity_blockers:
            return EvidenceFinding(
                pass_number=pass_number,
                root=requirement.root,
                glob=requirement.glob,
                status="blocked",
                matches=visible,
                blocker=f"artifact_integrity_failed:{requirement.root}:{requirement.glob}:{integrity_blockers[0]}",
            )
        if requirement.status_values:
            accepted = [path for path in matches if path.is_file() and self._json_status_ok(path, requirement.status_values)]
            if not accepted:
                return EvidenceFinding(
                    pass_number=pass_number,
                    root=requirement.root,
                    glob=requirement.glob,
                    status="blocked",
                    matches=visible,
                    blocker=f"artifact_status_not_accepted:{requirement.root}:{requirement.glob}",
                )
        return EvidenceFinding(
            pass_number=pass_number,
            root=requirement.root,
            glob=requirement.glob,
            status="pass",
            matches=visible,
        )

    def run(self) -> GAPassEvidenceReport:
        tracker_report = self._load_tracker_report()
        requirements = self._load_requirements()
        completed = [int(item) for item in tracker_report.get("completed_passes") or []]
        blockers: list[str] = []
        warnings: list[str] = []
        tracker_warnings = [str(item) for item in tracker_report.get("warnings") or []]
        if str(tracker_report.get("status") or "").lower() != "pass":
            blockers.append("tracker_report_not_pass")
        blockers.extend(f"tracker_warning:{warning}" for warning in tracker_warnings)
        findings: list[EvidenceFinding] = []
        for pass_number in completed:
            requirement = requirements.get(pass_number)
            if requirement is None:
                blocker = f"missing_evidence_requirements_for_completed_pass:{pass_number}"
                blockers.append(blocker)
                findings.append(
                    EvidenceFinding(
                        pass_number=pass_number,
                        root="config",
                        glob="",
                        status="blocked",
                        blocker=blocker,
                    )
                )
                continue
            if not requirement.required_artifacts:
                blocker = f"empty_evidence_requirements_for_completed_pass:{pass_number}"
                blockers.append(blocker)
                continue
            for artifact in requirement.required_artifacts:
                finding = self._check_artifact(pass_number=pass_number, requirement=artifact)
                findings.append(finding)
                if finding.blocker:
                    blockers.append(f"pass_{pass_number}:{finding.blocker}")
        for root_name, root_path in (
            ("data", self.data_root),
            ("eval", self.eval_root),
            ("security", self.security_root),
            ("pilot", self.pilot_root),
        ):
            if root_path and self.project_root in (root_path, *root_path.parents):
                blockers.append(f"{root_name}_root_inside_repo:{root_path}")
            elif root_path and root_path in self.project_root.parents:
                warnings.append(f"project_root_inside_{root_name}_root:{root_path}")
        status = "pass" if not blockers else "blocked"
        return GAPassEvidenceReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            true_ga_completed_claimed=completed,
            true_ga_remaining=int(tracker_report.get("true_ga_remaining") or 0),
            audited_completed_passes=completed if not blockers else [],
            blockers=blockers,
            warnings=warnings,
            findings=findings,
        )

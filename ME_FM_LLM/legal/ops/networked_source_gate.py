from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries.storage_layout import is_inside_project_repo


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_load_json(path: Path) -> Any:
    try:
        return _load_json(path)
    except Exception:
        return None


@dataclass(frozen=True)
class NetworkedSourceGateFinding:
    check: str
    status: str
    message: str
    path: str | None = None
    severity: str = "blocker"

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class NetworkedSourceGateReport:
    status: str
    networked_source_ready: bool
    production_legal_ready: bool
    repo_root: str
    data_root: str
    generated_at: str
    required_external_files_present: bool
    total_sources: int
    source_class_counts: dict[str, int] = field(default_factory=dict)
    parsed_record_counts: dict[str, int] = field(default_factory=dict)
    retrieval_indexes_present: list[str] = field(default_factory=list)
    gold_eval_rows_total: int = 0
    release_metric_names_present: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    findings: list[NetworkedSourceGateFinding] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)
    interpretation: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "networked_source_ready": self.networked_source_ready,
            "production_legal_ready": self.production_legal_ready,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "generated_at": self.generated_at,
            "required_external_files_present": self.required_external_files_present,
            "total_sources": self.total_sources,
            "source_class_counts": dict(self.source_class_counts),
            "parsed_record_counts": dict(self.parsed_record_counts),
            "retrieval_indexes_present": list(self.retrieval_indexes_present),
            "gold_eval_rows_total": self.gold_eval_rows_total,
            "release_metric_names_present": list(self.release_metric_names_present),
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
            "next_commands": list(self.next_commands),
            "interpretation": self.interpretation,
        }


class NetworkedSourceGateAuditor:
    """Audit external networked authority evidence after collection/ingestion.

    This gate is intentionally stricter than local fixture/source tests. It should fail until
    C:\\dev\\ME_FM_LLM_data contains real official-source manifests, parsed stores, retrieval
    indexes, attorney-reviewed eval evidence, and measured release metrics.
    """

    def __init__(self, repo_root: str | Path = ".", data_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.policy_path = self.repo_root / "configs" / "maine_networked_source_gate_policy.json"
        self.policy = _load_json(self.policy_path)
        self.data_root = Path(data_root or self.policy["default_windows_data_root"]).expanduser().resolve()

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.data_root).as_posix()
        except ValueError:
            return str(path)

    def _contains_fixture_marker(self, obj: Any) -> bool:
        markers = [str(item).lower() for item in self.policy.get("fixture_markers", [])]
        text = json.dumps(obj, sort_keys=True, default=str).lower()
        return any(marker in text for marker in markers)

    def _candidate_external_files(self, rel: str) -> list[str]:
        alternates = self.policy.get("required_external_file_alternates", {})
        candidates = [rel]
        for alternate in alternates.get(rel, []):
            if alternate not in candidates:
                candidates.append(str(alternate))
        return candidates

    def _required_file_exists(self, rel: str) -> bool:
        return any((self.data_root / candidate).is_file() for candidate in self._candidate_external_files(rel))

    def _read_required_file(self, rel: str, findings: list[NetworkedSourceGateFinding], blockers: list[str]) -> Any:
        selected_rel: str | None = None
        for candidate in self._candidate_external_files(rel):
            if (self.data_root / candidate).is_file():
                selected_rel = candidate
                break
        if selected_rel is None:
            blockers.append("missing_required_external_file")
            findings.append(
                NetworkedSourceGateFinding(
                    check="required_external_file",
                    status="fail",
                    path=rel,
                    message="Required external evidence file is missing, and no configured alternate was found.",
                )
            )
            return None
        if selected_rel != rel:
            findings.append(
                NetworkedSourceGateFinding(
                    check="required_external_file_alternate",
                    status="pass",
                    path=selected_rel,
                    message=f"Accepted alternate evidence file for {rel}.",
                    severity="info",
                )
            )
        path = self.data_root / selected_rel
        loaded = _safe_load_json(path)
        if loaded is None:
            blockers.append("required_external_file_not_json")
            findings.append(
                NetworkedSourceGateFinding(
                    check="required_external_file_json",
                    status="fail",
                    path=selected_rel,
                    message="Required external evidence file is not valid JSON.",
                )
            )
        return loaded

    def _source_class_count(self, source_counts: dict[str, int], required_class: str) -> int:
        aliases = self.policy.get("source_class_aliases", {})
        candidate_classes = {required_class, *[str(item) for item in aliases.get(required_class, [])]}
        return sum(source_counts.get(candidate, 0) for candidate in candidate_classes)

    @staticmethod
    def _parsed_counts_from_manifest(parsed_manifest: dict[str, Any]) -> dict[str, int]:
        raw_counts = (
            parsed_manifest.get("record_counts")
            or parsed_manifest.get("parsed_record_counts")
            or parsed_manifest.get("counts_by_collection")
            or {}
        )
        parsed_counts: dict[str, int] = {}
        if not isinstance(raw_counts, dict):
            return parsed_counts
        for key, value in raw_counts.items():
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            normalized_key = str(key).lower()
            if normalized_key.startswith("statutes/") or normalized_key == "statutes":
                category = "statutes"
            elif normalized_key.startswith("rules/") or normalized_key == "rules":
                category = "rules"
            elif normalized_key.startswith("forms/") or normalized_key == "forms":
                category = "forms"
            elif normalized_key.startswith("opinions/") or normalized_key == "opinions":
                category = "opinions"
            else:
                category = str(key)
            parsed_counts[category] = parsed_counts.get(category, 0) + count
        return parsed_counts

    @staticmethod
    def _indexes_from_manifest(retrieval_manifest: dict[str, Any]) -> list[str]:
        indexes_present: set[str] = set()
        raw_indexes = retrieval_manifest.get("indexes") or retrieval_manifest.get("index_types") or []
        if isinstance(raw_indexes, dict):
            indexes_present.update(str(k) for k, v in raw_indexes.items() if v)
        elif isinstance(raw_indexes, list):
            indexes_present.update(str(item.get("name") if isinstance(item, dict) else item) for item in raw_indexes)
        outputs = retrieval_manifest.get("outputs", {})
        if isinstance(outputs, dict):
            if outputs.get("bm25_documents"):
                indexes_present.add("bm25")
            if outputs.get("vector_embeddings"):
                indexes_present.add("vector")
            if outputs.get("hybrid_documents"):
                indexes_present.add("hybrid")
        return sorted(indexes_present)

    def audit(self) -> NetworkedSourceGateReport:
        findings: list[NetworkedSourceGateFinding] = []
        blockers: list[str] = []

        if is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("data_root_inside_source_repo")
            findings.append(
                NetworkedSourceGateFinding(
                    check="data_boundary",
                    status="fail",
                    path=str(self.data_root),
                    message="External data root must not be inside the source repository.",
                )
            )

        loaded_files: dict[str, Any] = {}
        for rel in self.policy.get("required_external_files", []):
            loaded_files[rel] = self._read_required_file(rel, findings, blockers)

        manifest = loaded_files.get("official_authority_store/source_manifest.json")
        sources = manifest if isinstance(manifest, list) else manifest.get("sources", []) if isinstance(manifest, dict) else []
        source_counts: dict[str, int] = {}
        for row in sources:
            if not isinstance(row, dict):
                continue
            source_class = str(row.get("source_class") or row.get("class") or "unknown")
            source_counts[source_class] = source_counts.get(source_class, 0) + 1

        minimum_total = int(self.policy.get("minimum_total_sources", 0))
        if len(sources) < minimum_total:
            blockers.append("minimum_total_sources_not_met")
            findings.append(
                NetworkedSourceGateFinding(
                    check="minimum_total_sources",
                    status="fail",
                    message=f"Found {len(sources)} sources; expected at least {minimum_total}.",
                    path="official_authority_store/source_manifest.json",
                )
            )
        for source_class, minimum in self.policy.get("required_source_classes", {}).items():
            actual = self._source_class_count(source_counts, source_class)
            if actual < int(minimum):
                blockers.append("source_class_minimum_not_met")
                findings.append(
                    NetworkedSourceGateFinding(
                        check="source_class_minimum",
                        status="fail",
                        path="official_authority_store/source_manifest.json",
                        message=f"{source_class} count {actual}; expected at least {minimum}.",
                    )
                )

        parsed_manifest = loaded_files.get("parsed_authority_store/parsed_authority_manifest.json")
        parsed_counts: dict[str, int] = {}
        if isinstance(parsed_manifest, dict):
            parsed_counts = self._parsed_counts_from_manifest(parsed_manifest)
        for category, minimum in self.policy.get("minimum_parsed_record_counts", {}).items():
            actual = int(parsed_counts.get(category, 0))
            if actual < int(minimum):
                blockers.append("parsed_authority_minimum_not_met")
                findings.append(
                    NetworkedSourceGateFinding(
                        check="parsed_authority_minimum",
                        status="fail",
                        path="parsed_authority_store/parsed_authority_manifest.json",
                        message=f"{category} parsed records {actual}; expected at least {minimum}.",
                    )
                )

        retrieval_manifest = loaded_files.get("embedding_store/retrieval_index_manifest.json")
        indexes_present: list[str] = []
        if isinstance(retrieval_manifest, dict):
            indexes_present = self._indexes_from_manifest(retrieval_manifest)
        for required_index in self.policy.get("minimum_retrieval_indexes", []):
            if required_index not in indexes_present:
                blockers.append("retrieval_index_manifest_missing_required_index")
                findings.append(
                    NetworkedSourceGateFinding(
                        check="retrieval_index_present",
                        status="fail",
                        path="embedding_store/retrieval_index_manifest.json",
                        message=f"Missing retrieval index: {required_index}.",
                    )
                )

        gold_manifest = loaded_files.get("eval_store/gold_eval_pack_manifest.json")
        gold_rows_total = 0
        if isinstance(gold_manifest, dict):
            datasets = gold_manifest.get("datasets", [])
            if isinstance(datasets, list):
                for dataset in datasets:
                    if isinstance(dataset, dict):
                        if dataset.get("review_status") in {"attorney_reviewed", "final", "approved"} or dataset.get("attorney_reviewed") is True:
                            gold_rows_total += int(dataset.get("rows", dataset.get("row_count", 0)) or 0)
            gold_rows_total = int(gold_manifest.get("attorney_reviewed_rows_total", gold_rows_total) or 0)
        if gold_rows_total < int(self.policy.get("minimum_gold_eval_rows_total", 0)):
            blockers.append("gold_eval_pack_missing_attorney_reviewed_rows")
            findings.append(
                NetworkedSourceGateFinding(
                    check="gold_eval_attorney_reviewed_rows",
                    status="fail",
                    path="eval_store/gold_eval_pack_manifest.json",
                    message="Gold eval pack has no attorney-reviewed rows recorded.",
                )
            )

        metrics_manifest = loaded_files.get("eval_store/release_metrics_evidence.json")
        metric_names: list[str] = []
        if isinstance(metrics_manifest, dict):
            metrics = metrics_manifest.get("metrics", [])
            if isinstance(metrics, list):
                metric_names = sorted(str(item.get("name")) for item in metrics if isinstance(item, dict) and item.get("name"))
            elif isinstance(metrics, dict):
                metric_names = sorted(str(k) for k in metrics)
        for name in self.policy.get("required_release_metric_names", []):
            if name not in metric_names:
                blockers.append("release_metrics_missing_required_metric")
                findings.append(
                    NetworkedSourceGateFinding(
                        check="release_metric_present",
                        status="fail",
                        path="eval_store/release_metrics_evidence.json",
                        message=f"Missing release metric: {name}.",
                    )
                )

        for rel, obj in loaded_files.items():
            if obj is not None and self._contains_fixture_marker(obj):
                blockers.append("fixture_marker_detected")
                findings.append(
                    NetworkedSourceGateFinding(
                        check="fixture_marker_absent",
                        status="fail",
                        path=rel,
                        message="Fixture/offline/synthetic marker detected in external evidence file.",
                    )
                )

        required_present = all(self._required_file_exists(rel) for rel in self.policy.get("required_external_files", []))
        ready = not blockers
        return NetworkedSourceGateReport(
            status="pass" if ready else "fail",
            networked_source_ready=ready,
            production_legal_ready=ready,
            repo_root=str(self.repo_root),
            data_root=str(self.data_root),
            generated_at=_utc_now(),
            required_external_files_present=required_present,
            total_sources=len(sources),
            source_class_counts=source_counts,
            parsed_record_counts=parsed_counts,
            retrieval_indexes_present=indexes_present,
            gold_eval_rows_total=gold_rows_total,
            release_metric_names_present=metric_names,
            blockers=blockers,
            findings=findings,
            next_commands=[
                "python scripts\\collect-enterprise-resources.py --project-root C:\\dev\\ME_FM_LLM --data-root C:\\dev\\ME_FM_LLM_data",
                "python scripts\\ingest-maine-authority.py --data-root C:\\dev\\ME_FM_LLM_data",
                "python scripts\\build-parsed-authority-store.py --data-root C:\\dev\\ME_FM_LLM_data",
                "python scripts\\build-authority-layer.py --data-root C:\\dev\\ME_FM_LLM_data",
                "python scripts\\build-retrieval-indexes.py --data-root C:\\dev\\ME_FM_LLM_data",
                "python scripts\\run-networked-source-gate.py --data-root C:\\dev\\ME_FM_LLM_data",
            ],
            interpretation=(
                "Pass means the external data root has enough non-fixture official-source evidence to start real legal validation. "
                "Fail is expected before networked collection, attorney review, and real metrics are completed."
            ),
        )

    def write(self, output_path: str | Path) -> NetworkedSourceGateReport:
        report = self.audit()
        path = Path(output_path)
        if not path.is_absolute():
            path = self.repo_root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report


def run_networked_source_gate(
    project_root: str | Path = ".",
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    return NetworkedSourceGateAuditor(project_root, data_root).audit().as_dict()

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.data_boundaries import StoreName

UNKNOWN_FRESHNESS = {"", "unknown", "stale_unknown", "retrieved_unparsed", "unknown_until_version_extracted"}


@dataclass(frozen=True)
class SourceFreshnessFinding:
    source_id: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class SourceUpdateReport:
    status: str
    data_root: str
    current_manifest_path: str
    previous_manifest_path: str | None = None
    total_sources: int = 0
    freshness_counts: dict[str, int] = field(default_factory=dict)
    changed_since_last_build: dict[str, list[str]] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    findings: list[SourceFreshnessFinding] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "current_manifest_path": self.current_manifest_path,
            "previous_manifest_path": self.previous_manifest_path,
            "total_sources": self.total_sources,
            "freshness_counts": self.freshness_counts,
            "changed_since_last_build": self.changed_since_last_build,
            "blockers": sorted(set(self.blockers)),
            "findings": [finding.as_dict() for finding in self.findings],
        }


class SourceUpdateEngine:
    """Classify source freshness and produce release diff evidence."""

    def __init__(
        self,
        *,
        data_root: str | Path,
        previous_manifest: str | Path | None = None,
        max_age_days: int = 120,
    ) -> None:
        self.data_root = Path(data_root).resolve()
        self.current_manifest = self.data_root / StoreName.OFFICIAL_AUTHORITY.value / "source_manifest.json"
        self.previous_manifest = Path(previous_manifest).resolve() if previous_manifest else None
        self.max_age_days = max_age_days

    def run(self, *, write_report: bool = True) -> SourceUpdateReport:
        findings: list[SourceFreshnessFinding] = []
        blockers: list[str] = []
        current = self._load_manifest(self.current_manifest, findings, blockers, required=True)
        previous = self._load_manifest(self.previous_manifest, findings, blockers, required=False) if self.previous_manifest else []
        freshness_counts = {"fresh": 0, "stale": 0, "unknown": 0, "superseded": 0}
        for record in current:
            status = self._classify_freshness(record, findings, blockers)
            freshness_counts[status] = freshness_counts.get(status, 0) + 1
        changes = self._diff(previous, current)
        for source_id in changes.get("removed", []):
            freshness_counts["superseded"] = freshness_counts.get("superseded", 0) + 1
            findings.append(
                SourceFreshnessFinding(source_id, "source_removed_or_superseded", "Source existed in previous manifest but not current manifest.")
            )
        status = "pass" if not blockers else "blocked"
        report = SourceUpdateReport(
            status=status,
            data_root=str(self.data_root),
            current_manifest_path=str(self.current_manifest),
            previous_manifest_path=str(self.previous_manifest) if self.previous_manifest else None,
            total_sources=len(current),
            freshness_counts=freshness_counts,
            changed_since_last_build=changes,
            blockers=blockers,
            findings=findings,
        )
        if write_report:
            path = self.data_root / "source_update_report.json"
            path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _load_manifest(
        self,
        path: Path | None,
        findings: list[SourceFreshnessFinding],
        blockers: list[str],
        *,
        required: bool,
    ) -> list[dict[str, Any]]:
        if path is None or not path.exists():
            if required:
                blockers.append("source_manifest_missing")
                findings.append(SourceFreshnessFinding("__manifest__", "source_manifest_missing", f"Manifest not found: {path}"))
            return []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append("source_manifest_parse_error")
            findings.append(SourceFreshnessFinding("__manifest__", "source_manifest_parse_error", str(exc)))
            return []
        if not isinstance(loaded, list):
            blockers.append("source_manifest_parse_error")
            findings.append(SourceFreshnessFinding("__manifest__", "source_manifest_parse_error", "Manifest must be a JSON array."))
            return []
        return [item for item in loaded if isinstance(item, dict)]

    def _classify_freshness(
        self,
        record: dict[str, Any],
        findings: list[SourceFreshnessFinding],
        blockers: list[str],
    ) -> str:
        source_id = str(record.get("source_id") or "__missing_source_id__")
        freshness = str(record.get("freshness_status") or "").lower()
        if freshness in UNKNOWN_FRESHNESS:
            blockers.append("freshness_unknown_blocks_current_law_claims")
            findings.append(SourceFreshnessFinding(source_id, "freshness_unknown", f"Freshness status is {freshness!r}."))
            return "unknown"
        retrieved_at = str(record.get("retrieved_at") or "")
        try:
            parsed = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            blockers.append("retrieved_at_invalid")
            findings.append(SourceFreshnessFinding(source_id, "retrieved_at_invalid", f"Invalid retrieved_at: {retrieved_at!r}."))
            return "unknown"
        age_days = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days
        if age_days > self.max_age_days:
            blockers.append("source_stale_blocks_current_law_claims")
            findings.append(SourceFreshnessFinding(source_id, "source_stale", f"Source snapshot is {age_days} days old; max age is {self.max_age_days}."))
            return "stale"
        return "fresh"

    def _diff(self, previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, list[str]]:
        prev_by_id = {str(item.get("source_id")): item for item in previous if item.get("source_id")}
        cur_by_id = {str(item.get("source_id")): item for item in current if item.get("source_id")}
        added = sorted(set(cur_by_id) - set(prev_by_id))
        removed = sorted(set(prev_by_id) - set(cur_by_id))
        hash_changed = sorted(
            source_id
            for source_id in set(prev_by_id) & set(cur_by_id)
            if str(prev_by_id[source_id].get("hash")) != str(cur_by_id[source_id].get("hash"))
        )
        unchanged = sorted(
            source_id
            for source_id in set(prev_by_id) & set(cur_by_id)
            if str(prev_by_id[source_id].get("hash")) == str(cur_by_id[source_id].get("hash"))
        )
        return {
            "added": added,
            "removed": removed,
            "hash_changed": hash_changed,
            "unchanged": unchanged,
        }

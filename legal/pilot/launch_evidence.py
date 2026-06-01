from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LaunchEvidenceArtifact:
    pass_number: int
    name: str
    path: str
    required_statuses: tuple[str, ...]
    present: bool
    status_value: str = ""
    sha256: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_number,
            "name": self.name,
            "path": self.path,
            "required_statuses": list(self.required_statuses),
            "present": self.present,
            "status_value": self.status_value,
            "sha256": self.sha256,
            "payload_keys": sorted(self.payload.keys()),
        }


@dataclass(frozen=True)
class LaunchEvidenceReport:
    status: str
    readiness: str
    generated_at: str
    artifacts: list[LaunchEvidenceArtifact]
    blockers: list[str] = field(default_factory=list)
    closed_passes: list[int] = field(default_factory=list)
    open_passes: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "closed_passes": list(self.closed_passes),
            "open_passes": list(self.open_passes),
            "artifacts": [artifact.as_dict() for artifact in self.artifacts],
            "blockers": sorted(set(self.blockers)),
        }


class LaunchEvidenceGate:
    """Fail-closed external evidence gate for Passes 48-51.

    This gate deliberately does not create pilot, signoff, or GA-shipment evidence.
    It only verifies externally supplied reports/signoffs and reports exactly what
    is still missing. That keeps repo plumbing complete without fabricating pilot,
    attorney, legal, product, security, or ops signoff.
    """

    REQUIRED_ARTIFACTS = (
        (48, "attorney_sandbox_pilot_report", "attorney_sandbox_pilot_report.json", ("pass",)),
        (49, "limited_real_matter_pilot_report", "limited_real_matter_pilot_report.json", ("pass",)),
        (50, "ga_release_candidate_signoff", "ga_release_candidate_signoff.json", ("pass", "signed")),
        (51, "ga_shipment_signoff", "ga_shipment_signoff.json", ("pass", "signed")),
    )

    def audit(self, *, pilot_root: str | Path, release_root: str | Path | None = None) -> LaunchEvidenceReport:
        pilot_root = Path(pilot_root)
        release_root = Path(release_root) if release_root is not None else pilot_root
        artifacts: list[LaunchEvidenceArtifact] = []
        blockers: list[str] = []
        closed: list[int] = []
        open_passes: list[int] = []

        for pass_number, name, filename, statuses in self.REQUIRED_ARTIFACTS:
            root = pilot_root if pass_number in {48, 49} else release_root
            path = root / filename
            artifact, artifact_blockers = self._load_artifact(
                pass_number=pass_number,
                name=name,
                path=path,
                required_statuses=statuses,
            )
            artifacts.append(artifact)
            if artifact_blockers:
                blockers.extend(artifact_blockers)
                open_passes.append(pass_number)
            else:
                closed.append(pass_number)

        status = "pass" if not blockers else "blocked"
        return LaunchEvidenceReport(
            status=status,
            readiness="pass48_51_launch_evidence_ready" if status == "pass" else "pass48_51_launch_evidence_blocked",
            generated_at=datetime.now(timezone.utc).isoformat(),
            artifacts=artifacts,
            blockers=blockers,
            closed_passes=closed,
            open_passes=open_passes,
        )

    def _load_artifact(
        self,
        *,
        pass_number: int,
        name: str,
        path: Path,
        required_statuses: tuple[str, ...],
    ) -> tuple[LaunchEvidenceArtifact, list[str]]:
        if not path.exists() or not path.is_file() or path.stat().st_size == 0:
            return (
                LaunchEvidenceArtifact(
                    pass_number=pass_number,
                    name=name,
                    path=str(path),
                    required_statuses=required_statuses,
                    present=False,
                ),
                [f"pass{pass_number}_missing_artifact:{path.name}"],
            )
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return (
                LaunchEvidenceArtifact(
                    pass_number=pass_number,
                    name=name,
                    path=str(path),
                    required_statuses=required_statuses,
                    present=True,
                    sha256=sha,
                ),
                [f"pass{pass_number}_artifact_not_json:{path.name}"],
            )
        if not isinstance(payload, dict):
            return (
                LaunchEvidenceArtifact(
                    pass_number=pass_number,
                    name=name,
                    path=str(path),
                    required_statuses=required_statuses,
                    present=True,
                    sha256=sha,
                ),
                [f"pass{pass_number}_artifact_not_object:{path.name}"],
            )
        status_value = str(
            payload.get("status")
            or payload.get("readiness")
            or payload.get("signoff_status")
            or payload.get("approval_status")
            or ""
        ).strip()
        artifact = LaunchEvidenceArtifact(
            pass_number=pass_number,
            name=name,
            path=str(path),
            required_statuses=required_statuses,
            present=True,
            status_value=status_value,
            sha256=sha,
            payload=payload,
        )
        if status_value not in required_statuses:
            return artifact, [f"pass{pass_number}_artifact_status_not_ready:{path.name}:{status_value or 'missing_status'}"]
        return artifact, []

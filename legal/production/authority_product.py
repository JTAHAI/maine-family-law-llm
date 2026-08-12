from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.data_boundaries.storage_layout import is_inside_project_repo

_MAX_CONTROL_FILE_BYTES = 64 * 1024 * 1024
_MAX_ARTIFACT_COUNT = 250_000
_SCHEMA_VERSION = "1.1"


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass


def _read_json(path: Path) -> Any:
    if path.is_symlink():
        raise ValueError(f"control file may not be a symlink: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if size > _MAX_CONTROL_FILE_BYTES:
        raise ValueError(f"control file exceeds {_MAX_CONTROL_FILE_BYTES} bytes: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class AuthorityProductFinding:
    code: str
    message: str
    path: str | None = None
    source_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.path is not None:
            payload["path"] = self.path
        if self.source_id is not None:
            payload["source_id"] = self.source_id
        return payload


@dataclass
class AuthorityProductReport:
    status: str
    data_root: str
    build_id: str | None = None
    build_manifest_path: str | None = None
    active_pointer_path: str | None = None
    source_count: int = 0
    artifact_count: int = 0
    findings: list[AuthorityProductFinding] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "build_id": self.build_id,
            "build_manifest_path": self.build_manifest_path,
            "active_pointer_path": self.active_pointer_path,
            "source_count": self.source_count,
            "artifact_count": self.artifact_count,
            "findings": [finding.as_dict() for finding in self.findings],
            "blockers": sorted(set(self.blockers)),
        }


class _AuthorityProductBase:
    def __init__(self, *, data_root: str | Path, repo_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root else None
        self.product_root = self.data_root / "authority_product"
        self.builds_root = self.product_root / "builds"
        self.active_pointer = self.product_root / "ACTIVE_BUILD.json"

    def _safe_data_path(self, raw: str | Path, *, base: Path | None = None) -> Path:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (base or self.data_root) / candidate
        lexical = Path(os.path.abspath(candidate))
        try:
            relative = lexical.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError(f"path escapes external data root: {raw}") from exc
        current = self.data_root
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ValueError(f"symlinked authority path component is not allowed: {current}")
        resolved = lexical.resolve()
        try:
            resolved.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError(f"resolved path escapes external data root: {raw}") from exc
        return resolved

    def _safe_mkdir(self, path: Path) -> None:
        target = Path(os.path.abspath(path))
        relative = target.relative_to(self.data_root)
        current = self.data_root
        for part in relative.parts:
            current = current / part
            if current.exists():
                if current.is_symlink() or not current.is_dir():
                    raise ValueError(f"unsafe authority directory component: {current}")
            else:
                current.mkdir()

    @staticmethod
    def _copy_verified(source: Path, destination: Path, *, expected_hash: str, expected_size: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
        try:
            with source.open("rb") as input_handle, temporary.open("xb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
                output_handle.flush()
                os.fsync(output_handle.fileno())
            if temporary.stat().st_size != expected_size or _sha256_file(temporary) != expected_hash:
                raise ValueError(f"copied authority artifact failed verification: {source}")
            os.replace(temporary, destination)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _artifact_row(*, role: str, path: Path, data_root: Path) -> dict[str, Any]:
        return {
            "role": role,
            "relative_path": path.relative_to(data_root).as_posix(),
            "sha256": _sha256_file(path),
            "size": path.stat().st_size,
        }


class AuthorityProductPublisher(_AuthorityProductBase):
    """Publish a verified immutable generation of the external authority product."""

    CONTROL_ARTIFACTS = {
        "source_manifest": "official_authority_store/source_manifest.json",
        "parsed_manifest": "parsed_authority_store/parsed_authority_manifest.json",
        "authority_layer_report": "authority_layer/authority_layer_report.json",
        "retrieval_index_manifest": "embedding_store/retrieval_index_manifest.json",
        "source_update_report": "source_update_report.json",
    }

    def publish(self, *, product_version: str = "unknown", activate: bool = True) -> AuthorityProductReport:
        findings: list[AuthorityProductFinding] = []
        blockers: list[str] = []

        if self.repo_root and is_inside_project_repo(self.data_root, self.repo_root):
            blockers.append("authority_product_inside_repo")
            findings.append(
                AuthorityProductFinding(
                    "authority_product_inside_repo",
                    "The official authority data product must remain outside the source repository.",
                    str(self.data_root),
                )
            )

        controls: dict[str, Any] = {}
        control_paths: dict[str, Path] = {}
        for role, relative in self.CONTROL_ARTIFACTS.items():
            path = self._safe_data_path(relative)
            try:
                controls[role] = _read_json(path)
                control_paths[role] = path
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                blockers.append("authority_control_artifact_invalid")
                findings.append(AuthorityProductFinding("authority_control_artifact_invalid", str(exc), str(path)))

        if blockers:
            return AuthorityProductReport(
                status="blocked",
                data_root=str(self.data_root),
                findings=findings,
                blockers=blockers,
            )

        self._validate_control_statuses(controls, findings, blockers)
        source_rows = controls["source_manifest"] if isinstance(controls["source_manifest"], list) else []
        if not source_rows:
            blockers.append("authority_source_manifest_empty")
            findings.append(AuthorityProductFinding("authority_source_manifest_empty", "No official source rows were found."))

        source_snapshots: list[dict[str, Any]] = []
        seen_source_ids: set[str] = set()
        for row in source_rows:
            if not isinstance(row, dict):
                blockers.append("authority_source_row_invalid")
                continue
            source_id = str(row.get("source_id") or "").strip()
            if not source_id or source_id in seen_source_ids:
                blockers.append("authority_source_id_invalid")
                findings.append(
                    AuthorityProductFinding(
                        "authority_source_id_invalid",
                        "Source IDs must be present and unique.",
                        source_id=source_id or None,
                    )
                )
                continue
            seen_source_ids.add(source_id)
            raw_snapshot = row.get("snapshot_path")
            if not raw_snapshot:
                blockers.append("authority_snapshot_path_missing")
                findings.append(
                    AuthorityProductFinding(
                        "authority_snapshot_path_missing",
                        "Official source row has no snapshot_path.",
                        source_id=source_id,
                    )
                )
                continue
            try:
                snapshot = self._safe_data_path(str(raw_snapshot), base=self.data_root / "official_authority_store")
                if not snapshot.is_file():
                    raise FileNotFoundError(snapshot)
                actual_hash = _sha256_file(snapshot)
                expected_hash = str(row.get("hash") or "")
                if actual_hash != expected_hash:
                    blockers.append("authority_snapshot_hash_mismatch")
                    findings.append(
                        AuthorityProductFinding(
                            "authority_snapshot_hash_mismatch",
                            f"Expected {expected_hash}; found {actual_hash}.",
                            str(snapshot),
                            source_id,
                        )
                    )
                    continue
                source_snapshots.append(
                    {
                        "source_id": source_id,
                        "source_class": row.get("source_class"),
                        "relative_path": snapshot.relative_to(self.data_root).as_posix(),
                        "sha256": actual_hash,
                        "size": snapshot.stat().st_size,
                        "freshness_status": row.get("freshness_status"),
                        "retrieved_at": row.get("retrieved_at"),
                    }
                )
            except (OSError, ValueError) as exc:
                blockers.append("authority_snapshot_invalid")
                findings.append(AuthorityProductFinding("authority_snapshot_invalid", str(exc), str(raw_snapshot), source_id))

        artifacts = [
            self._artifact_row(role=role, path=path, data_root=self.data_root)
            for role, path in sorted(control_paths.items())
        ]
        artifacts.extend(self._referenced_artifacts(controls, findings, blockers))
        try:
            artifacts = self._deduplicate_artifacts(artifacts)
        except ValueError as exc:
            blockers.append("authority_artifact_changed_during_publication")
            findings.append(AuthorityProductFinding("authority_artifact_changed_during_publication", str(exc)))
            artifacts = []
        if len(artifacts) > _MAX_ARTIFACT_COUNT:
            blockers.append("authority_artifact_count_exceeded")
            findings.append(
                AuthorityProductFinding(
                    "authority_artifact_count_exceeded",
                    f"Authority product has {len(artifacts)} artifacts; maximum is {_MAX_ARTIFACT_COUNT}.",
                )
            )

        fingerprint_input = {
            "schema_version": _SCHEMA_VERSION,
            "product_version": product_version,
            "sources": sorted(
                ({"source_id": row["source_id"], "sha256": row["sha256"]} for row in source_snapshots),
                key=lambda row: row["source_id"],
            ),
            "artifacts": sorted(
                ({"relative_path": row["relative_path"], "sha256": row["sha256"]} for row in artifacts),
                key=lambda row: row["relative_path"],
            ),
        }
        fingerprint = hashlib.sha256(_canonical_json(fingerprint_input)).hexdigest()
        build_id = fingerprint[:24]

        if blockers:
            return AuthorityProductReport(
                status="blocked",
                data_root=str(self.data_root),
                build_id=build_id,
                source_count=len(source_snapshots),
                artifact_count=len(artifacts),
                findings=findings,
                blockers=blockers,
            )

        manifest_path = self.builds_root / build_id / "authority_product_manifest.json"
        final_build_dir = manifest_path.parent
        materialized_sources: list[dict[str, Any]] = []
        materialized_artifacts: list[dict[str, Any]] = []
        if final_build_dir.exists():
            try:
                existing = _read_json(manifest_path)
                if str(existing.get("build_fingerprint")) != fingerprint:
                    raise ValueError("existing immutable build has a different fingerprint")
                materialized_sources = list(existing.get("source_snapshots") or [])
                materialized_artifacts = list(existing.get("artifacts") or [])
                if len(materialized_sources) != len(source_snapshots) or len(materialized_artifacts) != len(artifacts):
                    raise ValueError("existing immutable build is incomplete")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                blockers.append("immutable_build_collision")
                findings.append(AuthorityProductFinding("immutable_build_collision", str(exc), str(manifest_path)))
        else:
            staging_dir = self.builds_root / f".{build_id}.{uuid.uuid4().hex}.staging"
            try:
                self._safe_mkdir(self.builds_root)
                self._safe_mkdir(staging_dir)
                for ordinal, row in enumerate(sorted(source_snapshots, key=lambda item: item["source_id"]), start=1):
                    source = self._safe_data_path(str(row["relative_path"]))
                    suffix = source.suffix.lower() if source.suffix.lower() in {".html", ".htm", ".pdf", ".txt", ".json", ".xml", ".docx"} else ".bin"
                    destination_relative = Path("sources") / f"{ordinal:06d}-{str(row['sha256'])[:16]}{suffix}"
                    destination = staging_dir / destination_relative
                    self._copy_verified(
                        source,
                        destination,
                        expected_hash=str(row["sha256"]),
                        expected_size=int(row["size"]),
                    )
                    materialized_sources.append(
                        {
                            **row,
                            "source_relative_path": str(row["relative_path"]),
                            "relative_path": (
                                final_build_dir / destination_relative
                            ).relative_to(self.data_root).as_posix(),
                        }
                    )
                for row in sorted(artifacts, key=lambda item: item["relative_path"]):
                    source = self._safe_data_path(str(row["relative_path"]))
                    destination_relative = Path("artifacts") / str(row["relative_path"])
                    destination = staging_dir / destination_relative
                    self._copy_verified(
                        source,
                        destination,
                        expected_hash=str(row["sha256"]),
                        expected_size=int(row["size"]),
                    )
                    materialized_artifacts.append(
                        {
                            **row,
                            "source_relative_path": str(row["relative_path"]),
                            "relative_path": (
                                final_build_dir / destination_relative
                            ).relative_to(self.data_root).as_posix(),
                        }
                    )
                build_manifest = {
                    "schema_version": _SCHEMA_VERSION,
                    "build_id": build_id,
                    "build_fingerprint": fingerprint,
                    "product_version": product_version,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "data_root_policy": "external_only",
                    "source_count": len(materialized_sources),
                    "artifact_count": len(materialized_artifacts),
                    "freshness_counts": dict(controls["source_update_report"].get("freshness_counts") or {}),
                    "retrieval_document_count": int(controls["retrieval_index_manifest"].get("document_count") or 0),
                    "parsed_record_counts": dict(controls["parsed_manifest"].get("record_counts") or {}),
                    "source_snapshots": sorted(materialized_sources, key=lambda row: row["source_id"]),
                    "artifacts": sorted(materialized_artifacts, key=lambda row: row["relative_path"]),
                    "fingerprint_input": fingerprint_input,
                    "activation_policy": "materialize_verify_then_atomic_pointer",
                    "review_required": True,
                }
                _atomic_write_json(staging_dir / "authority_product_manifest.json", build_manifest)
                os.replace(staging_dir, final_build_dir)
            except (OSError, ValueError) as exc:
                blockers.append("authority_build_materialization_failed")
                findings.append(AuthorityProductFinding("authority_build_materialization_failed", str(exc), str(staging_dir)))
                shutil.rmtree(staging_dir, ignore_errors=True)

        manifest_hash = _sha256_file(manifest_path) if manifest_path.exists() else ""
        if not blockers and manifest_path.exists():
            verification = AuthorityProductVerifier(data_root=self.data_root).verify(build_id=build_id)
            if verification.status != "pass":
                blockers.append("authority_build_self_verification_failed")
                findings.extend(verification.findings)
        if activate and not blockers:
            try:
                self._safe_mkdir(self.product_root)
                pointer = {
                    "schema_version": _SCHEMA_VERSION,
                    "build_id": build_id,
                    "manifest_relative_path": manifest_path.relative_to(self.data_root).as_posix(),
                    "manifest_sha256": manifest_hash,
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                }
                _atomic_write_json(self.active_pointer, pointer)
            except (OSError, ValueError) as exc:
                blockers.append("authority_activation_failed")
                findings.append(AuthorityProductFinding("authority_activation_failed", str(exc), str(self.active_pointer)))

        return AuthorityProductReport(
            status="pass" if not blockers else "blocked",
            data_root=str(self.data_root),
            build_id=build_id,
            build_manifest_path=str(manifest_path),
            active_pointer_path=str(self.active_pointer) if activate and not blockers else None,
            source_count=len(source_snapshots),
            artifact_count=len(artifacts),
            findings=findings,
            blockers=blockers,
        )

    @staticmethod
    def _validate_control_statuses(
        controls: dict[str, Any],
        findings: list[AuthorityProductFinding],
        blockers: list[str],
    ) -> None:
        for role in ("authority_layer_report", "retrieval_index_manifest", "source_update_report"):
            payload = controls.get(role)
            if not isinstance(payload, dict) or payload.get("status") != "pass":
                blockers.append("authority_control_gate_not_passed")
                findings.append(
                    AuthorityProductFinding(
                        "authority_control_gate_not_passed",
                        f"{role} must report status=pass before activation.",
                    )
                )
        if not isinstance(controls.get("parsed_manifest"), dict):
            blockers.append("parsed_manifest_invalid")
        if not isinstance(controls.get("source_manifest"), list):
            blockers.append("source_manifest_invalid")

    def _referenced_artifacts(
        self,
        controls: dict[str, Any],
        findings: list[AuthorityProductFinding],
        blockers: list[str],
    ) -> list[dict[str, Any]]:
        referenced: list[tuple[str, Any]] = []
        parsed_outputs = controls["parsed_manifest"].get("output_files") or {}
        if isinstance(parsed_outputs, dict):
            referenced.extend((f"parsed_collection:{name}", path) for name, path in parsed_outputs.items())
        authority_outputs = controls["authority_layer_report"].get("outputs") or {}
        if isinstance(authority_outputs, dict):
            referenced.extend((f"authority_layer:{name}", path) for name, path in authority_outputs.items())
        retrieval_outputs = controls["retrieval_index_manifest"].get("outputs") or {}
        if isinstance(retrieval_outputs, dict):
            referenced.extend((f"retrieval_index:{name}", path) for name, path in retrieval_outputs.items())

        artifacts: list[dict[str, Any]] = []
        for role, raw_path in referenced:
            try:
                path = self._safe_data_path(str(raw_path))
                if not path.is_file():
                    raise FileNotFoundError(path)
                artifacts.append(self._artifact_row(role=role, path=path, data_root=self.data_root))
            except (OSError, ValueError) as exc:
                blockers.append("authority_referenced_artifact_invalid")
                findings.append(AuthorityProductFinding("authority_referenced_artifact_invalid", str(exc), str(raw_path)))
        return artifacts

    @staticmethod
    def _deduplicate_artifacts(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        by_path: dict[str, dict[str, Any]] = {}
        for row in rows:
            relative = str(row["relative_path"])
            existing = by_path.get(relative)
            if existing is None:
                by_path[relative] = dict(row)
            elif existing["sha256"] != row["sha256"]:
                raise ValueError(f"artifact changed during publication: {relative}")
            else:
                roles = sorted(set(str(existing["role"]).split("|") + [str(row["role"])]))
                existing["role"] = "|".join(roles)
        return list(by_path.values())


class AuthorityProductVerifier(_AuthorityProductBase):
    """Verify an immutable authority generation and its active pointer."""

    def verify(self, *, build_id: str | None = None) -> AuthorityProductReport:
        findings: list[AuthorityProductFinding] = []
        blockers: list[str] = []
        manifest_path: Path | None = None

        if build_id is None:
            try:
                pointer = _read_json(self.active_pointer)
                build_id = str(pointer.get("build_id") or "")
                raw_manifest = str(pointer.get("manifest_relative_path") or "")
                manifest_path = self._safe_data_path(raw_manifest)
                actual_manifest_hash = _sha256_file(manifest_path)
                if actual_manifest_hash != str(pointer.get("manifest_sha256") or ""):
                    blockers.append("active_manifest_hash_mismatch")
                    findings.append(
                        AuthorityProductFinding(
                            "active_manifest_hash_mismatch",
                            "The active pointer no longer matches the immutable build manifest.",
                            str(manifest_path),
                        )
                    )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                blockers.append("active_build_pointer_invalid")
                findings.append(AuthorityProductFinding("active_build_pointer_invalid", str(exc), str(self.active_pointer)))
        else:
            if not build_id or any(character not in "0123456789abcdef" for character in build_id.lower()) or len(build_id) != 24:
                blockers.append("build_id_invalid")
            manifest_path = self.builds_root / build_id / "authority_product_manifest.json"

        manifest: dict[str, Any] = {}
        if manifest_path is not None and not blockers:
            try:
                manifest = _read_json(manifest_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                blockers.append("authority_product_manifest_invalid")
                findings.append(AuthorityProductFinding("authority_product_manifest_invalid", str(exc), str(manifest_path)))

        sources = manifest.get("source_snapshots") if isinstance(manifest.get("source_snapshots"), list) else []
        artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
        if len(sources) + len(artifacts) > _MAX_ARTIFACT_COUNT:
            blockers.append("authority_artifact_count_exceeded")

        fingerprint_input = manifest.get("fingerprint_input")
        if isinstance(fingerprint_input, dict):
            fingerprint = hashlib.sha256(_canonical_json(fingerprint_input)).hexdigest()
            if fingerprint != str(manifest.get("build_fingerprint") or "") or fingerprint[:24] != str(build_id or ""):
                blockers.append("authority_build_fingerprint_mismatch")
                findings.append(
                    AuthorityProductFinding(
                        "authority_build_fingerprint_mismatch",
                        "Build ID/fingerprint does not match the recorded immutable inputs.",
                        str(manifest_path) if manifest_path else None,
                    )
                )
        else:
            blockers.append("authority_build_fingerprint_missing")

        self._verify_rows(sources, findings, blockers, source_rows=True)
        self._verify_rows(artifacts, findings, blockers, source_rows=False)

        return AuthorityProductReport(
            status="pass" if not blockers else "blocked",
            data_root=str(self.data_root),
            build_id=build_id,
            build_manifest_path=str(manifest_path) if manifest_path else None,
            active_pointer_path=str(self.active_pointer) if self.active_pointer.exists() else None,
            source_count=len(sources),
            artifact_count=len(artifacts),
            findings=findings,
            blockers=blockers,
        )

    def _verify_rows(
        self,
        rows: list[Any],
        findings: list[AuthorityProductFinding],
        blockers: list[str],
        *,
        source_rows: bool,
    ) -> None:
        for row in rows:
            if not isinstance(row, dict):
                blockers.append("authority_product_row_invalid")
                continue
            raw_path = str(row.get("relative_path") or "")
            try:
                path = self._safe_data_path(raw_path)
                if not path.is_file():
                    raise FileNotFoundError(path)
                actual_size = path.stat().st_size
                actual_hash = _sha256_file(path)
                if actual_size != int(row.get("size") or -1):
                    blockers.append("authority_product_size_mismatch")
                    findings.append(
                        AuthorityProductFinding(
                            "authority_product_size_mismatch",
                            f"Expected {row.get('size')}; found {actual_size}.",
                            str(path),
                            str(row.get("source_id")) if source_rows else None,
                        )
                    )
                if actual_hash != str(row.get("sha256") or ""):
                    blockers.append("authority_product_hash_mismatch")
                    findings.append(
                        AuthorityProductFinding(
                            "authority_product_hash_mismatch",
                            f"Expected {row.get('sha256')}; found {actual_hash}.",
                            str(path),
                            str(row.get("source_id")) if source_rows else None,
                        )
                    )
            except (OSError, ValueError) as exc:
                blockers.append("authority_product_path_invalid")
                findings.append(
                    AuthorityProductFinding(
                        "authority_product_path_invalid",
                        str(exc),
                        raw_path,
                        str(row.get("source_id")) if source_rows else None,
                    )
                )

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .frontmatter import dump_frontmatter, split_document
from .models import KnowledgeBundleError, KnowledgeConcept, parse_concept_id

_RESERVED_NAMES = {"index.md", "log.md", "manifest.json"}
_MAX_CONCEPT_FILE_BYTES = 6 * 1024 * 1024
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
_MAX_CONCEPTS = 10_000


@dataclass(frozen=True)
class BundleValidationReport:
    status: str
    concept_count: int
    errors: tuple[str, ...]
    manifest_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "concept_count": self.concept_count,
            "errors": list(self.errors),
            "manifest_sha256": self.manifest_sha256,
        }


def _within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _reject_symlink_chain(root: Path, path: Path) -> None:
    relative = path.relative_to(root)
    current = root
    if root.is_symlink():
        raise KnowledgeBundleError("symlink bundle roots are not allowed")
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise KnowledgeBundleError(f"symlink path component is not allowed: {relative}")


def concept_path(root: Path, concept_id: str) -> Path:
    parts = parse_concept_id(concept_id)
    candidate = root.joinpath(*parts[:-1], f"{parts[-1]}.md")
    if candidate.name in _RESERVED_NAMES:
        raise KnowledgeBundleError(f"reserved concept filename: {candidate.name}")
    return candidate


def write_concept(root: Path, concept: KnowledgeConcept) -> Path:
    raw_root = root.expanduser()
    if raw_root.exists() and raw_root.is_symlink():
        raise KnowledgeBundleError("symlink bundle roots are not allowed")
    bundle_root = raw_root.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    path = concept_path(bundle_root, concept.concept_id)
    _reject_symlink_chain(bundle_root, path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = path.parent.resolve(strict=True)
    if not _within(bundle_root, resolved_parent):
        raise KnowledgeBundleError("concept path escaped bundle root")
    if path.exists() and path.is_symlink():
        raise KnowledgeBundleError("symlink concepts are not allowed")
    document = f"{dump_frontmatter(concept.frontmatter())}\n{concept.body.rstrip()}\n"
    encoded = document.encode("utf-8")
    if len(encoded) > _MAX_CONCEPT_FILE_BYTES:
        raise KnowledgeBundleError("concept file exceeds 6 MiB")
    path.write_bytes(encoded)
    return path


def read_concept(root: Path, path: Path) -> KnowledgeConcept:
    raw_root = root.expanduser()
    if raw_root.is_symlink():
        raise KnowledgeBundleError("symlink bundle roots are not allowed")
    bundle_root = raw_root.resolve(strict=True)
    if path.is_symlink():
        raise KnowledgeBundleError("symlink concepts are not allowed")
    resolved = path.resolve(strict=True)
    if not _within(bundle_root, resolved) or resolved == bundle_root:
        raise KnowledgeBundleError("concept path escaped bundle root")
    _reject_symlink_chain(bundle_root, resolved)
    if resolved.name in _RESERVED_NAMES or resolved.suffix.lower() != ".md":
        raise KnowledgeBundleError("invalid concept filename")
    if resolved.stat().st_size > _MAX_CONCEPT_FILE_BYTES:
        raise KnowledgeBundleError("concept file exceeds 6 MiB")
    values, body = split_document(resolved.read_text(encoding="utf-8"))
    concept_id = resolved.relative_to(bundle_root).with_suffix("").as_posix()
    known = {"type", "title", "description", "resource", "tags", "timestamp", "citations"}
    return KnowledgeConcept(
        concept_id=concept_id,
        type=str(values.get("type", "")),
        title=str(values.get("title", "")),
        description=str(values.get("description", "")),
        resource=str(values.get("resource", "")),
        tags=tuple(values.get("tags", [])),
        timestamp=str(values.get("timestamp", "")),
        citations=tuple(values.get("citations", [])),
        body=body.rstrip(),
        metadata={key: value for key, value in values.items() if key not in known},
    )


def _index_for(directory: Path, concepts: Iterable[KnowledgeConcept]) -> str:
    rows = ["# Knowledge index", ""]
    for concept in sorted(concepts, key=lambda item: item.concept_id):
        relative = concept_path(directory, concept.concept_id).relative_to(directory).as_posix()
        rows.append(f"- [{concept.title}]({relative}) — {concept.type}")
    rows.append("")
    return "\n".join(rows)


def _walk_bundle_files(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    errors: list[str] = []
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept: list[str] = []
        for name in sorted(dirs, key=str.casefold):
            candidate = current_path / name
            if candidate.is_symlink():
                errors.append(f"symlink directory blocked: {candidate.relative_to(root).as_posix()}")
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(names, key=str.casefold):
            candidate = current_path / name
            if candidate.is_symlink():
                errors.append(f"symlink file blocked: {candidate.relative_to(root).as_posix()}")
            elif candidate.is_file():
                files.append(candidate)
    return files, errors


def build_bundle(root: Path, concepts: Iterable[KnowledgeConcept]) -> BundleValidationReport:
    raw_root = root.expanduser()
    if raw_root.exists() and raw_root.is_symlink():
        raise KnowledgeBundleError("symlink bundle roots are not allowed")
    bundle_root = raw_root.resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)
    concept_list = tuple(concepts)
    if len(concept_list) > _MAX_CONCEPTS:
        raise KnowledgeBundleError("bundle contains too many concepts")
    seen: set[str] = set()
    desired_paths: set[str] = set()
    for concept in concept_list:
        if concept.concept_id in seen:
            raise KnowledgeBundleError(f"duplicate concept id: {concept.concept_id}")
        seen.add(concept.concept_id)
        desired_paths.add(concept_path(bundle_root, concept.concept_id).relative_to(bundle_root).as_posix())

    existing_files, walk_errors = _walk_bundle_files(bundle_root)
    if walk_errors:
        raise KnowledgeBundleError("; ".join(walk_errors))
    stale_concepts = {
        path.relative_to(bundle_root).as_posix()
        for path in existing_files
        if path.suffix.lower() == ".md" and path.name not in {"index.md", "log.md"}
    } - desired_paths
    if stale_concepts:
        raise KnowledgeBundleError(
            "bundle contains stale concept files: " + ", ".join(sorted(stale_concepts))
        )
    for control_name in ("index.md", "manifest.json"):
        control_path = bundle_root / control_name
        if control_path.exists() and control_path.is_symlink():
            raise KnowledgeBundleError(f"symlink control file blocked: {control_name}")

    manifest_rows: list[dict[str, str]] = []
    for concept in concept_list:
        path = write_concept(bundle_root, concept)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_rows.append(
            {
                "concept_id": concept.concept_id,
                "path": path.relative_to(bundle_root).as_posix(),
                "sha256": digest,
            }
        )
    (bundle_root / "index.md").write_text(
        _index_for(bundle_root, concept_list), encoding="utf-8", newline="\n"
    )
    manifest = {
        "schema": "mfl_knowledge_bundle_v1",
        "format_inspiration": "Open Knowledge Format v0.1",
        "concepts": sorted(manifest_rows, key=lambda row: row["concept_id"]),
    }
    raw = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if len(raw.encode("utf-8")) > _MAX_MANIFEST_BYTES:
        raise KnowledgeBundleError("manifest exceeds size limit")
    (bundle_root / "manifest.json").write_text(raw, encoding="utf-8", newline="\n")
    return validate_bundle(bundle_root)


def _safe_manifest_path(bundle_root: Path, value: object) -> tuple[Path, str]:
    if not isinstance(value, str) or not value:
        raise KnowledgeBundleError("manifest concept path must be a non-empty string")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise KnowledgeBundleError(f"unsafe manifest path: {value!r}")
    if pure.suffix.lower() != ".md" or pure.name in _RESERVED_NAMES:
        raise KnowledgeBundleError(f"invalid manifest concept path: {value!r}")
    target = bundle_root.joinpath(*pure.parts)
    if target.is_symlink():
        raise KnowledgeBundleError(f"symlink manifest target blocked: {value}")
    resolved = target.resolve(strict=True)
    if not _within(bundle_root, resolved) or resolved == bundle_root:
        raise KnowledgeBundleError(f"manifest path escaped root: {value}")
    _reject_symlink_chain(bundle_root, resolved)
    return resolved, pure.as_posix()


def validate_bundle(root: Path) -> BundleValidationReport:
    raw_root = root.expanduser()
    errors: list[str] = []
    if raw_root.is_symlink():
        return BundleValidationReport("fail", 0, ("symlink bundle roots are not allowed",))
    try:
        bundle_root = raw_root.resolve(strict=True)
    except OSError as exc:
        return BundleValidationReport("fail", 0, (f"bundle root invalid: {exc}",))
    if not bundle_root.is_dir():
        return BundleValidationReport("fail", 0, ("bundle root is not a directory",))

    all_files, walk_errors = _walk_bundle_files(bundle_root)
    errors.extend(walk_errors)
    allowed_control = {"index.md", "log.md", "manifest.json"}
    concept_files: list[Path] = []
    for path in all_files:
        relative = path.relative_to(bundle_root).as_posix()
        if path.name in allowed_control:
            continue
        if path.suffix.lower() != ".md":
            errors.append(f"unexpected bundle file: {relative}")
            continue
        concept_files.append(path)
    if len(concept_files) > _MAX_CONCEPTS:
        errors.append("bundle contains too many concepts")

    concepts: list[KnowledgeConcept] = []
    actual_paths: set[str] = set()
    for path in sorted(concept_files):
        relative = path.relative_to(bundle_root).as_posix()
        actual_paths.add(relative)
        try:
            concepts.append(read_concept(bundle_root, path))
        except (KnowledgeBundleError, OSError, UnicodeDecodeError) as exc:
            errors.append(f"{relative}: {exc}")

    manifest_path = bundle_root / "manifest.json"
    manifest_sha: str | None = None
    manifest_paths: set[str] = set()
    if manifest_path.exists() and not manifest_path.is_symlink():
        try:
            if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
                raise KnowledgeBundleError("manifest exceeds size limit")
            raw = manifest_path.read_bytes()
            manifest_sha = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise KnowledgeBundleError("manifest must be a JSON object")
            if payload.get("schema") != "mfl_knowledge_bundle_v1":
                errors.append("manifest schema is invalid")
            rows = payload.get("concepts")
            if not isinstance(rows, list):
                raise KnowledgeBundleError("manifest concepts must be a list")
            if len(rows) > _MAX_CONCEPTS:
                raise KnowledgeBundleError("manifest contains too many concepts")
            manifest_ids: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise KnowledgeBundleError("manifest concept rows must be objects")
                concept_id = row.get("concept_id")
                if not isinstance(concept_id, str):
                    raise KnowledgeBundleError("manifest concept_id must be a string")
                parse_concept_id(concept_id)
                if concept_id in manifest_ids:
                    errors.append(f"duplicate manifest concept id: {concept_id}")
                manifest_ids.add(concept_id)
                resolved, relative = _safe_manifest_path(bundle_root, row.get("path"))
                if relative in manifest_paths:
                    errors.append(f"duplicate manifest path: {relative}")
                manifest_paths.add(relative)
                expected_path = concept_path(bundle_root, concept_id).relative_to(bundle_root).as_posix()
                if relative != expected_path:
                    errors.append(
                        f"manifest concept/path mismatch: {concept_id} -> {relative}"
                    )
                digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
                expected_digest = row.get("sha256")
                if not isinstance(expected_digest, str) or not re_full_sha256(expected_digest):
                    errors.append(f"invalid manifest hash: {relative}")
                elif digest != expected_digest:
                    errors.append(f"hash mismatch: {relative}")
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"manifest invalid: {exc}")
    else:
        errors.append("manifest.json is missing or is a symlink")

    for missing in sorted(manifest_paths - actual_paths):
        errors.append(f"manifest references missing concept: {missing}")
    for untracked in sorted(actual_paths - manifest_paths):
        errors.append(f"concept missing from manifest: {untracked}")

    return BundleValidationReport(
        status="pass" if not errors else "fail",
        concept_count=len(concepts),
        errors=tuple(errors),
        manifest_sha256=manifest_sha,
    )


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())

"""Immutable authority-generation change impact and matter revalidation.

The workbench compares two verified external authority generations and maps
changed official sources to a saved document and its most recent review packet.
A changed authority generation never proves that the law changed in a legally
material way; it creates review work and invalidates affected approvals until a
qualified human revalidates the exact revision against the new generation.
"""

from __future__ import annotations

import hashlib
import html
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.data_boundaries.storage_layout import is_inside_project_repo
from legal.documents.workspace import get_document, workspace_paths
from legal.production.authority_product import AuthorityProductVerifier
from legal.review.review_ledger import list_review_history

SCHEMA_VERSION = "authority_change_impact_v1"
ALGORITHM_VERSION = "5.15.0-authority-impact-v1"
ROOT_FOLDER = "21_AUTHORITY_CHANGE_IMPACT"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_GENERATIONS = 200
MAX_SOURCE_ROWS = 250_000
MAX_REFERENCES = 5_000
_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_BUILD_RE = re.compile(r"^[a-f0-9]{24}$")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_FORM_RE = re.compile(r"\b(?:FM|PA|CV|PB)[ -]?\d{1,4}[A-Z]?\b", re.IGNORECASE)
_CITATION_RE = re.compile(
    r"\b(?:\d{4}\s+ME\s+\d+|\d{1,2}(?:-A)?\s+M\.R\.S\.\s*§+\s*[\w.-]+|M\.R\.\s+Civ\.\s+P\.\s*\d+[A-Za-z.-]*)\b",
    re.IGNORECASE,
)
_LOCK = threading.RLock()


class AuthorityImpactError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: Any) -> str:
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _validate_build_id(value: Any, label: str = "build_id") -> str:
    candidate = str(value or "").strip().lower()
    if not _BUILD_RE.fullmatch(candidate):
        raise AuthorityImpactError(f"invalid_{label}", f"Invalid {label}.", status_code=404)
    return candidate


def _validate_document_id(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if not _ID_RE.fullmatch(candidate):
        raise AuthorityImpactError("invalid_document_id", "Invalid document ID.", status_code=404)
    return candidate


def _atomic_write(path: Path, data: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise AuthorityImpactError("authority_impact_symlink_refused", "An authority-impact symlink was refused.", status_code=409)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise AuthorityImpactError("authority_impact_record_unavailable", "An authority-impact record is unavailable.", status_code=404)
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise AuthorityImpactError("authority_impact_record_too_large", "An authority-impact record is unexpectedly large.", status_code=409)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityImpactError("authority_impact_record_invalid", "An authority-impact record is invalid.", status_code=409) from exc
    if not isinstance(payload, dict):
        raise AuthorityImpactError("authority_impact_record_invalid", "An authority-impact record is invalid.", status_code=409)
    return payload


def _safe_form_ids(text: str) -> list[str]:
    return sorted({match.group(0).upper().replace(" ", "-") for match in _FORM_RE.finditer(text or "")})


def _safe_citations(text: str) -> list[str]:
    return sorted({match.group(0).strip() for match in _CITATION_RE.finditer(text or "")})


def _review_request(case_root: Path, document_id: str, request_id: str) -> dict[str, Any]:
    paths = workspace_paths(case_root)
    path = paths.root / "reviews" / document_id / "requests" / f"{request_id}.json"
    try:
        resolved = path.resolve(strict=True)
        root = (paths.root / "reviews").resolve(strict=True)
    except OSError as exc:
        raise AuthorityImpactError("review_request_unavailable", "The prior review request is unavailable.", status_code=409) from exc
    if root not in resolved.parents or resolved.is_symlink():
        raise AuthorityImpactError("review_request_path_invalid", "The prior review request path is invalid.", status_code=409)
    request = _read_json(resolved)
    stored = str(request.get("request_sha256") or "")
    check = dict(request)
    check.pop("request_sha256", None)
    if not _SHA_RE.fullmatch(stored) or not hmac.compare_digest(stored, _sha(check)):
        raise AuthorityImpactError("review_request_hash_mismatch", "The prior review request failed its integrity check.", status_code=409)
    return request


def _latest_review_packet(case_root: Path, document_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    history = list_review_history(case_root, document_id)
    for decision in history.get("decisions") or []:
        request_id = str(decision.get("request_id") or "")
        if not _ID_RE.fullmatch(request_id):
            continue
        request = _review_request(case_root, document_id, request_id)
        packet = request.get("packet")
        if isinstance(packet, dict):
            return decision, packet
    return None, None


class AuthorityChangeImpactStore:
    """Compare verified authority generations and create immutable revalidation packets."""

    def __init__(self, case_root: str | Path, *, data_root: str | Path, repo_root: str | Path | None = None) -> None:
        self.case_root = Path(case_root).expanduser().resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root else Path.cwd().resolve()
        if is_inside_project_repo(self.data_root, self.repo_root):
            raise AuthorityImpactError("authority_data_root_inside_repo", "Authority data must remain outside the source repository.", status_code=409)
        self.authority_product_root = self.data_root / "authority_product"
        self.builds_root = self.authority_product_root / "builds"
        self.root = self.case_root / ROOT_FOLDER
        self.builds = self.root / "builds"
        self.active_pointer = self.root / "ACTIVE_BUILD.json"
        self.builds.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _manifest_path(self, build_id: str) -> Path:
        build_id = _validate_build_id(build_id)
        path = self.builds_root / build_id / "authority_product_manifest.json"
        try:
            resolved = path.resolve(strict=True)
            root = self.builds_root.resolve(strict=True)
        except OSError as exc:
            raise AuthorityImpactError("authority_generation_unavailable", "The requested authority generation is unavailable.", status_code=404) from exc
        if root not in resolved.parents or resolved.is_symlink():
            raise AuthorityImpactError("authority_generation_path_invalid", "The authority generation path is invalid.", status_code=409)
        verification = AuthorityProductVerifier(data_root=self.data_root).verify(build_id=build_id)
        if verification.status != "pass":
            raise AuthorityImpactError("authority_generation_unverified", "The requested authority generation failed verification.", status_code=409)
        return resolved

    def _manifest(self, build_id: str) -> dict[str, Any]:
        manifest = _read_json(self._manifest_path(build_id))
        if str(manifest.get("build_id") or "") != build_id:
            raise AuthorityImpactError("authority_generation_identity_mismatch", "The authority generation identity does not match its path.", status_code=409)
        rows = manifest.get("source_snapshots")
        if not isinstance(rows, list) or len(rows) > MAX_SOURCE_ROWS:
            raise AuthorityImpactError("authority_generation_source_rows_invalid", "The authority generation source list is invalid.", status_code=409)
        return manifest

    def list_generations(self) -> dict[str, Any]:
        active_id = ""
        if self.authority_product_root.joinpath("ACTIVE_BUILD.json").is_file():
            try:
                active_id = str(_read_json(self.authority_product_root / "ACTIVE_BUILD.json").get("build_id") or "")
            except AuthorityImpactError:
                active_id = ""
        rows: list[dict[str, Any]] = []
        if self.builds_root.is_dir() and not self.builds_root.is_symlink():
            for path in sorted(self.builds_root.iterdir(), reverse=True)[:MAX_GENERATIONS]:
                if not path.is_dir() or path.is_symlink() or not _BUILD_RE.fullmatch(path.name):
                    continue
                verification = AuthorityProductVerifier(data_root=self.data_root).verify(build_id=path.name)
                if verification.status != "pass":
                    continue
                manifest = _read_json(path / "authority_product_manifest.json")
                rows.append({
                    "build_id": path.name,
                    "product_version": manifest.get("product_version"),
                    "generated_at": manifest.get("generated_at"),
                    "source_count": manifest.get("source_count", 0),
                    "freshness_counts": manifest.get("freshness_counts") or {},
                    "active": path.name == active_id,
                    "verified": True,
                })
        rows.sort(key=lambda row: (str(row.get("generated_at") or ""), str(row.get("build_id") or "")), reverse=True)
        return {
            "status": "available" if rows else "blocked",
            "active_build_id": active_id,
            "generations": rows,
            "blockers": [] if rows else ["verified_authority_generations_unavailable"],
            "review_required": True,
        }

    @staticmethod
    def _source_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in manifest.get("source_snapshots") or []:
            if not isinstance(raw, dict):
                continue
            source_id = str(raw.get("source_id") or "").strip()
            if source_id:
                result[source_id] = {
                    "source_id": source_id,
                    "source_class": str(raw.get("source_class") or ""),
                    "sha256": str(raw.get("sha256") or ""),
                    "freshness_status": str(raw.get("freshness_status") or "unknown"),
                    "retrieved_at": str(raw.get("retrieved_at") or ""),
                }
        return result

    def compare(self, base_build_id: str, target_build_id: str) -> dict[str, Any]:
        base_build_id = _validate_build_id(base_build_id, "base_build_id")
        target_build_id = _validate_build_id(target_build_id, "target_build_id")
        if base_build_id == target_build_id:
            raise AuthorityImpactError("authority_generations_identical", "Choose two different authority generations.", status_code=409)
        base = self._manifest(base_build_id)
        target = self._manifest(target_build_id)
        before = self._source_map(base)
        after = self._source_map(target)
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        hash_changed = sorted(source_id for source_id in set(before) & set(after) if before[source_id]["sha256"] != after[source_id]["sha256"])
        metadata_changed = sorted(
            source_id for source_id in set(before) & set(after)
            if before[source_id]["sha256"] == after[source_id]["sha256"]
            and (before[source_id]["freshness_status"], before[source_id]["source_class"])
            != (after[source_id]["freshness_status"], after[source_id]["source_class"])
        )
        changed_rows: list[dict[str, Any]] = []
        for source_id in added:
            changed_rows.append({"source_id": source_id, "change_type": "added", "before": None, "after": after[source_id]})
        for source_id in removed:
            changed_rows.append({"source_id": source_id, "change_type": "removed", "before": before[source_id], "after": None})
        for source_id in hash_changed:
            changed_rows.append({"source_id": source_id, "change_type": "content_hash_changed", "before": before[source_id], "after": after[source_id]})
        for source_id in metadata_changed:
            changed_rows.append({"source_id": source_id, "change_type": "metadata_changed", "before": before[source_id], "after": after[source_id]})
        return {
            "schema_version": "authority_generation_diff_v1",
            "base_build_id": base_build_id,
            "target_build_id": target_build_id,
            "base_manifest_sha256": _sha(self._manifest_path(base_build_id).read_bytes()),
            "target_manifest_sha256": _sha(self._manifest_path(target_build_id).read_bytes()),
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "content_hash_changed": len(hash_changed),
                "metadata_changed": len(metadata_changed),
                "unchanged": len(set(before) & set(after)) - len(hash_changed) - len(metadata_changed),
            },
            "changed_source_ids": sorted(set(added + removed + hash_changed + metadata_changed)),
            "changes": sorted(changed_rows, key=lambda row: (row["source_id"], row["change_type"])),
            "target_freshness_counts": target.get("freshness_counts") or {},
            "generated_at": _utc_now(),
            "review_required": True,
            "notice": "A source hash or metadata change is a review signal, not a legal conclusion about the effect of the change.",
        }

    @staticmethod
    def _review_references(document: dict[str, Any], review_packet: dict[str, Any] | None) -> dict[str, Any]:
        source_ids: set[str] = set()
        form_ids: set[str] = set(_safe_form_ids(str(document.get("content") or "")))
        citations: set[str] = set(_safe_citations(str(document.get("content") or "")))
        for raw in document.get("source_refs") or []:
            if isinstance(raw, dict) and str(raw.get("source_id") or "").strip():
                source_ids.add(str(raw.get("source_id")).strip())
        packet = review_packet or {}
        authority = packet.get("authority_verification") or {}
        for raw in authority.get("sources") or []:
            if isinstance(raw, dict) and str(raw.get("source_id") or "").strip():
                source_ids.add(str(raw.get("source_id")).strip())
        for raw in packet.get("claims_for_review") or []:
            if not isinstance(raw, dict):
                continue
            for value in raw.get("source_ids") or []:
                value = str(value or "").strip()
                if value:
                    source_ids.add(value)
            citations.update(_safe_citations(str(raw.get("statement") or "")))
        forms = packet.get("forms_report") or {}
        for key in ("current_forms", "stale_forms", "unknown_forms"):
            form_ids.update(str(value or "").upper().replace(" ", "-") for value in forms.get(key) or [] if str(value or "").strip())
        if len(source_ids) + len(form_ids) + len(citations) > MAX_REFERENCES:
            raise AuthorityImpactError("authority_impact_reference_limit_exceeded", "The document has too many authority references for one revalidation run.", status_code=409)
        return {"source_ids": sorted(source_ids), "form_ids": sorted(form_ids), "citations": sorted(citations)}

    def analyze_document(self, document_id: str, base_build_id: str, target_build_id: str) -> dict[str, Any]:
        document_id = _validate_document_id(document_id)
        document = get_document(self.case_root, document_id)
        decision, review_packet = _latest_review_packet(self.case_root, document_id)
        generation_diff = self.compare(base_build_id, target_build_id)
        references = self._review_references(document, review_packet)
        changed_ids = set(generation_diff.get("changed_source_ids") or [])
        impacted_source_ids = sorted(changed_ids & set(references["source_ids"]))
        changed_rows = {str(row.get("source_id") or ""): row for row in generation_diff.get("changes") or [] if isinstance(row, dict)}
        impacted_changes = [changed_rows[source_id] for source_id in impacted_source_ids if source_id in changed_rows]
        form_related = sorted(
            row["source_id"] for row in generation_diff.get("changes") or []
            if isinstance(row, dict)
            and "form" in str(((row.get("after") or row.get("before") or {}).get("source_class") or "")).casefold()
        )
        target_freshness = generation_diff.get("target_freshness_counts") or {}
        blockers: list[str] = []
        if impacted_source_ids:
            blockers.append("authority_change_impacts_reviewed_sources")
            blockers.append("prior_review_stale_after_authority_change")
        if references["form_ids"] and form_related:
            blockers.append("court_form_sources_changed_recheck_required")
        if int(target_freshness.get("stale") or 0) > 0:
            blockers.append("target_authority_generation_contains_stale_sources")
        if int(target_freshness.get("unknown") or 0) > 0:
            blockers.append("target_authority_generation_contains_unknown_freshness")
        if decision is None or review_packet is None:
            blockers.append("prior_review_context_missing")
        prior_build = str(((review_packet or {}).get("authority_verification") or {}).get("build_id") or ((review_packet or {}).get("authority_verification") or {}).get("authority_build_id") or "")
        if prior_build and prior_build != str(base_build_id):
            blockers.append(f"base_generation_not_prior_review_generation:{prior_build}:{base_build_id}")
        impact = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "document_id": document_id,
            "document_title": document.get("title"),
            "revision_id": document.get("current_revision_id"),
            "document_content_sha256": document.get("content_sha256"),
            "base_build_id": base_build_id,
            "target_build_id": target_build_id,
            "prior_review_decision_sha256": (decision or {}).get("decision_sha256"),
            "prior_review_packet_sha256": (review_packet or {}).get("packet_sha256"),
            "generation_diff": generation_diff,
            "document_references": references,
            "impacted_source_ids": impacted_source_ids,
            "impacted_changes": impacted_changes,
            "form_source_changes": form_related,
            "blockers": sorted(set(blockers)),
            "status": "revalidation_blocked" if blockers else "no_direct_reference_impact_detected",
            "prior_approval_valid_for_target_generation": False,
            "review_required": True,
            "filing_ready": False,
            "generated_at": _utc_now(),
            "notice": "This analysis detects source-generation changes and reference overlap. It does not determine legal materiality, negative treatment, or current-law effect.",
        }
        return impact

    @staticmethod
    def _render_html(impact: dict[str, Any]) -> str:
        def items(values: Iterable[Any]) -> str:
            return "".join(f"<li>{html.escape(str(value))}</li>" for value in values)
        changes = impact.get("impacted_changes") or []
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(str(row.get('source_id') or ''))}</td>"
            f"<td>{html.escape(str(row.get('change_type') or ''))}</td>"
            f"<td><code>{html.escape(str(((row.get('before') or {}).get('sha256') or '')))}</code></td>"
            f"<td><code>{html.escape(str(((row.get('after') or {}).get('sha256') or '')))}</code></td>"
            "</tr>" for row in changes
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Authority change impact</title>"
            "<style>body{font-family:system-ui;margin:2rem;color:#172b3a}section{border:1px solid #ccd7df;border-radius:10px;padding:1rem;margin:1rem 0}table{border-collapse:collapse;width:100%}th,td{border:1px solid #d8e1e7;padding:.45rem;text-align:left}code{overflow-wrap:anywhere}</style></head><body>"
            f"<h1>{html.escape(str(impact.get('document_title') or 'Authority change impact'))}</h1>"
            f"<p><strong>Revision:</strong> <code>{html.escape(str(impact.get('revision_id') or ''))}</code></p>"
            f"<p><strong>Authority generations:</strong> <code>{html.escape(str(impact.get('base_build_id') or ''))}</code> → <code>{html.escape(str(impact.get('target_build_id') or ''))}</code></p>"
            f"<section><h2>Blockers</h2><ul>{items(impact.get('blockers') or []) or '<li>No direct reference overlap detected; full human revalidation is still required.</li>'}</ul></section>"
            f"<section><h2>Impacted sources</h2><table><tr><th>Source</th><th>Change</th><th>Before hash</th><th>After hash</th></tr>{rows or '<tr><td colspan=4>No directly referenced changed source was detected.</td></tr>'}</table></section>"
            f"<section><h2>Generation diff</h2><pre>{html.escape(json.dumps(impact.get('generation_diff') or {}, indent=2, sort_keys=True))}</pre></section>"
            "<p>This packet is review work product. It does not establish current law or the legal effect of any source change.</p></body></html>"
        )

    def build(self, document_id: str, base_build_id: str, target_build_id: str, *, approved: bool = False) -> dict[str, Any]:
        if approved is not True:
            raise AuthorityImpactError("explicit_authority_revalidation_approval_required", "Explicit approval is required to build an authority revalidation packet.", status_code=409)
        with _LOCK:
            impact = self.analyze_document(document_id, base_build_id, target_build_id)
            stable = dict(impact)
            stable.pop("generated_at", None)
            generation_diff = dict(stable.get("generation_diff") or {})
            generation_diff.pop("generated_at", None)
            stable["generation_diff"] = generation_diff
            build_id = _sha(stable)[:24]
            impact["build_id"] = build_id
            impact.pop("impact_sha256", None)
            impact["impact_sha256"] = _sha(impact)
            build_dir = self.builds / build_id
            if build_dir.exists():
                verification = self.verify(build_id)
                if verification.get("status") != "pass":
                    raise AuthorityImpactError("immutable_authority_impact_collision", "An existing authority-impact packet failed verification.", status_code=409)
                return self.active(build_id)
            staging = self.builds / f".{build_id}.{uuid.uuid4().hex}.staging"
            staging.mkdir(mode=0o700)
            try:
                packet_bytes = json.dumps(impact, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                html_bytes = self._render_html(impact).encode("utf-8")
                receipt = {
                    "schema_version": "authority_change_impact_receipt_v1",
                    "build_id": build_id,
                    "document_id": impact["document_id"],
                    "revision_id": impact["revision_id"],
                    "document_content_sha256": impact["document_content_sha256"],
                    "base_build_id": impact["base_build_id"],
                    "target_build_id": impact["target_build_id"],
                    "impact_sha256": impact["impact_sha256"],
                    "blockers": impact["blockers"],
                    "review_required": True,
                    "generated_at": impact["generated_at"],
                }
                receipt["receipt_sha256"] = _sha(receipt)
                files = {
                    "authority-change-impact.json": packet_bytes,
                    "authority-change-impact.html": html_bytes,
                    "authority-change-impact-receipt.json": json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8"),
                }
                artifact_rows = []
                for name, raw in files.items():
                    _atomic_write(staging / name, raw)
                    artifact_rows.append({"name": name, "sha256": _sha(raw), "size_bytes": len(raw)})
                manifest = {"schema_version": "authority_change_impact_manifest_v1", "build_id": build_id, "artifacts": sorted(artifact_rows, key=lambda row: row["name"])}
                manifest["manifest_sha256"] = _sha(manifest)
                _atomic_write(staging / "artifact-manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
                os.replace(staging, build_dir)
                _atomic_write(self.active_pointer, json.dumps({"build_id": build_id, "document_id": impact["document_id"], "revision_id": impact["revision_id"], "manifest_sha256": manifest["manifest_sha256"], "activated_at": _utc_now()}, indent=2, sort_keys=True).encode("utf-8"))
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            if self.verify(build_id).get("status") != "pass":
                raise AuthorityImpactError("authority_impact_self_verification_failed", "The authority-impact packet failed self-verification.", status_code=409)
            return self.active(build_id)

    def verify(self, build_id: str) -> dict[str, Any]:
        build_id = _validate_build_id(build_id)
        build_dir = self.builds / build_id
        try:
            resolved = build_dir.resolve(strict=True)
            root = self.builds.resolve(strict=True)
        except OSError:
            return {"status": "blocked", "build_id": build_id, "blockers": ["authority_impact_build_unavailable"]}
        blockers: list[str] = []
        if root not in resolved.parents or resolved.is_symlink():
            blockers.append("authority_impact_build_path_invalid")
            return {"status": "blocked", "build_id": build_id, "blockers": blockers}
        try:
            manifest = _read_json(build_dir / "artifact-manifest.json")
        except AuthorityImpactError:
            return {"status": "blocked", "build_id": build_id, "blockers": ["authority_impact_manifest_invalid"]}
        stored_manifest_hash = str(manifest.get("manifest_sha256") or "")
        check = dict(manifest)
        check.pop("manifest_sha256", None)
        if not _SHA_RE.fullmatch(stored_manifest_hash) or not hmac.compare_digest(stored_manifest_hash, _sha(check)):
            blockers.append("authority_impact_manifest_hash_mismatch")
        expected = {"authority-change-impact.json", "authority-change-impact.html", "authority-change-impact-receipt.json"}
        rows = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
        names = {str(row.get("name") or "") for row in rows if isinstance(row, dict)}
        if names != expected:
            blockers.append("authority_impact_manifest_artifact_set_invalid")
        for row in rows:
            if not isinstance(row, dict):
                blockers.append("authority_impact_manifest_row_invalid")
                continue
            name = Path(str(row.get("name") or "")).name
            path = build_dir / name
            if not path.is_file() or path.is_symlink():
                blockers.append(f"authority_impact_artifact_unavailable:{name}")
                continue
            raw = path.read_bytes()
            if len(raw) != int(row.get("size_bytes") or -1) or _sha(raw) != str(row.get("sha256") or ""):
                blockers.append(f"authority_impact_artifact_hash_mismatch:{name}")
        if not blockers:
            packet = _read_json(build_dir / "authority-change-impact.json")
            stored = str(packet.get("impact_sha256") or "")
            check = dict(packet)
            check.pop("impact_sha256", None)
            if not _SHA_RE.fullmatch(stored) or not hmac.compare_digest(stored, _sha(check)):
                blockers.append("authority_impact_packet_hash_mismatch")
        return {"status": "pass" if not blockers else "blocked", "build_id": build_id, "blockers": sorted(set(blockers)), "review_required": True}

    def active(self, build_id: str = "", *, document_id: str = "") -> dict[str, Any]:
        if not build_id:
            pointer = _read_json(self.active_pointer)
            build_id = str(pointer.get("build_id") or "")
            if document_id and str(pointer.get("document_id") or "") != str(document_id):
                raise AuthorityImpactError("authority_impact_active_document_mismatch", "The active authority-impact packet belongs to another document.", status_code=404)
        build_id = _validate_build_id(build_id)
        verification = self.verify(build_id)
        if verification["status"] != "pass":
            raise AuthorityImpactError("authority_impact_build_unverified", "The authority-impact packet failed verification.", status_code=409)
        build_dir = self.builds / build_id
        packet = _read_json(build_dir / "authority-change-impact.json")
        try:
            document = get_document(self.case_root, str(packet.get("document_id") or ""))
        except Exception as exc:
            raise AuthorityImpactError(
                "authority_impact_document_unavailable",
                "The document bound to this authority-impact packet is unavailable.",
                status_code=409,
            ) from exc
        if (
            str(document.get("current_revision_id") or "") != str(packet.get("revision_id") or "")
            or str(document.get("content_sha256") or "") != str(packet.get("document_content_sha256") or "")
        ):
            raise AuthorityImpactError(
                "authority_impact_stale_after_document_change",
                "The authority-impact packet is stale because the document changed.",
                status_code=409,
            )
        media = {
            "authority-change-impact.json": "application/json",
            "authority-change-impact.html": "text/html",
            "authority-change-impact-receipt.json": "application/json",
        }
        artifacts = []
        for name, media_type in media.items():
            raw = (build_dir / name).read_bytes()
            artifacts.append({"name": name, "sha256": _sha(raw), "size_bytes": len(raw), "media_type": media_type})
        return {"status": "pass", "build_id": build_id, "packet": packet, "artifacts": artifacts, "verification": verification, "review_required": True}

    def resolve_artifact(self, build_id: str, filename: str) -> tuple[Path, str]:
        allowed = {
            "authority-change-impact.json": "application/json",
            "authority-change-impact.html": "text/html",
            "authority-change-impact-receipt.json": "application/json",
        }
        name = Path(str(filename or "")).name
        if name not in allowed:
            raise AuthorityImpactError("authority_impact_artifact_not_allowed", "The authority-impact artifact is not allowed.", status_code=404)
        if self.verify(build_id).get("status") != "pass":
            raise AuthorityImpactError("authority_impact_artifact_build_unverified", "The authority-impact packet failed verification.", status_code=409)
        packet = _read_json(self.builds / _validate_build_id(build_id) / "authority-change-impact.json")
        try:
            document = get_document(self.case_root, str(packet.get("document_id") or ""))
        except Exception as exc:
            raise AuthorityImpactError(
                "authority_impact_document_unavailable",
                "The document bound to this authority-impact packet is unavailable.",
                status_code=409,
            ) from exc
        if (
            str(document.get("current_revision_id") or "") != str(packet.get("revision_id") or "")
            or str(document.get("content_sha256") or "") != str(packet.get("document_content_sha256") or "")
        ):
            raise AuthorityImpactError(
                "authority_impact_stale_after_document_change",
                "The authority-impact packet is stale because the document changed.",
                status_code=409,
            )
        path = self.builds / _validate_build_id(build_id) / name
        if not path.is_file() or path.is_symlink():
            raise AuthorityImpactError("authority_impact_artifact_unavailable", "The authority-impact artifact is unavailable.", status_code=404)
        return path, allowed[name]

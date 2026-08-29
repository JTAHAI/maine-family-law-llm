"""Fail-closed validation for Store listing assets and accepted release scope."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_PNG = b"\x89PNG\r\n\x1a\n"
_MAX_IMAGE_BYTES = 50 * 1024 * 1024
_CAPTION = re.compile(r"^\|\s*`(?P<file>[^`]+)`\s*\|\s*(?P<caption>.+?)\s*\|\s*$")
_BANNED_CLAIMS = re.compile(r"\b(?:enterprise\s+ga\s+ready|store\s+certified|attorney[-\s]?approved|automated\s+filing|guaranteed\s+outcome)\b", re.IGNORECASE)
_PRIVATE_MARKERS = re.compile(r"(?:\bssn\b|social security number|\b\d{3}-\d{2}-\d{4}\b|c:\\users\\|/users/)", re.IGNORECASE)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_metadata(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()[:33]
    if len(raw) < 33 or raw[:8] != _PNG or raw[12:16] != b"IHDR":
        raise ValueError("png_encoding_invalid")
    width, height = struct.unpack(">II", raw[16:24])
    return {"encoding": "PNG", "width": width, "height": height, "landscape": width > height, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _captions(path: Path) -> dict[str, str]:
    captions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _CAPTION.match(line)
        if match and match.group("file") != "File":
            captions[match.group("file")] = match.group("caption")
    return captions


def validate_store_assets(*, submission_root: str | Path, listing_root: str | Path, release_scope_path: str | Path) -> dict[str, Any]:
    submission = Path(submission_root).resolve()
    listing = Path(listing_root).resolve()
    scope_path = Path(release_scope_path).resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    screenshots = submission / "screenshots"
    manifest_path = screenshots / "MANIFEST.json"
    captions_path = screenshots / "CAPTIONS.md"
    scope: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    try:
        scope = json.loads(scope_path.read_text(encoding="utf-8"))
    except Exception:
        blockers.append("release_scope_unreadable")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        blockers.append("screenshot_manifest_unreadable")
    try:
        captions = _captions(captions_path)
    except Exception:
        captions = {}; blockers.append("screenshot_captions_unreadable")
    image_results: list[dict[str, Any]] = []
    screenshot_rows = manifest.get("screenshots") if isinstance(manifest, dict) else []
    if not isinstance(screenshot_rows, list) or not screenshot_rows:
        blockers.append("screenshots_missing")
        screenshot_rows = []
    for row in screenshot_rows:
        file_name = str(row.get("file") or "") if isinstance(row, dict) else ""
        image = screenshots / file_name
        result: dict[str, Any] = {"file": file_name, "status": "pass"}
        try:
            metadata = _png_metadata(image)
            result.update(metadata)
            if metadata["size_bytes"] > _MAX_IMAGE_BYTES:
                result["status"] = "blocked"; blockers.append(f"screenshot_size:{file_name}")
            if not metadata["landscape"] or metadata["width"] < 1366 or metadata["height"] < 768:
                result["status"] = "blocked"; blockers.append(f"screenshot_dimensions:{file_name}")
            if str(row.get("sha256") or "") != metadata["sha256"]:
                result["status"] = "blocked"; blockers.append(f"screenshot_hash:{file_name}")
            caption = captions.get(file_name, "")
            result["caption_length"] = len(caption)
            if not caption or len(caption) >= 200:
                result["status"] = "blocked"; blockers.append(f"screenshot_caption:{file_name}")
        except Exception as exc:  # noqa: BLE001
            result["status"] = "blocked"; result["error"] = str(exc); blockers.append(f"screenshot_invalid:{file_name}")
        image_results.append(result)
    if set(captions) != {str(row.get("file") or "") for row in screenshot_rows if isinstance(row, dict)}:
        blockers.append("screenshot_caption_manifest_mismatch")
    files = [path for path in listing.glob("*") if path.is_file()]
    listing_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)
    claims = sorted({match.group(0) for match in _BANNED_CLAIMS.finditer(listing_text)})
    if claims:
        blockers.append("listing_unsubstantiated_claim")
    private_markers = sorted({match.group(0) for match in _PRIVATE_MARKERS.finditer(listing_text)})
    if private_markers:
        blockers.append("listing_private_marker")
    privacy_ok = (listing / "support-information.md").is_file() and "PRIVACY_POLICY_MICROSOFT_STORE.html" in (listing / "support-information.md").read_text(encoding="utf-8")
    if not privacy_ok:
        blockers.append("privacy_link_missing")
    accepted = list(scope.get("public_addon_features") or []) if isinstance(scope, dict) else []
    if not accepted:
        blockers.append("accepted_release_scope_missing")
    if not bool((scope.get("release_boundaries") or {}).get("review_required")):
        blockers.append("review_required_boundary_missing")
    archive = submission / "MaineFamilyLawLLM_v8.0.0_Store_Screenshots.zip"
    archive_status = "not_present"
    if archive.is_file():
        try:
            with zipfile.ZipFile(archive, "r") as zip_file:
                names = set(zip_file.namelist())
            expected = {str(row["file"]) for row in screenshot_rows if isinstance(row, dict)} | {"MANIFEST.json", "CAPTIONS.md"}
            archive_status = "pass" if expected.issubset(names) else "blocked"
            if archive_status == "blocked": blockers.append("screenshot_archive_incomplete")
        except Exception:
            archive_status = "blocked"; blockers.append("screenshot_archive_invalid")
    else:
        warnings.append("screenshot_archive_not_present")
    return {
        "schema_version": "store_asset_validation_v1",
        "generated_at": _now(),
        "status": "pass" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "screenshot_validation": image_results,
        "screenshot_archive": {"status": archive_status, "file_name": archive.name},
        "listing": {"file_count": len(files), "privacy_link_present": privacy_ok, "unsubstantiated_claims": claims, "private_markers": private_markers},
        "accepted_release_scope": {"feature_count": len(accepted), "feature_ids": accepted, "review_required": bool((scope.get("release_boundaries") or {}).get("review_required")), "local_only": bool((scope.get("release_boundaries") or {}).get("local_only"))},
        "review_required": True,
        "store_release_blocked": bool(blockers),
    }


__all__ = ["validate_store_assets"]

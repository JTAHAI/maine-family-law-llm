"""Exact MSIX size accounting and offline tier-policy validation."""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_GROUPS = (
    ("docling_models", "store/docling/models/"),
    ("whisper", "store/whisper/"),
    ("tesseract", "store/tesseract/"),
    ("spacy_model", "_internal/en_core_web_lg/"),
    ("torch", "_internal/torch/"),
    ("opencv", "_internal/cv2/"),
    ("rapidocr", "_internal/rapidocr/"),
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _group(path: str) -> str:
    normalized = path.replace("\\", "/")
    for group, prefix in _GROUPS:
        if normalized.startswith(prefix):
            return group
    return "other_internal" if normalized.startswith("_internal/") else "app_and_assets"


def analyze_msix_package(*, package: str | Path, tier_config: str | Path, requested_tier: str) -> dict[str, Any]:
    package_path = Path(package).resolve(); config_path = Path(tier_config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    tiers = config.get("tiers") if isinstance(config, dict) else None
    if not package_path.is_file() or not isinstance(tiers, dict) or requested_tier not in tiers:
        return {"schema_version": "msix_package_size_budget_v1", "status": "blocked", "blockers": ["package_or_tier_config_invalid"], "review_required": True}
    tier = tiers[requested_tier]
    totals: dict[str, int] = {}
    entries: list[tuple[str, int]] = []
    try:
        with zipfile.ZipFile(package_path, "r") as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                group = _group(entry.filename)
                totals[group] = totals.get(group, 0) + entry.file_size
                entries.append((entry.filename.replace("\\", "/"), entry.file_size))
    except Exception:
        return {"schema_version": "msix_package_size_budget_v1", "status": "blocked", "blockers": ["msix_archive_unreadable"], "review_required": True}
    uncompressed = sum(totals.values())
    blockers: list[str] = []
    if package_path.stat().st_size > int(tier.get("maximum_package_bytes") or 0):
        blockers.append("compressed_package_budget_exceeded")
    names = {name for name, _size in entries}
    for prefix in tier.get("required_archive_prefixes") or []:
        if not any(name.startswith(str(prefix)) for name in names):
            blockers.append(f"required_tier_payload_missing:{prefix}")
    for prefix in tier.get("excluded_archive_prefixes") or []:
        if any(name.startswith(str(prefix)) for name in names):
            blockers.append(f"excluded_tier_payload_present:{prefix}")
    policy = config.get("policy") if isinstance(config, dict) else {}
    if not isinstance(policy, dict) or policy.get("runtime_downloads_allowed") is not False or policy.get("tier_change_requires_new_signed_package") is not True:
        blockers.append("offline_tier_policy_invalid")
    largest = [{"path": name, "size_bytes": size} for name, size in sorted(entries, key=lambda row: (-row[1], row[0]))[:25]]
    optional_bytes = sum(totals.get(key, 0) for key in ("docling_models", "spacy_model", "torch", "opencv", "rapidocr"))
    return {
        "schema_version": "msix_package_size_budget_v1",
        "generated_at": _now(),
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "package": {"file_name": package_path.name, "sha256": _sha256(package_path), "compressed_size_bytes": package_path.stat().st_size, "uncompressed_size_bytes": uncompressed},
        "tier": {"requested": requested_tier, "definition": tier, "runtime_downloads_allowed": policy.get("runtime_downloads_allowed"), "tier_change_requires_new_signed_package": policy.get("tier_change_requires_new_signed_package")},
        "size_groups": [{"group": name, "size_bytes": size} for name, size in sorted(totals.items(), key=lambda row: (-row[1], row[0]))],
        "largest_entries": largest,
        "optimization": {"optional_full_intelligence_payload_bytes": optional_bytes, "essential_edition_available_only_as_separate_build": True, "runtime_feature_download_or_side_load": False, "recommendation": "Build and qualify the essential tier separately; never remove payloads or download models from an installed package."},
        "review_required": True,
    }


__all__ = ["analyze_msix_package"]

"""Fail-closed release catalog for ordinary-user optional local AI setup.

The catalog is intentionally an allowlist rather than a model search feature.
An empty catalog is a valid, truthful shipping state: it means no model bytes,
engine, license, or task claim can be offered for installation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from legal.security.strict_json import StrictJSONError, strict_json_load_path


_PROFILE_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_MODEL_CLASS = frozenset({"reasoning_4b", "reasoning_8b"})
_REQUIRED_TOP_LEVEL = {
    "schema_version",
    "catalog_revision",
    "publication_status",
    "network_refresh_enabled",
    "review_required",
    "profiles",
}


class LocalAiCatalogError(ValueError):
    def __init__(self, code: str, status_code: int = 409):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "local_ai_catalog.json"


class LocalAiCatalog:
    """Read one bundled catalog without network refresh or implicit trust setup."""

    schema = "mfl_local_ai_catalog_v1"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or default_catalog_path()).resolve(strict=False)

    def _document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": self.schema,
                "catalog_revision": 0,
                "publication_status": "unavailable",
                "network_refresh_enabled": False,
                "review_required": True,
                "profiles": [],
            }
        try:
            value = strict_json_load_path(self.path, max_bytes=256 * 1024, max_depth=16, max_items=4_000, require_object=True)
        except StrictJSONError as exc:
            raise LocalAiCatalogError("local_ai_catalog_unavailable") from exc
        if set(value) != _REQUIRED_TOP_LEVEL or value.get("schema_version") != self.schema:
            raise LocalAiCatalogError("local_ai_catalog_invalid")
        if (
            type(value.get("catalog_revision")) is not int
            or value["catalog_revision"] < 0
            or value.get("publication_status") not in {"unconfigured", "released", "unavailable"}
            or value.get("network_refresh_enabled") is not False
            or value.get("review_required") is not True
            or not isinstance(value.get("profiles"), list)
            or len(value["profiles"]) > 24
        ):
            raise LocalAiCatalogError("local_ai_catalog_invalid")
        return value

    @staticmethod
    def _safe_profile(profile: Any) -> dict[str, Any] | None:
        """Expose only profiles that already carry every release prerequisite.

        The actual signature and bytes must later be rechecked by the installer;
        this preflight prevents an incomplete draft declaration from becoming a
        public card in the meantime.
        """
        if not isinstance(profile, dict):
            return None
        allowed = {
            "profile_id", "display_name", "engine_id", "artifact_sha256", "artifact_bytes",
            "license_notice_id", "task_capabilities", "quality_evidence_id", "admission_status",
            "resource_profiles", "review_required", "download_origin_ids", "model_class",
        }
        if set(profile) != allowed:
            return None
        profile_id = profile.get("profile_id")
        if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
            return None
        if (
            not isinstance(profile.get("display_name"), str)
            or not 1 <= len(profile["display_name"]) <= 100
            or not isinstance(profile.get("engine_id"), str)
            or not _PROFILE_ID.fullmatch(profile["engine_id"])
            or not isinstance(profile.get("artifact_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", profile["artifact_sha256"])
            or type(profile.get("artifact_bytes")) is not int
            or not 1 <= profile["artifact_bytes"] <= 25 * 1024**3
            or not isinstance(profile.get("license_notice_id"), str)
            or not _PROFILE_ID.fullmatch(profile["license_notice_id"])
            or not isinstance(profile.get("task_capabilities"), list)
            or not profile["task_capabilities"]
            or len(profile["task_capabilities"]) > 12
            or not all(isinstance(item, str) and _PROFILE_ID.fullmatch(item) for item in profile["task_capabilities"])
            or not isinstance(profile.get("quality_evidence_id"), str)
            or not _PROFILE_ID.fullmatch(profile["quality_evidence_id"])
            or profile.get("admission_status") != "production_admitted"
            or not isinstance(profile.get("resource_profiles"), list)
            or not profile["resource_profiles"]
            or profile.get("review_required") is not True
            or not isinstance(profile.get("download_origin_ids"), list)
            or not profile["download_origin_ids"]
            or not all(isinstance(item, str) and _PROFILE_ID.fullmatch(item) for item in profile["download_origin_ids"])
            or profile.get("model_class") not in _MODEL_CLASS
        ):
            return None
        resource_profiles = [LocalAiCatalog._safe_resource_profile(item) for item in profile["resource_profiles"]]
        if not all(resource_profiles):
            return None
        return {
            "profile_id": profile_id,
            "display_name": profile["display_name"],
            "engine_id": profile["engine_id"],
            "artifact_sha256": profile["artifact_sha256"],
            "artifact_bytes": profile["artifact_bytes"],
            "license_notice_id": profile["license_notice_id"],
            "task_capabilities": list(profile["task_capabilities"]),
            "quality_evidence_id": profile["quality_evidence_id"],
            "admission_status": profile["admission_status"],
            "resource_profiles": resource_profiles,
            "review_required": True,
            "download_origin_ids": list(profile["download_origin_ids"]),
            "model_class": profile["model_class"],
        }

    @staticmethod
    def _safe_resource_profile(value: Any) -> dict[str, Any] | None:
        """Validate a measured runtime requirement without claiming fit.

        A model card, total installed RAM, or GPU name alone cannot safely make
        a device recommendation.  Catalog authors must bind a profile to one
        tested backend/context configuration and its measured peak/reservation.
        """
        if not isinstance(value, dict):
            return None
        allowed = {
            "resource_profile_id", "backend", "context_tokens", "min_available_memory_bytes",
            "min_disk_free_bytes", "estimated_peak_memory_bytes", "expected_download_bytes",
            "expected_installed_bytes", "temporary_install_bytes", "hardware_baseline",
        }
        if set(value) != allowed:
            return None
        resource_id = value.get("resource_profile_id")
        backend = value.get("backend")
        integer_keys = (
            "context_tokens", "min_available_memory_bytes", "min_disk_free_bytes",
            "estimated_peak_memory_bytes", "expected_download_bytes", "expected_installed_bytes",
            "temporary_install_bytes",
        )
        if (
            not isinstance(resource_id, str)
            or not _PROFILE_ID.fullmatch(resource_id)
            or not isinstance(backend, str)
            or not _PROFILE_ID.fullmatch(backend)
            or not isinstance(value.get("hardware_baseline"), str)
            or not 1 <= len(value["hardware_baseline"]) <= 240
            or any(type(value.get(key)) is not int or value[key] < 1 for key in integer_keys)
            or value["context_tokens"] > 32768
            or value["expected_download_bytes"] > 25 * 1024**3
            or value["expected_installed_bytes"] > 25 * 1024**3
            or value["temporary_install_bytes"] > 25 * 1024**3
            or value["estimated_peak_memory_bytes"] < value["min_available_memory_bytes"]
        ):
            return None
        return {key: value[key] for key in allowed}

    @staticmethod
    def assess(profile: dict[str, Any], hardware: dict[str, Any]) -> dict[str, Any]:
        """Return the safest fitting measured configuration, or explicit blockers.

        This assessment performs no model probe, process launch, download, or
        external request.  Available RAM and free storage are rechecked again
        by the installer and runner; this is deliberately advisory only.
        """
        available_memory = max(0, int(hardware.get("available_memory_bytes") or 0))
        disk_free = max(0, int(hardware.get("disk_free_bytes") or 0))
        options: list[dict[str, Any]] = []
        for resource in profile["resource_profiles"]:
            required_disk = max(
                resource["min_disk_free_bytes"],
                resource["expected_download_bytes"] + resource["temporary_install_bytes"],
            )
            blockers: list[str] = []
            if not available_memory:
                blockers.append("available_memory_unverified")
            elif available_memory < resource["min_available_memory_bytes"]:
                blockers.append("insufficient_available_memory")
            if not disk_free:
                blockers.append("available_disk_unverified")
            elif disk_free < required_disk:
                blockers.append("insufficient_available_disk")
            options.append({
                **resource,
                "required_disk_bytes": required_disk,
                "eligible": not blockers,
                "blockers": blockers,
            })
        eligible = [item for item in options if item["eligible"]]
        selected = min(eligible, key=lambda item: (item["estimated_peak_memory_bytes"], item["required_disk_bytes"])) if eligible else None
        return {
            "schema_version": "local_ai_profile_assessment_v1",
            "profile_id": profile["profile_id"],
            "model_class": profile["model_class"],
            "status": "eligible_for_install_review" if selected else "hardware_or_storage_review_required",
            "selected_resource_profile": selected,
            "resource_options": options,
            "review_required": True,
            "network_used": False,
            "basis": "local_available_memory_and_disk_snapshot",
        }

    def status(self) -> dict[str, Any]:
        document = self._document()
        published = [self._safe_profile(item) for item in document["profiles"]]
        profiles = [item for item in published if item is not None]
        rejected = len(document["profiles"]) - len(profiles)
        status = "catalog_ready" if document["publication_status"] == "released" and profiles else "no_installable_model_catalog"
        return {
            "schema_version": "local_ai_catalog_status_v1",
            "status": status,
            "catalog_revision": document["catalog_revision"],
            "profile_count": len(profiles),
            "profiles": profiles,
            "rejected_profile_count": rejected,
            "catalog_refresh_supported": False,
            "network_used": False,
            "review_required": True,
            "blockers": ([] if status == "catalog_ready" else ["production_admitted_model_catalog_unavailable"]),
        }

    def profile(self, profile_id: str) -> dict[str, Any]:
        clean_id = str(profile_id or "").strip().casefold()
        if not _PROFILE_ID.fullmatch(clean_id):
            raise LocalAiCatalogError("local_ai_profile_invalid", 400)
        for profile in self.status()["profiles"]:
            if profile["profile_id"] == clean_id:
                return profile
        raise LocalAiCatalogError("local_ai_profile_unavailable", 404)

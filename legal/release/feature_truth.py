"""Canonical, conservative release-feature truth for the shipped workbench.

Reachability is useful for support and migration, but it is not Store eligibility.
This module keeps the two facts separate until a current source snapshot, frozen
runtime, and exact package have all been qualified.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

from legal.security.strict_json import StrictJSONError, strict_json_load_path


class FeatureTruthError(ValueError):
    """Raised when the source-controlled release ledger is malformed."""


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def default_manifest_path() -> Path:
    return _repo_root() / "configs" / "release_feature_truth.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise FeatureTruthError(f"feature_truth_{field}_invalid")
    if len(set(value)) != len(value):
        raise FeatureTruthError(f"feature_truth_{field}_duplicates")
    return list(value)


def load_feature_truth(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the source-controlled truth ledger without guessing."""

    manifest_path = Path(path).resolve() if path else default_manifest_path()
    try:
        payload = strict_json_load_path(manifest_path, max_bytes=256 * 1024, require_object=True)
    except (OSError, UnicodeError, StrictJSONError) as exc:
        raise FeatureTruthError("feature_truth_manifest_unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != "release_feature_truth_v1":
        raise FeatureTruthError("feature_truth_schema_invalid")
    release = payload.get("release")
    evidence = payload.get("evidence")
    if not isinstance(release, dict) or not isinstance(evidence, dict):
        raise FeatureTruthError("feature_truth_release_or_evidence_invalid")
    if release.get("review_required") is not True or release.get("local_only") is not True:
        raise FeatureTruthError("feature_truth_safety_flags_invalid")
    for name in ("msix", "full_regression", "frozen_runtime"):
        if not isinstance(evidence.get(name), dict):
            raise FeatureTruthError("feature_truth_evidence_record_invalid")
    for name, flag in (
        ("full_regression", "current_tree_bound"),
        ("frozen_runtime", "current_package_bound"),
    ):
        if type(evidence[name].get(flag)) is not bool:
            raise FeatureTruthError("feature_truth_evidence_boolean_invalid")
    blockers = _require_string_list(payload.get("release_blockers"), "release_blockers")
    if not isinstance(payload.get("feature_status"), str) or not payload["feature_status"]:
        raise FeatureTruthError("feature_truth_feature_status_invalid")
    if release.get("status") not in {
        "pending_current_package_verification",
        "qualified_current_package",
        "blocked",
    }:
        raise FeatureTruthError("feature_truth_release_status_invalid")
    legacy = _require_string_list(
        payload.get("legacy_reachable_feature_ids"), "legacy_reachable_feature_ids"
    )
    store = _require_string_list(
        payload.get("current_store_claim_feature_ids"), "current_store_claim_feature_ids"
    )
    if not set(store).issubset(legacy):
        raise FeatureTruthError("feature_truth_store_features_not_reachable")
    unavailable = payload.get("unavailable_features")
    if not isinstance(unavailable, list) or not all(
        isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and row.get("status") in {"blocked", "disabled", "hidden"}
        and isinstance(row.get("reason"), str)
        and row["reason"]
        for row in unavailable
    ):
        raise FeatureTruthError("feature_truth_unavailable_features_invalid")
    _require_string_list(payload.get("required_feature_evidence"), "required_feature_evidence")
    package_hash = str((evidence.get("msix") or {}).get("current_package_sha256") or "")
    is_current = bool((evidence.get("full_regression") or {}).get("current_tree_bound"))
    package_bound = bool((evidence.get("frozen_runtime") or {}).get("current_package_bound"))
    if store and (
        not re.fullmatch(r"[a-f0-9]{64}", package_hash)
        or not is_current
        or not package_bound
        or release.get("status") != "qualified_current_package"
        or blockers
        or any(
            evidence[name].get("status") != "pass"
            for name in ("msix", "full_regression", "frozen_runtime")
        )
    ):
        raise FeatureTruthError("feature_truth_store_claim_without_current_package_evidence")
    return payload


def feature_truth_inventory(path: str | Path | None = None) -> dict[str, Any]:
    """Return public-safe release status without turning route counts into claims."""

    manifest_path = Path(path).resolve() if path else default_manifest_path()
    payload = load_feature_truth(manifest_path)
    release = dict(payload["release"])
    evidence = dict(payload["evidence"])
    store_features = list(payload["current_store_claim_feature_ids"])
    package_hash = str((evidence.get("msix") or {}).get("current_package_sha256") or "")
    current_source = bool((evidence.get("full_regression") or {}).get("current_tree_bound"))
    package_bound = bool((evidence.get("frozen_runtime") or {}).get("current_package_bound"))
    store_eligible = bool(
        store_features
        and package_hash
        and current_source
        and package_bound
        and release.get("status") == "qualified_current_package"
    )
    evidence_requirements = list(payload["required_feature_evidence"])
    feature_records = [
        {
            "feature_id": feature_id,
            "source_reachable": True,
            "release_claim_status": (
                "eligible_for_current_store_claim"
                if store_eligible and feature_id in store_features
                else "pending_current_package_verification"
            ),
            "required_evidence": evidence_requirements,
            "review_required": bool(release.get("review_required")),
        }
        for feature_id in payload["legacy_reachable_feature_ids"]
    ]
    return {
        "schema_version": "runtime_feature_truth_inventory_v1",
        "manifest_path": "configs/release_feature_truth.json",
        "manifest_sha256": _sha256(manifest_path),
        "release": release,
        "evidence": evidence,
        "legacy_reachable_feature_ids": list(payload["legacy_reachable_feature_ids"]),
        "store_claim_feature_ids": store_features if store_eligible else [],
        "store_feature_claim_eligible": store_eligible,
        "feature_status": str(payload["feature_status"]),
        "features": feature_records,
        "unavailable_features": list(payload["unavailable_features"]),
        "release_blockers": list(payload["release_blockers"]),
        "review_required": bool(release.get("review_required")),
    }


__all__ = [
    "FeatureTruthError",
    "default_manifest_path",
    "feature_truth_inventory",
    "load_feature_truth",
]

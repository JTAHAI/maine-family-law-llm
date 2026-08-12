"""Truthful runtime feature-tier and optional-pack reporting."""

from __future__ import annotations

import importlib.util
import os
from typing import Any

PACKS = {
    "core": ("fastapi", "pypdf", "cryptography"),
    "document_intelligence": ("docling", "presidio_analyzer", "spacy"),
    "advanced_retrieval": ("sqlite_vec", "qdrant_client"),
}


def feature_tier_status() -> dict[str, Any]:
    configured = str(os.environ.get("MFL_STORE_FEATURE_TIER") or "development").strip().lower()
    packs: dict[str, dict[str, Any]] = {}
    for name, modules in PACKS.items():
        availability = {module: importlib.util.find_spec(module) is not None for module in modules}
        packs[name] = {
            "status": "available" if all(availability.values()) else "not_installed",
            "modules": availability,
            "required_for_core_workflows": name == "core",
        }
    blockers = [
        f"required_pack_unavailable:{name}"
        for name, value in packs.items()
        if value["required_for_core_workflows"] and value["status"] != "available"
    ]
    return {
        "schema_version": "local_feature_tier_status_v1",
        "status": "pass" if not blockers else "blocked",
        "configured_tier": configured,
        "packs": packs,
        "core_workflows_available": not blockers,
        "optional_features_degrade_gracefully": True,
        "default_store_tier": "essential",
        "blockers": blockers,
        "review_required": False,
    }


__all__ = ["PACKS", "feature_tier_status"]

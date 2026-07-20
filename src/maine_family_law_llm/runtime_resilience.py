"""Privacy-safe local runtime readiness checks.

The health snapshot verifies package-internal invariants without returning local
paths, private matter metadata, or raw exception text. It is a runtime integrity
check, not a claim of legal-currentness or production GA readiness.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import tomllib
from typing import Any

from .focaf_library import audit_packaged_printables
from .sources import load_seed_manifest
from .version import PACKAGE_VERSION, VERSION


@lru_cache(maxsize=1)
def runtime_health_snapshot() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    checks: list[dict[str, Any]] = []

    version_values: dict[str, str] = {"runtime": PACKAGE_VERSION}
    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version_values["pyproject"] = f"{pyproject['project']['version']}.0"
    except Exception:
        version_values["pyproject"] = "unreadable"
    for name in ("identity.example.json", "identity.local.json"):
        try:
            payload = json.loads((root / "store" / "msix" / name).read_text(encoding="utf-8"))
            version_values[name] = str(payload.get("package_version") or "")
        except Exception:
            version_values[name] = "unreadable"
    version_ok = all(value == PACKAGE_VERSION for value in version_values.values())
    checks.append(
        {
            "component": "version_alignment",
            "status": "pass" if version_ok else "fail",
            "details": {
                "product_version": VERSION,
                "package_version": PACKAGE_VERSION,
                "all_package_versions_match": version_ok,
            },
        }
    )

    ui_files = (
        root / "src" / "maine_family_law_llm" / "ui" / "workbench.html",
        root / "src" / "maine_family_law_llm" / "ui" / "workbench.js",
        root / "src" / "maine_family_law_llm" / "ui" / "workbench.css",
    )
    ui_ok = all(path.is_file() and path.stat().st_size > 0 for path in ui_files)
    checks.append(
        {
            "component": "local_ui_assets",
            "status": "pass" if ui_ok else "fail",
            "details": {"required_asset_count": len(ui_files), "available_asset_count": sum(path.is_file() for path in ui_files)},
        }
    )

    try:
        sources = load_seed_manifest()
        source_ids = [str(entry.id) for entry in sources]
        source_ok = bool(source_ids) and len(source_ids) == len(set(source_ids))
        source_details = {
            "source_count": len(source_ids),
            "unique_source_ids": len(set(source_ids)),
            "live_currentness_certified": False,
        }
    except Exception:
        source_ok = False
        source_details = {"source_count": 0, "unique_source_ids": 0, "live_currentness_certified": False}
    checks.append(
        {
            "component": "bundled_source_registry",
            "status": "pass" if source_ok else "fail",
            "details": source_details,
        }
    )

    try:
        focaf = audit_packaged_printables(verify_hashes=True)
        focaf_ok = focaf.get("status") == "pass"
        focaf_details = {
            "expected": int(focaf.get("expected") or 0),
            "resolved": int(focaf.get("resolved") or 0),
            "missing_count": len(focaf.get("missing") or []),
            "hash_mismatch_count": len(focaf.get("hash_mismatches") or []),
        }
    except Exception:
        focaf_ok = False
        focaf_details = {"expected": 0, "resolved": 0, "missing_count": 0, "hash_mismatch_count": 0}
    checks.append(
        {
            "component": "bundled_focaf_assets",
            "status": "pass" if focaf_ok else "fail",
            "details": focaf_details,
        }
    )

    blockers = [check["component"] for check in checks if check["status"] != "pass"]
    return {
        "schema_version": "runtime_health_v2",
        "status": "ok" if not blockers else "degraded",
        "mode": "local-workbench",
        "version": VERSION,
        "package_version": PACKAGE_VERSION,
        "checks": checks,
        "blockers": blockers,
        "private_paths_included": False,
        "private_matter_state_included": False,
        "network_used": False,
        "legal_currentness_certified": False,
        "review_required": True,
    }


def clear_runtime_health_cache() -> None:
    runtime_health_snapshot.cache_clear()

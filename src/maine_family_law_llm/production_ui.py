"""Inventory and integrity checks for the one shipped workbench frontend."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from .local_workbench_ui import ui_asset_root

# The existing HTML/CSS/JS entrypoint names stay stable for frozen builds.
# The dependency-free component module is loaded by workbench.html before the
# controller and is included explicitly in the production asset inventory.
PRODUCTION_ASSETS = ("workbench.html", "workbench.css", "workbench_components.js", "workbench.js")
EXPERIMENTAL_HIDDEN_WORKSPACE_IDS: frozenset[str] = frozenset()
EXPERIMENTAL_HIDDEN_API_PREFIXES: tuple[str, ...] = ()
REQUIRED_CONTRACTS = {
    "skip_navigation": ("workbench.html", 'class="skip-link"'),
    "live_status": ("workbench.html", "aria-live="),
    "keyboard_focus": ("workbench.css", ":focus-visible"),
    "reduced_motion": ("workbench.css", "prefers-reduced-motion"),
    "responsive_layout": ("workbench.css", "@media"),
    "escape_handling": ("workbench.js", "key === 'Escape'"),
    "request_cancellation": ("workbench.js", "AbortController"),
    "production_identity": ("workbench.html", 'data-production-ui="workbench"'),
}


def _accessibility_audit(contents: dict[str, str]) -> dict[str, Any]:
    """Return a static production-asset accessibility audit.

    This is a repeatable packaging check, not a substitute for testing with a
    screen reader in the frozen desktop application.  It deliberately reports
    only what can be established from the shipped assets.
    """

    markup = contents.get("workbench.html", "")
    stylesheet = contents.get("workbench.css", "")
    javascript = contents.get("workbench.js", "")
    checks = {
        "single_main_landmark": markup.count("<main") == 1,
        "skip_link": 'class="skip-link" href="#main-workbench"' in markup,
        "live_status_regions": "aria-live=" in markup,
        "dialog_markup": 'role="dialog"' in markup and 'aria-modal="true"' in markup,
        "dialog_focus_return": "overlayReturnFocus" in javascript,
        "dialog_focusable_filter": "function overlayFocusableElements" in javascript,
        "escape_closes_overlays": "event.key === 'Escape'" in javascript,
        "tabpanel_relationships": "panel.setAttribute('aria-labelledby', tab.id)" in javascript,
        "visible_keyboard_focus": ":focus-visible" in stylesheet,
        "reduced_motion": "prefers-reduced-motion" in stylesheet,
        "forced_colors": "forced-colors: active" in stylesheet,
        "responsive_profile_announcement": "function syncViewportContract()" in javascript,
    }
    blockers = [f"accessibility_contract_failed:{name}" for name, passed in checks.items() if not passed]
    return {
        "status": "pass" if not blockers else "fail",
        "audit_kind": "static_packaged_asset_audit",
        "checks": checks,
        "counts": {
            "main_landmarks": markup.count("<main"),
            "dialogs": len(re.findall(r'role=["\']dialog["\']', markup)),
            "modal_dialogs": len(re.findall(r'aria-modal=["\']true["\']', markup)),
            "live_regions": len(re.findall(r'aria-live=', markup)),
        },
        "limitations": [
            "Does not prove a screen-reader session, browser rendering, frozen executable, or MSIX behavior.",
            "Does not replace manual keyboard, zoom, high-contrast, or assistive-technology testing.",
        ],
        "blockers": blockers,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def production_ui_manifest(root: str | Path | None = None) -> dict[str, Any]:
    asset_root = Path(root) if root is not None else ui_asset_root()
    files: dict[str, dict[str, Any]] = {}
    contents: dict[str, str] = {}
    missing: list[str] = []
    for name in PRODUCTION_ASSETS:
        path = asset_root / name
        if not path.is_file():
            missing.append(name)
            continue
        contents[name] = path.read_text(encoding="utf-8")
        files[name] = {
            "url": f"/ui-assets/{name}",
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    checks = {
        name: marker in contents.get(filename, "")
        for name, (filename, marker) in REQUIRED_CONTRACTS.items()
    }
    accessibility_audit = _accessibility_audit(contents)
    javascript = contents.get("workbench.js", "")
    all_api_paths = sorted(set(re.findall(r"[\"'](/api/[a-zA-Z0-9_?&=./{}:-]+)", javascript)))
    experimental_api_paths = [
        path
        for path in all_api_paths
        if any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in EXPERIMENTAL_HIDDEN_API_PREFIXES
        )
    ]
    api_paths = [path for path in all_api_paths if path not in experimental_api_paths]
    markup = contents.get("workbench.html", "")
    all_workspace_ids = sorted(
        set(re.findall(r'id=["\']([^"\']*workspace(?:-overlay)?)["\']', markup))
    )
    experimental_workspace_ids = [
        workspace_id
        for workspace_id in all_workspace_ids
        if workspace_id in EXPERIMENTAL_HIDDEN_WORKSPACE_IDS
    ]
    workspace_ids = [
        workspace_id
        for workspace_id in all_workspace_ids
        if workspace_id not in EXPERIMENTAL_HIDDEN_WORKSPACE_IDS
    ]
    blockers = [f"missing_asset:{name}" for name in missing]
    blockers.extend(f"contract_failed:{name}" for name, passed in checks.items() if not passed)
    blockers.extend(accessibility_audit["blockers"])
    return {
        "schema_version": "production_ui_manifest_v2",
        "status": "pass" if not blockers else "fail",
        "surface": "bundled_dependency_free_workbench",
        "entrypoint": "/",
        "source_entrypoint": "src/maine_family_law_llm/ui/workbench.html",
        "assets": files,
        "asset_count": len(files),
        "contracts": checks,
        "accessibility_audit": accessibility_audit,
        "api_path_count": len(api_paths),
        "api_paths": api_paths,
        "experimental_hidden_api_paths": experimental_api_paths,
        "workspace_count": len(workspace_ids),
        "workspace_ids": workspace_ids,
        "experimental_hidden_workspace_ids": experimental_workspace_ids,
        "external_runtime_dependencies": [],
        "shadow_tsx_is_production": False,
        "offline_capable": True,
        "blockers": blockers,
        "review_required": False,
    }


__all__ = [
    "EXPERIMENTAL_HIDDEN_API_PREFIXES",
    "EXPERIMENTAL_HIDDEN_WORKSPACE_IDS",
    "PRODUCTION_ASSETS",
    "REQUIRED_CONTRACTS",
    "_accessibility_audit",
    "production_ui_manifest",
]

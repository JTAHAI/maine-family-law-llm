"""Audit shipped production UI assets from a running frozen v8 executable.

This is a static frozen-asset and UI-manifest audit. It does not substitute for
screen-reader sessions, keyboard user testing, 200% zoom, forced-colors visual
rendering, native click automation, or Store qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _shared() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get(base_url: str, route: str, accept: str) -> tuple[int, str]:
    request = urllib.request.Request(f"{base_url}{route}", headers={"Accept": accept})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(response.status), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def _json(base_url: str, route: str, headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(f"{base_url}{route}", headers={**headers, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read().decode("utf-8")
            return int(response.status), json.loads(data) if data else {}
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        try:
            return int(exc.code), json.loads(data) if data else {}
        except json.JSONDecodeError:
            return int(exc.code), {}


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    shared = _shared(); shared.validate_runtime_pair(runtime, package); helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_frozen_ui_accessibility_audit_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "execution_level": "frozen_runtime_production_ui_static_asset_audit",
        "fictional_data_only": True, "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime),
        "checks": {}, "asset_hashes": {}, "blockers": [],
        "notice": "Static frozen-runtime asset evidence only; it does not prove a human assistive-technology, visual, zoom, or pointer session.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-frozen-ui-a11y-") as temporary:
        root = Path(temporary); process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            html_status, html = _get(base_url, "/", "text/html")
            js_status, javascript = _get(base_url, "/ui-assets/workbench.js", "application/javascript")
            css_status, stylesheet = _get(base_url, "/ui-assets/workbench.css", "text/css")
            components_status, components = _get(base_url, "/ui-assets/workbench_components.js", "application/javascript")
            manifest_status, manifest = _json(base_url, "/api/runtime/ui-manifest", helper.QA_HEADERS)
            network = monitor.stop(); monitor = None
            audit = dict(manifest.get("accessibility_audit") or {})
            checks = {
                "runtime_health": health.get("status") == "ok",
                "production_workbench_and_components_served": html_status == 200 and js_status == 200 and css_status == 200 and components_status == 200 and 'data-production-ui="workbench"' in html and len(components) > 200,
                "design_tokens_and_display_modes_shipped": all(token in stylesheet for token in ("--color-canvas", "--color-surface", "--color-text", "--color-text-muted", "--color-border", "--color-action", "--color-focus", "--color-status-success", "--space-1", "--type-base", "--focus-ring", "--motion-fast", "@media (prefers-reduced-motion: reduce)", "@media (forced-colors: active)", "data-density", "data-text-scale")),
                "responsive_and_virtual_list_contract_shipped": all(marker in javascript for marker in ("function syncViewportContract()", "dataset.viewportProfile = profile", "window.visualViewport?.width || window.innerWidth", "Chat and its primary action remain available", "sourceCardWindowPageSize = 60", "filterAndWindowItems(", "data-show-more-sources")) and all(marker in components for marker in ("function filterAndWindowItems", "visibleItems: matchingItems.slice(0, requestedLimit)")) and all(marker in stylesheet for marker in ("@media (max-width: 959px)", 'data-viewport-profile="overlay"', "min-inline-size: 44px", "min-block-size: 40px", "source-card-window")),
                "static_accessibility_audit_passes_in_frozen_runtime": manifest_status == 200 and audit.get("status") == "pass" and all(bool(value) for value in dict(audit.get("checks") or {}).values()) and int((audit.get("counts") or {}).get("main_landmarks") or 0) == 1,
                "keyboard_and_focus_controls_shipped": all(marker in javascript for marker in ("KEYBOARD_SHORTCUT_STORAGE_KEY", "keyboardShortcutOptions", "function keyboardShortcutMatches", "function saveKeyboardShortcuts", "const overlayStack = [];", "function activeManagedOverlay()", "function setOverlayBackgroundState(element, active)", "element.inert = !active;", "dialog.setAttribute('aria-modal', active ? 'true' : 'false');")) and all(marker in html for marker in ('id="shortcut-command-palette"', 'id="shortcut-justice"', 'id="shortcut-preferences-save"', 'data-shortcut-command-palette', 'data-shortcut-justice')),
                "density_and_safe_error_center_shipped": all(marker in javascript for marker in ("DISPLAY_PREFERENCES_STORAGE_KEY", "displayPreferenceOptions", "function syncDisplayPreferences", "function saveDisplayPreferences", "dataset.density = displayPreferences.density", "dataset.textScale = displayPreferences.text_scale", "const safeErrorEvents = [];", "const maxSafeErrorEvents = 25;", "function recordSafeError(error, title)", "function renderErrorCenter()", "function openErrorCenter(owner = null)", "recordSafeError(error, title);", "button.dataset.v8Action === 'errors'")) and all(marker in html for marker in ('id="display-density"', 'id="display-text-scale"', 'id="display-preferences-save"', 'id="display-preferences-status"', 'id="error-center-overlay"', 'id="error-center-status"', 'id="error-center-list"', 'data-v8-action="errors"')) and all(marker in stylesheet for marker in (".display-preferences", 'data-density="compact"', 'data-text-scale="large"', 'data-text-scale="extra_large"', ".error-center-card", ".error-center-list")),
                "review_required_and_local_only_boundary_visible": "Review required" in html and "Local-only" in html,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if value else "fail" for name, value in checks.items()}
            report["asset_hashes"] = {"html": hashlib.sha256(html.encode("utf-8")).hexdigest(), "workbench_js": hashlib.sha256(javascript.encode("utf-8")).hexdigest(), "workbench_css": hashlib.sha256(stylesheet.encode("utf-8")).hexdigest(), "components_js": hashlib.sha256(components.encode("utf-8")).hexdigest()}
            report["accessibility_audit_counts"] = dict(audit.get("counts") or {})
            report["network_samples"] = int(network.get("sample_count") or 0)
            report["blockers"] = sorted(name for name, value in checks.items() if not value); report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"frozen_ui_accessibility_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())

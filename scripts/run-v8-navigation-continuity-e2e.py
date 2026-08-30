"""Exercise frozen v8 navigation and continuity workflows with fictional data."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_RUNNER = ROOT / "scripts" / "run-v8-procedure-review-e2e.py"


def _procedure() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_v8_procedure_e2e", PROCEDURE_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("procedure_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _encrypted(case_root: Path, relative: str, forbidden: str) -> bool:
    path = case_root / relative
    return path.is_file() and forbidden.encode("utf-8") not in path.read_bytes()


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    procedure = _procedure()
    shared = procedure._shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_navigation_continuity_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime),
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This proves fictional review-work navigation only; it does not establish facts, conclusions, legal advice, filing readiness, browser/native interaction, Store qualification, or Enterprise GA.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-navigation-") as temporary:
        root = Path(temporary)
        matter, other_matter = root / "fictional-matter", root / "other-fictional-matter"
        matter.mkdir(); other_matter.mkdir()
        records = helper.build_case_fixture(matter)
        record = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        record_hash = str(record.get("source_hash") or "")
        process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            ui_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            command_bar = shared.request(helper, "GET", base_url, "/api/command-bar/search?q=record")
            matter_search = shared.request(helper, "GET", base_url, "/api/matter-search?q=record")
            smart = shared.request(helper, "POST", base_url, "/api/smart-views", {"view_id": "fictional_view_001", "kind": "review_queue", "title": "Fictional review queue", "user_confirmed": True})
            smart_run = shared.request(helper, "GET", base_url, "/api/smart-views/fictional_view_001/run")
            recent = shared.request(helper, "PUT", base_url, "/api/recent-work", {"workspace_id": "chat", "scroll_position": 240, "selected_sources": [{"lane": "private_matter_record", "record_id": "REC-DOCX", "source_hash": record_hash, "page": 1}], "unsent_draft": "Fictional unsent local-review question."})
            recent_source = shared.request(helper, "GET", base_url, "/api/recent-work/chat/sources/0")
            tab = shared.request(helper, "POST", base_url, "/api/workspace-tabs", {"tab_id": "fictional_tab_001", "kind": "record", "label": "Fictional record review", "target": {"record_id": "REC-DOCX", "source_hash": record_hash, "page": 1}, "user_confirmed": True})
            tab_active = shared.request(helper, "POST", base_url, "/api/workspace-tabs/fictional_tab_001/activate", {})
            tab_target = shared.request(helper, "GET", base_url, "/api/workspace-tabs/fictional_tab_001/target")
            history = shared.request(helper, "POST", base_url, "/api/command-history", {"command_id": "fictional_search_001", "operation": "matter_search", "kind": "read", "parameters": {"query": "record"}})
            replay = shared.request(helper, "POST", base_url, "/api/command-history/fictional_search_001/replay", {})
            queue = shared.request(helper, "POST", base_url, "/api/bulk-review-queue", {"item_id": "fictional_queue_001", "kind": "claim", "label": "Fictional claim review", "source_ref": {"record_id": "REC-DOCX", "source_hash": record_hash, "page": 1}, "user_confirmed": True})
            triage = shared.request(helper, "POST", base_url, "/api/bulk-review-queue/fictional_queue_001/triage", {"state": "qualified", "reviewer_safe_id": "reviewer_fictional_001", "user_confirmed": True})
            queue_source = shared.request(helper, "GET", base_url, "/api/bulk-review-queue/fictional_queue_001/source")
            favorite = shared.request(helper, "POST", base_url, "/api/favorites", {"favorite_id": "fictional_favorite_001", "kind": "record", "label": "Fictional record pin", "target": {"record_id": "REC-DOCX", "source_hash": record_hash}, "visibility": "private", "owner_role": "reviewer", "user_confirmed": True})
            favorite_open = shared.request(helper, "GET", base_url, "/api/favorites/fictional_favorite_001/open?viewer_role=reviewer")
            label = shared.request(helper, "POST", base_url, "/api/user-labels", {"label_id": "fictional_priority", "name": "Fictional priority", "color": "#1f7a8c", "user_confirmed": True})
            assignment = shared.request(helper, "POST", base_url, "/api/user-labels/fictional_priority/assignments", {"record_id": "REC-DOCX", "source_hash": record_hash, "user_confirmed": True})
            label_export = shared.request(helper, "POST", base_url, "/api/user-labels/export", {"user_confirmed": True})
            brief = shared.request(helper, "POST", base_url, "/api/daily-matter-briefs", {"brief_id": "fictional_brief_001", "user_confirmed": True})
            brief_loaded = shared.request(helper, "GET", base_url, "/api/daily-matter-briefs/fictional_brief_001")
            source_statuses = {
                "recent": procedure._source_status(helper, base_url, str((recent_source.get("source") or {}).get("source_token") or "")),
                "tab": procedure._source_status(helper, base_url, str((tab_target.get("target") or {}).get("source_token") or "")),
                "queue": procedure._source_status(helper, base_url, str((queue_source.get("source") or {}).get("source_token") or "")),
                "favorite": procedure._source_status(helper, base_url, str((favorite_open.get("target") or {}).get("source_token") or "")),
            }
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            recent_other = shared.request(helper, "GET", base_url, "/api/recent-work?workspace_id=chat")
            cross_statuses = {
                "smart": procedure._status(helper, base_url, "/api/smart-views/fictional_view_001/run"),
                "tab": procedure._status(helper, base_url, "/api/workspace-tabs/fictional_tab_001/target"),
                "queue": procedure._status(helper, base_url, "/api/bulk-review-queue/fictional_queue_001/source"),
                "favorite": procedure._status(helper, base_url, "/api/favorites/fictional_favorite_001/open?viewer_role=reviewer"),
                "brief": procedure._status(helper, base_url, "/api/daily-matter-briefs/fictional_brief_001"),
            }
            network = monitor.stop(); monitor = None
            checks = {
                "runtime_health": health.get("status") == "ok", "fictional_matter_activated": activation.get("status") == "ok",
                "shipped_production_ui_entries_present": ui_status == 200 and all(value in workbench_js for value in ("/api/command-bar/search", "Unified matter search", "Saved smart views", "/api/recent-work", "Workspace tabs", "Command history", "Bulk review queue", "Favorites and pins", "User-defined labels", "Daily matter brief")),
                "searches_are_matter_scoped_and_path_safe": command_bar.get("active_matter_only") is True and matter_search.get("matter_scope") == "active_matter_only" and all("case_root" not in row for row in list(command_bar.get("results") or [])),
                "smart_view_is_review_filter": (smart.get("view") or {}).get("review_required") is True and smart_run.get("review_required") is True,
                "recent_work_and_tabs_preserve_review_boundary": (recent.get("restore_point") or {}).get("review_required") is True and (tab.get("tab") or {}).get("review_required") is True and tab_active.get("active_tab_id") == "fictional_tab_001",
                "history_replays_only_safe_read": history.get("command", {}).get("review_required") is True and replay.get("execute") is True and (replay.get("result") or {}).get("matter_scope") == "active_matter_only",
                "queue_favorites_labels_and_brief_are_review_only": (queue.get("item") or {}).get("state") == "new" and (triage.get("item") or {}).get("state") == "qualified" and (favorite.get("favorite") or {}).get("review_required") is True and bool((label.get("label") or {}).get("label_id")) and bool((assignment.get("assignment") or {}).get("record_id")) and bool((label_export.get("export") or {}).get("sha256")) and (brief.get("brief") or {}).get("review_required") is True and (brief_loaded.get("brief") or {}).get("brief_id") == "fictional_brief_001",
                "private_source_drill_downs_reopen": all(value == 200 for value in source_statuses.values()),
                "encrypted_navigation_sidecars": all((
                    _encrypted(matter, "40_RUNTIME/smart-views/views.json.enc", "Fictional review queue"),
                    _encrypted(matter, "40_RUNTIME/recent-work/restore-points.json.enc", "Fictional unsent local-review question"),
                    _encrypted(matter, "40_RUNTIME/workspace-tabs/tabs.json.enc", "Fictional record review"),
                    _encrypted(matter, "40_RUNTIME/command-history/commands.json.enc", "query"),
                    _encrypted(matter, "40_RUNTIME/bulk-review-queue/queue.json.enc", "Fictional claim review"),
                    _encrypted(matter, "40_RUNTIME/favorites/favorites.json.enc", "Fictional record pin"),
                    _encrypted(matter, "40_RUNTIME/user-labels/labels.json.enc", "Fictional priority"),
                    _encrypted(matter, "40_RUNTIME/daily-matter-brief/briefs.json.enc", "REC-DOCX"),
                )),
                "cross_matter_access_denied": switched.get("status") == "ok" and all(value == 404 for value in cross_statuses.values()) and recent_other.get("restore_point") is None,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {"source_hash": record_hash, "source_drill_down_statuses": source_statuses, "cross_matter_statuses": cross_statuses, "recent_restore_point_after_matter_switch": "present" if recent_other.get("restore_point") is not None else "absent", "network_samples": int(network.get("sample_count") or 0), "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest()}
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed); report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"navigation_continuity_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())

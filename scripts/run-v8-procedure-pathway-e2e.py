"""Exercise a fictional, non-advisory procedure pathway through the frozen runtime."""

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
    if spec is None or spec.loader is None: raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def _status(helper: Any, method: str, base_url: str, route: str) -> int:
    request = urllib.request.Request(f"{base_url}{route}", method=method, headers={**helper.QA_HEADERS, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read(); return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read(); return int(exc.code)


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = _shared(); shared.validate_runtime_pair(runtime, package); helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_procedure_pathway_e2e_v1", "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED", "fictional_data_only": True, "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package), "runtime_sha256": shared.sha256_file(runtime), "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This proves a reviewer-entered procedure checklist only. It does not decide venue, jurisdiction, service, deadlines, requirements, legal effect, likely outcome, filing readiness, or GA status.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-procedure-") as temporary:
        root = Path(temporary); matter, other = root / "fictional-matter", root / "fictional-other-matter"
        matter.mkdir(); other.mkdir(); records = helper.build_case_fixture(matter)
        expected = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        process = None; monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            candidates = shared.request(helper, "GET", base_url, "/api/drafting/outline-evidence-candidates")
            order = next((row for row in list(candidates.get("candidates") or []) if row.get("record_id") == "REC-DOCX"), {})
            source = shared.request(helper, "GET", base_url, f"/api/authority/sources/{authority_source_id}")
            created = shared.request(helper, "POST", base_url, "/api/procedure-pathways", {
                "pathway_id": "fictional_pathway_001", "reviewer_safe_id": "reviewer_fictional_001", "case_type": "family_matter", "posture": "post_judgment",
                "venue_label": "Fictional venue note for reviewer discussion", "existing_orders": [{"record_id": str(order.get("record_id") or ""), "source_hash": str(order.get("source_hash") or ""), "page_number": 1}],
                "authority_source_id": authority_source_id, "user_confirmed": True,
            })
            pathway = dict(created.get("pathway") or {})
            loaded = shared.request(helper, "GET", base_url, "/api/procedure-pathways/fictional_pathway_001")
            private = shared.request(helper, "GET", base_url, "/api/procedure-pathways/fictional_pathway_001/private_matter_record/REC-DOCX/source")
            authority_id = str((pathway.get("authority") or {}).get("authority_id") or "")
            official = shared.request(helper, "GET", base_url, f"/api/procedure-pathways/fictional_pathway_001/official_authority/{authority_id}/source")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, "/api/procedure-pathways/fictional_pathway_001")
            network = monitor.stop(); monitor = None
            encrypted = list(matter.rglob("pathways.json.enc")); ciphertext = encrypted[0].read_bytes() if len(encrypted) == 1 else b""
            private_source = dict(private.get("source") or {}); official_source = dict(official.get("source") or {})
            checks = {
                "runtime_health": health.get("status") == "ok", "fictional_matter_activated": activated.get("status") == "ok",
                "private_order_hash_bound": str(order.get("source_hash") or "") == str(expected.get("source_hash") or ""),
                "canonical_official_source_detail_available": source.get("status") == "pass" and bool((source.get("source_card") or {}).get("source_hash")),
                "pathway_review_required_non_filing_non_advisory": created.get("review_required") is True and created.get("filing_ready") is False and pathway.get("legal_conclusion") == "not_determined",
                "pathway_reload_current_matter": str((loaded.get("pathway") or {}).get("pathway_id") or "") == "fictional_pathway_001",
                "private_source_drilldown": str(private_source.get("source_hash") or "") == str(expected.get("source_hash") or "") and bool(private_source.get("source_token")),
                "official_source_drilldown": str(official_source.get("source_id") or "") == authority_source_id and bool(official_source.get("source_hash")),
                "pathway_state_encrypted_at_rest": len(encrypted) == 1 and b"Fictional venue note" not in ciphertext,
                "cross_matter_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {"pathway_id": str(pathway.get("pathway_id") or ""), "step_count": len(list(pathway.get("steps") or [])), "authority_id": authority_id, "private_record_hash": str(private_source.get("source_hash") or ""), "official_source_hash": str(official_source.get("source_hash") or ""), "encrypted_pathway_state_sha256": hashlib.sha256(ciphertext).hexdigest(), "cross_matter_status": cross_status, "network_samples": int(network.get("sample_count") or 0)}
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed); report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"procedure_pathway_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--runtime-executable", required=True, type=Path); parser.add_argument("--package", required=True, type=Path); parser.add_argument("--authority-data-root", required=True, type=Path); parser.add_argument("--authority-source-id", required=True); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_data_root.resolve(strict=True), authority_source_id=args.authority_source_id)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())

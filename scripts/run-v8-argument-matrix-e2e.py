"""Exercise one source-bound argument/counterargument matrix in the frozen runtime.

Only a disposable fictional matter is used.  The evidence deliberately records
opaque IDs, hashes, and status codes rather than private record text or source
text.  Passing this runner proves a review workflow, never a legal conclusion,
credibility assessment, outcome prediction, or filing-ready artifact.
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


def _status(helper: Any, method: str, base_url: str, route: str) -> int:
    request = urllib.request.Request(
        f"{base_url}{route}", method=method, headers={**helper.QA_HEADERS, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_argument_matrix_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_provenance": {"source_id": authority_source_id, "resolution": "pending"},
        "checks": {}, "artifacts": {}, "blockers": [],
        "notice": "This proves an encrypted, review-required comparison of fictional positions. It does not decide facts, credibility, law, jurisdiction, legal sufficiency, likely outcomes, filing readiness, Store qualification, or Enterprise GA.",
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-argument-matrix-") as temporary:
        root = Path(temporary)
        matter, other = root / "fictional-matter", root / "fictional-other-matter"
        matter.mkdir(); other.mkdir()
        records = helper.build_case_fixture(matter)
        expected = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        process = None
        monitor = None
        try:
            port = helper.free_port(); base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata", authority_data_root=authority_root)
            monitor = helper.RuntimeNetworkMonitor(process.pid); monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            candidates = shared.request(helper, "GET", base_url, "/api/drafting/outline-evidence-candidates")
            evidence = next((row for row in list(candidates.get("candidates") or []) if row.get("record_id") == "REC-DOCX"), {})
            authority_detail = shared.request(helper, "GET", base_url, f"/api/authority/sources/{authority_source_id}")
            authority_card = dict(authority_detail.get("source_card") or {})
            authority_hash = str(authority_card.get("source_hash") or "")
            report["authority_provenance"] = {
                "source_id": authority_source_id,
                "source_hash": authority_hash,
                "source_class": str(authority_card.get("source_class") or ""),
                "freshness_status": str(authority_card.get("freshness_status") or ""),
                "resolution_status": str(authority_detail.get("status") or ""),
            }
            authority_response = shared.request(helper, "GET", base_url, f"/api/drafting/outline-authority-candidate/{authority_source_id}")
            authority = dict(authority_response.get("candidate") or {})
            precise_candidates = [
                dict(item) for item in list(authority_response.get("pinpoint_candidates") or [])
                if isinstance(item, dict) and item.get("authority_id") and item.get("source_hash") and item.get("exact_span")
            ]
            # This is an explicit deterministic fictional-test selection, not an
            # application default.  The production UI now requires the reviewer
            # to make this choice whenever more than one source span is offered.
            if len(precise_candidates) > 1:
                authority = precise_candidates[0]
            position_source = {"record_id": str(evidence.get("record_id") or ""), "source_hash": str(evidence.get("source_hash") or ""), "page_number": 1}
            position_a = {
                "position_id": "position_a", "label": "Fictional position A", "statement": "Fictional reviewer-entered position A.",
                "supporting_evidence": [position_source], "supporting_authority": [authority],
                "weaknesses": ["Fictional context requires reviewer inspection."], "missing_proof": [],
            }
            position_b = {
                "position_id": "position_b", "label": "Fictional position B", "statement": "Fictional reviewer-entered position B.",
                "supporting_evidence": [position_source], "supporting_authority": [authority],
                "weaknesses": [], "missing_proof": ["Fictional missing attachment."],
            }
            created = shared.request(helper, "POST", base_url, "/api/drafting/argument-matrices", {
                "matrix_id": "fictional_matrix_001", "issue_label": "Fictional parenting-time issue",
                "reviewer_safe_id": "reviewer_fictional_001", "positions": [position_a, position_b], "user_confirmed": True,
            })
            matrix = dict(created.get("matrix") or {})
            loaded = shared.request(helper, "GET", base_url, "/api/drafting/argument-matrices/fictional_matrix_001")
            positions = list(matrix.get("positions") or [])
            first = dict(positions[0]) if positions else {}
            private = shared.request(helper, "GET", base_url, "/api/drafting/argument-matrices/fictional_matrix_001/positions/position_a/private_matter_record/REC-DOCX/source")
            authority_id = str((list(first.get("supporting_authority") or [{}])[0]).get("authority_id") or "")
            official = shared.request(helper, "GET", base_url, f"/api/drafting/argument-matrices/fictional_matrix_001/positions/position_a/official_authority/{authority_id}/source")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other)})
            cross_status = _status(helper, "GET", base_url, "/api/drafting/argument-matrices/fictional_matrix_001")
            network = monitor.stop(); monitor = None
            encrypted = list(matter.rglob("matrices.json.enc"))
            ciphertext = encrypted[0].read_bytes() if len(encrypted) == 1 else b""
            private_source = dict(private.get("source") or {})
            official_source = dict(official.get("source") or {})
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "private_record_hash_bound": str(evidence.get("source_hash") or "") == str(expected.get("source_hash") or ""),
                "authority_candidate_matches_resolved_source": authority_detail.get("status") == "pass" and bool(authority_hash) and str(authority.get("source_hash") or "") == authority_hash,
                "two_positions_and_separate_source_lanes": len(positions) == 2 and str((first.get("supporting_evidence") or [{}])[0].get("lane") or "") == "private_matter_record" and str((first.get("supporting_authority") or [{}])[0].get("lane") or "") == "official_authority",
                "review_required_not_predictive_or_filing_ready": created.get("review_required") is True and created.get("filing_ready") is False and matrix.get("outcome_prediction") is False,
                "private_source_drilldown": str(private_source.get("source_hash") or "") == str(expected.get("source_hash") or "") and bool(private_source.get("source_token")),
                "official_source_drilldown": str(official_source.get("source_hash") or "") == authority_hash and str(official_source.get("source_id") or "") == authority_source_id,
                "matrix_reload_current_matter": str((loaded.get("matrix") or {}).get("matrix_id") or "") == "fictional_matrix_001",
                "matrix_state_encrypted_at_rest": len(encrypted) == 1 and b"Fictional reviewer-entered" not in ciphertext,
                "cross_matter_access_denied": switched.get("status") == "ok" and cross_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {key: "pass" if value else "fail" for key, value in checks.items()}
            report["artifacts"] = {
                "matrix_id": str(matrix.get("matrix_id") or ""), "position_count": len(positions),
                "explicit_selected_authority_id": str(authority.get("authority_id") or ""),
                "precise_authority_candidate_count": len(precise_candidates),
                "private_record_hash": str(private_source.get("source_hash") or ""), "official_source_hash": str(official_source.get("source_hash") or ""),
                "encrypted_matrix_state_sha256": hashlib.sha256(ciphertext).hexdigest(), "cross_matter_status": cross_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(key for key, value in checks.items() if not value)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"argument_matrix_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None: monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists(): parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True), authority_root=args.authority_data_root.resolve(strict=True), authority_source_id=args.authority_source_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())

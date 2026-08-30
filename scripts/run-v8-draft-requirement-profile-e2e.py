"""Exercise the local draft-requirement profile workflow through a frozen runtime.

Only disposable fictional text is created.  The report contains opaque IDs,
hashes, statuses, and counts; it intentionally omits record text and local
paths.  A passing result is a bounded local workflow proof, never a court-form,
legal-sufficiency, filing-readiness, Store, or Enterprise claim.
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


def _load_shared() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status(helper: Any, method: str, base_url: str, route: str) -> int:
    request = urllib.request.Request(
        f"{base_url}{route}",
        method=method,
        headers={**helper.QA_HEADERS, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
            return int(response.status)
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code)


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    shared = _load_shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_draft_requirement_profile_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This proves only a local reviewer-configured text-check workflow. It does not determine a court "
            "requirement, legal sufficiency, filing readiness, or a real-world outcome."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-requirement-profile-") as temporary:
        temp_root = Path(temporary)
        matter = temp_root / "fictional-matter"
        other_matter = temp_root / "fictional-other-matter"
        matter.mkdir()
        other_matter.mkdir()
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=temp_root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            document = shared.request(
                helper,
                "POST",
                base_url,
                "/api/document-workspace/documents",
                {
                    "title": "Fictional profile draft",
                    "document_type": "draft",
                    "content": "Background\nRequested relief\nFictional reviewer working copy.",
                    "note": "Fictional review only.",
                },
            )
            document_id = str((document.get("document") or {}).get("document_id") or "")
            profile = shared.request(
                helper,
                "POST",
                base_url,
                "/api/drafting/requirement-profiles",
                {
                    "profile_id": "fictional_profile_001",
                    "label": "Fictional local review profile",
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "required_sections": ["Background", "Requested relief"],
                    "max_characters": 500,
                    "review_gates": ["Human review required"],
                    "user_confirmed": True,
                },
            )
            evaluated = shared.request(
                helper,
                "POST",
                base_url,
                f"/api/drafting/documents/{document_id}/requirement-profiles/fictional_profile_001/evaluate",
            )
            listed = shared.request(helper, "GET", base_url, "/api/drafting/requirement-profiles")
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            other_listed = shared.request(helper, "GET", base_url, "/api/drafting/requirement-profiles")
            cross_matter_status = _status(
                helper,
                "POST",
                base_url,
                f"/api/drafting/documents/{document_id}/requirement-profiles/fictional_profile_001/evaluate",
            )
            network = monitor.stop()
            monitor = None
            encrypted_paths = list(matter.rglob("profiles.json.enc"))
            ciphertext = encrypted_paths[0].read_text(encoding="utf-8") if len(encrypted_paths) == 1 else ""
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "profile_created_review_required": profile.get("review_required") is True and profile.get("filing_ready") is False,
                "profile_evaluation_uses_only_configured_checks": not list(evaluated.get("blockers") or [])
                and evaluated.get("review_required") is True
                and evaluated.get("filing_ready") is False,
                "profile_listed_in_active_matter": len(list(listed.get("profiles") or [])) == 1,
                "cross_matter_profile_list_isolated": switched.get("status") == "ok" and not list(other_listed.get("profiles") or []),
                "cross_matter_document_evaluation_denied": cross_matter_status == 404,
                "profile_state_encrypted_at_rest": len(encrypted_paths) == 1 and "Background" not in ciphertext,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "document_id": document_id,
                "profile_id": str((profile.get("profile") or {}).get("profile_id") or ""),
                "profile_count": len(list(listed.get("profiles") or [])),
                "evaluation_document_hash": str(evaluated.get("document_content_sha256") or ""),
                "encrypted_profile_state_sha256": hashlib.sha256(ciphertext.encode("utf-8")).hexdigest(),
                "cross_matter_status": cross_matter_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"draft_requirement_profile_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(runtime=args.runtime_executable.resolve(strict=True), package=args.package.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

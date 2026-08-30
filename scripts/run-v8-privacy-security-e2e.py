"""Exercise locally operable privacy/security controls in the frozen r6 runtime.

The runner uses one disposable fictional matter and never writes a capability,
source token, record text, local path, support-bundle content, or clipboard
content to its evidence.  It proves bounded local software behavior only;
Windows Hello hardware, OS clipboard behavior, complete parser isolation,
cryptographic key recovery, Store qualification, and Enterprise GA remain
outside this evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.matter_store import MatterStore
from legal.matter.models import Matter


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_RUNNER = ROOT / "scripts" / "run-v8-procedure-review-e2e.py"


def _procedure() -> Any:
    spec = importlib.util.spec_from_file_location("mfl_v8_procedure_e2e", PROCEDURE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("procedure_runner_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request_result(
    helper: Any,
    method: str,
    base_url: str,
    route: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {**helper.QA_HEADERS, "Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{route}", data=body, method=method.upper(), headers=request_headers
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return int(response.status), (json.loads(raw) if raw else {}), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        return int(exc.code), data, dict(exc.headers.items())


def _download_status(helper: Any, base_url: str, route: str) -> tuple[int, dict[str, str]]:
    request = urllib.request.Request(f"{base_url}{route}", headers={**helper.QA_HEADERS, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response.read()
            return int(response.status), dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        exc.read()
        return int(exc.code), dict(exc.headers.items())


def _header(headers: dict[str, str], name: str) -> str:
    """Read a response header without depending on urllib's display casing."""

    wanted = name.casefold()
    return next((str(value) for key, value in headers.items() if str(key).casefold() == wanted), "")


def _safe_error_code(payload: dict[str, Any]) -> str:
    """Return only a machine-style failure code; never surface server detail."""

    detail = payload.get("detail")
    value = detail.get("error") if isinstance(detail, dict) else ""
    candidate = str(value or "")
    return candidate if candidate.replace("_", "").isalnum() and len(candidate) <= 120 else "no_safe_error_code"


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    procedure = _procedure()
    shared = procedure._shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_privacy_security_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_and_production_ui",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "No real matter data, clipboard content, credentials, biometric data, capability, source token, "
            "raw support bundle, or local path is retained in this evidence. This does not prove Windows Hello "
            "hardware, OS clipboard clearing, kernel isolation, every parser family, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-privacy-security-") as temporary:
        root = Path(temporary)
        # Use the same intentionally local development envelope key the isolated
        # frozen runner uses after it removes MAINE_MATTER_STORE_KEY.  The matter
        # remains outside the repository and disappears with this temporary root.
        vault_root = root / "localappdata" / "vault"
        previous_vault_root = os.environ.get("MFL_VAULT_KEY_ROOT")
        os.environ["MFL_VAULT_KEY_ROOT"] = str(vault_root)
        try:
            store = MatterStore(
                root / "fictional-matter-store",
                project_root=ROOT,
                encryption_key="local-development-key-change-me",
            )
            matter = store.create_matter(
                Matter(
                    matter_id="fictional-matter",
                    tenant_id="local-desktop",
                    title="Fictional privacy-security matter",
                )
            )
        finally:
            if previous_vault_root is None:
                os.environ.pop("MFL_VAULT_KEY_ROOT", None)
            else:
                os.environ["MFL_VAULT_KEY_ROOT"] = previous_vault_root
        other_matter = root / "other-fictional-matter"
        other_matter.mkdir()
        helper.build_case_fixture(matter)
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=root / "localappdata")
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            html_status, html = procedure._text(base_url, "/")
            js_status, workbench_js = procedure._text(base_url, "/ui-assets/workbench.js")
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})

            clipboard_status, clipboard, _ = _request_result(helper, "GET", base_url, "/api/security/privacy/clipboard-policy")
            key_status_code, key_status, _ = _request_result(helper, "GET", base_url, "/api/security/privacy/matter-key")
            unlock_status_code, unlock_status, _ = _request_result(helper, "GET", base_url, "/api/security/privacy/matter-unlock")
            reviewer_rotate_status, _, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/matter-key/rotate", {"approved": True})
            cross_session_status, _, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/session", {"matter_id": "other-fictional-matter", "action": "security_privacy_backup"})
            arbitrary_session_status, _, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/session", {"action": "arbitrary_export"})

            preview_status, preview, _ = _request_result(
                helper,
                "POST",
                base_url,
                "/api/security/privacy/diagnostics/preview",
                {"sections": ["product", "client_error_codes"], "client_error_codes": [{"code": "ui_timeout", "component": "chat"}]},
            )
            build_denied_status, _, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/diagnostics/build", {"sections": ["product"]})
            build_status, bundle, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/diagnostics/build", {"approved": True, "sections": ["product"]})
            adversarial_status, adversarial, _ = _request_result(helper, "POST", base_url, "/api/security/privacy/adversarial-corpus/run", {})

            integrity_status, integrity, _ = _request_result(helper, "GET", base_url, "/api/records/REC-PII-TXT/integrity")
            source_token = str((integrity.get("preview") or {}).get("token") or "")
            disarm_status, disarm, _ = _request_result(
                helper,
                "POST",
                base_url,
                "/api/records/REC-PII-TXT/safe-review-copy",
                {"source_token": source_token, "approved": True, "reviewer": "fictional_reviewer"},
            )
            artifact = dict((disarm.get("artifacts") or {}).get("safe_review_copy") or {})
            receipt = dict((disarm.get("artifacts") or {}).get("receipt") or {})
            artifact_status, artifact_headers = _download_status(helper, base_url, str(artifact.get("download_url") or "")) if artifact.get("download_url") else (0, {})
            receipt_status, receipt_headers = _download_status(helper, base_url, str(receipt.get("receipt_url") or "")) if receipt.get("receipt_url") else (0, {})

            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_artifact_status, _ = _download_status(helper, base_url, str(artifact.get("download_url") or "")) if artifact.get("download_url") else (0, {})
            network = monitor.stop()
            monitor = None

            preview_bundle = dict(preview.get("bundle") or {})
            built_bundle = dict(bundle.get("bundle") or {})
            checks = {
                "runtime_health_and_fictional_matter_activation": health.get("status") == "ok" and activation.get("status") == "ok",
                "production_privacy_ui_entries_shipped": html_status == 200 and js_status == 200 and all(marker in html for marker in ("refresh-matter-key-status", "verify-matter-unlock", "lock-matter-unlock", "run-adversarial-corpus", "preview-support-bundle", "never reads clipboard contents")) and all(marker in workbench_js for marker in ("/api/security/privacy/matter-key", "/api/security/privacy/matter-unlock/", "/api/security/privacy/diagnostics/build", "/api/security/privacy/adversarial-corpus/run", "safe-review-copy", "writeClipboardText(")),
                "matter_key_and_unlock_status_are_nonsecret_and_fail_closed": key_status_code == 200 and key_status.get("status") in {"active", "not_provisioned", "blocked"} and key_status.get("review_required") is True and key_status.get("key_material_exported") is not True and unlock_status_code == 200 and unlock_status.get("status") in {"not_enabled", "blocked", "locked"} and unlock_status.get("biometric_data_collected") is not True and unlock_status.get("review_required") is True,
                "role_and_matter_capability_boundaries_fail_closed": reviewer_rotate_status == 403 and cross_session_status == 403 and arbitrary_session_status == 422,
                "clipboard_policy_never_reads_or_stores_content": clipboard_status == 200 and clipboard.get("clipboard_reading") == "never" and clipboard.get("clipboard_history_stored") is False and clipboard.get("review_required") is True,
                "diagnostics_require_approval_and_exclude_private_content": preview_status == 200 and preview_bundle.get("contains_matter_content") is False and preview_bundle.get("contains_paths") is False and build_denied_status == 409 and build_status == 200 and built_bundle.get("contains_prompts_or_record_text") is False and built_bundle.get("contains_paths") is False and len(str(built_bundle.get("bundle_sha256") or "")) == 64,
                "synthetic_adversarial_corpus_passes_without_matter_or_network": adversarial_status == 200 and adversarial.get("status") == "pass" and adversarial.get("local_only") is True and adversarial.get("synthetic_only") is True and adversarial.get("no_matter_content_read") is True and adversarial.get("no_external_request") is True and int(adversarial.get("safe_count") or 0) == int(adversarial.get("result_count") or -1) and list(adversarial.get("unsafe_case_ids") or []) == [],
                "approved_content_disarm_is_source_bound_and_review_required": integrity_status == 200 and len(source_token) == 64 and disarm_status == 200 and disarm.get("review_required") is True and disarm.get("local_only") is True and disarm.get("original_modified") is False and (disarm.get("disarm") or {}).get("active_content_executed") is False and (disarm.get("disarm") or {}).get("external_resources_loaded") is False and artifact_status == 200 and _header(artifact_headers, "X-MFL-Hash-Verified") == "true" and receipt_status == 200,
                "artifact_capability_fails_closed_after_matter_switch": switched.get("status") == "ok" and cross_artifact_status == 404,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "network_samples": int(network.get("sample_count") or 0),
                "workbench_js_sha256": hashlib.sha256(workbench_js.encode("utf-8")).hexdigest(),
                "safe_adversarial_case_count": int(adversarial.get("safe_count") or 0),
                "adversarial_result_count": int(adversarial.get("result_count") or 0),
                "matter_unlock_status": str(unlock_status.get("status") or ""),
                "matter_key_status": str(key_status.get("status") or ""),
                "matter_key_http_status": key_status_code,
                "matter_key_safe_error_code": _safe_error_code(key_status),
                "matter_key_review_required": key_status.get("review_required") is True,
                "matter_key_material_exported": key_status.get("key_material_exported") is True,
                "matter_unlock_review_required": unlock_status.get("review_required") is True,
                "matter_unlock_biometric_data_collected": unlock_status.get("biometric_data_collected") is True,
                "content_disarm_status": str(disarm.get("status") or ""),
                "content_disarm_review_required": disarm.get("review_required") is True,
                "content_disarm_local_only": disarm.get("local_only") is True,
                "content_disarm_original_modified": disarm.get("original_modified") is True,
                "content_disarm_active_content_executed": (disarm.get("disarm") or {}).get("active_content_executed") is True,
                "content_disarm_external_resources_loaded": (disarm.get("disarm") or {}).get("external_resources_loaded") is True,
                "safe_review_copy_hash_header": _header(artifact_headers, "X-MFL-Hash-Verified"),
                "safe_review_copy_http_status": artifact_status,
                "safe_review_receipt_http_status": receipt_status,
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"privacy_security_exception:{type(exc).__name__}"]
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

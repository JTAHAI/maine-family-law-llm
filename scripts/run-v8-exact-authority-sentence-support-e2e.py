"""Prove the frozen sentence-support-map authority boundary with fictional data.

The runner uses an external admitted authority build only to select one exact
source span.  It creates a temporary fictional matter, never writes authority
text or a local path into evidence, and proves that the canonical API replaces
client-supplied authority fields before the encrypted review work product is
created.  It is not a legal-quality or release-certification test.
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


def _request_status(
    helper: Any, base_url: str, route: str, payload: dict[str, Any]
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"{base_url}{route}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={**helper.QA_HEADERS, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), json.loads(exc.read().decode("utf-8"))
        except json.JSONDecodeError:
            return int(exc.code), {}


def _safe_map(value: dict[str, Any]) -> dict[str, Any]:
    summary = dict(value.get("summary") or {})
    return {
        "map_id": str(value.get("map_id") or ""),
        "document_id": str(value.get("document_id") or ""),
        "revision_id": str(value.get("revision_id") or ""),
        "sentence_count": int(summary.get("sentence_count") or 0),
        "supported_sentences": int(summary.get("supported_sentences") or 0),
        "missing_context_sentences": int(summary.get("missing_context_sentences") or 0),
        "review_required": value.get("review_required") is True,
        "filing_ready": value.get("filing_ready") is True,
        "current_revision_match": value.get("current_revision_match") is True,
        "stale_for_current_draft": value.get("stale_for_current_draft") is True,
    }


def run(
    *, runtime: Path, package: Path, authority_root: Path, authority_source_id: str, pinpoint: str
) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_exact_authority_sentence_support_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority": {
            "source_id": authority_source_id,
            "selected_pinpoint_sha256": hashlib.sha256(pinpoint.encode("utf-8")).hexdigest(),
        },
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "Fictional local-workflow evidence only. A source match is a review signal, not a legal conclusion, "
            "factual finding, current-law statement, attorney review, filing authorization, Store qualification, "
            "or Enterprise GA evidence."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-exact-sentence-map-") as temporary:
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
            process = helper.start_runtime(
                runtime,
                port,
                localappdata=temp_root / "localappdata",
                authority_data_root=authority_root,
            )
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activated = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(matter)})
            resolved = shared.request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/outline-authority-candidate/{authority_source_id}",
            )
            candidates = [
                dict(row)
                for row in list(resolved.get("pinpoint_candidates") or [])
                if isinstance(row, dict) and str(row.get("authority_id") or "")
            ]
            selected = next((row for row in candidates if str(row.get("pinpoint") or "") == pinpoint), {})
            authority_id = str(selected.get("authority_id") or "")
            source_hash = str(selected.get("source_hash") or "")
            exact_span = str(selected.get("exact_span") or "")
            document = shared.request(
                helper,
                "POST",
                base_url,
                "/api/document-workspace/documents",
                {
                    "title": "Fictional exact-authority support draft",
                    "document_type": "draft",
                    "content": f"19-A M.R.S. § 1653(1) provides: {exact_span}",
                    "note": "Temporary fictional review draft only.",
                },
            )
            document_id = str((document.get("document") or {}).get("document_id") or "")
            map_route = f"/api/drafting/documents/{document_id}/sentence-support-maps"
            forged_status, forged_body = _request_status(
                helper,
                base_url,
                map_route,
                {
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_authority": [
                        {"source_id": authority_source_id, "authority_id": authority_id, "source_hash": "0" * 64}
                    ],
                    "user_confirmed": True,
                },
            )
            created = shared.request(
                helper,
                "POST",
                base_url,
                map_route,
                {
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_authority": [
                        {
                            "source_id": authority_source_id,
                            "authority_id": authority_id,
                            "source_hash": source_hash,
                            "citation": "untrusted-client-citation",
                            "exact_span": "untrusted-client-span",
                            "freshness_status": "stale",
                        }
                    ],
                    "user_confirmed": True,
                },
            )
            sentence_map = dict(created.get("map") or {})
            map_id = str(sentence_map.get("map_id") or "")
            authority_sentence = next(
                (
                    row
                    for row in list(sentence_map.get("sentences") or [])
                    if any(card.get("lane") == "official_authority" for card in list(row.get("supports") or []))
                ),
                {},
            )
            authority_index = next(
                (
                    index
                    for index, card in enumerate(list(authority_sentence.get("supports") or []))
                    if card.get("lane") == "official_authority"
                ),
                -1,
            )
            source = (
                shared.request(
                    helper,
                    "GET",
                    base_url,
                    f"{map_route}/{map_id}/sentences/{str(authority_sentence.get('sentence_id') or '')}/"
                    f"supports/{authority_index}/source",
                )
                if authority_sentence and authority_index >= 0
                else {}
            )
            source_card = dict(source.get("source") or {})
            encrypted_map = matter / "19_DRAFTING" / "sentence-support-maps" / "sentence-support-maps.json.enc"
            encrypted_bytes = encrypted_map.read_bytes() if encrypted_map.is_file() and not encrypted_map.is_symlink() else b""
            switched = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(other_matter)})
            cross_matter_status = shared.status_for_bytes(helper, base_url, f"{map_route}/{map_id}")
            network = monitor.stop()
            monitor = None
            map_state = _safe_map(sentence_map)
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activated.get("status") == "ok",
                "exact_pinpoint_selected": bool(authority_id) and bool(source_hash) and bool(exact_span),
                "forged_client_hash_rejected": forged_status == 409 and str(forged_body.get("detail") or "") == "sentence_support_authority_hash_mismatch",
                "client_authority_fields_re_resolved": bool(source_card) and source_card.get("lane") == "official_authority" and str(source_card.get("source_hash") or "") == source_hash and str(source_card.get("citation") or "") != "untrusted-client-citation",
                "source_drilldown_review_required": source.get("review_required") is True,
                "map_review_required_not_filing_ready": map_state["review_required"] and not map_state["filing_ready"],
                "current_revision_visible": map_state["current_revision_match"] and not map_state["stale_for_current_draft"],
                "map_encrypted_at_rest": bool(encrypted_bytes) and exact_span.encode("utf-8") not in encrypted_bytes and b"untrusted-client-citation" not in encrypted_bytes,
                "cross_matter_map_access_denied": switched.get("status") == "ok" and cross_matter_status == 404,
                "external_authority_excluded_from_msix": True,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "pinpoint_candidate_count": len(candidates),
                "selected_authority_hash": source_hash,
                "map": map_state,
                "authority_source_lane": str(source_card.get("lane") or ""),
                "authority_source_hash": str(source_card.get("source_hash") or ""),
                "cross_matter_map_status": cross_matter_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"exact_authority_sentence_support_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--pinpoint", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable.resolve(strict=True),
        package=args.package.resolve(strict=True),
        authority_root=args.authority_data_root.resolve(strict=True),
        authority_source_id=args.authority_source_id,
        pinpoint=args.pinpoint,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

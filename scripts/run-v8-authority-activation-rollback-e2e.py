"""Prove frozen authority activation and rollback on a disposable fictional root.

The runner materializes two minimal fictional authority builds below a temporary
external data root.  It then uses the frozen runtime's canonical API to review
the staged diff, activate it with an explicit acknowledgement, restart, and
roll it back with another explicit acknowledgement.  The live authority root
is never opened for writing, no source update is performed, and evidence keeps
only opaque build IDs, hashes, counts, and safe statuses.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.production import AuthorityProductPublisher, AuthorityProductVerifier


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _shared() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_v8_outline_e2e", OUTLINE_RUNNER)
    if specification is None or specification.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_root(temporary_root: Path) -> tuple[Path, Path]:
    """Create a complete fictional authority product input outside this repository."""

    root = temporary_root / "external-fictional-authority"
    snapshot = root / "official_authority_store" / "snapshots" / "fictional-title19a.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("<h1>Fictional authority version one</h1>", encoding="utf-8")

    def write_manifest(*, retrieved_at: str) -> None:
        _write_json(
            root / "official_authority_store" / "source_manifest.json",
            [
                {
                    "source_id": "fictional-maine-authority-001",
                    "source_class": "statute_title_index",
                    "jurisdiction": "maine",
                    "retrieved_at": retrieved_at,
                    "hash": _sha256(snapshot),
                    "parser_status": "parsed",
                    "freshness_status": "fresh",
                    "data_class": "official_public_authority",
                    "source_url_or_path": "https://example.invalid/fictional-authority",
                    "snapshot_path": "snapshots/fictional-title19a.html",
                    "parser_audit": {"status": "parsed"},
                }
            ],
        )

    write_manifest(retrieved_at="2026-08-29T00:00:00+00:00")
    parsed = root / "parsed_authority_store" / "statutes" / "fictional_sections.jsonl"
    parsed.parent.mkdir(parents=True, exist_ok=True)
    parsed.write_text(
        json.dumps(
            {
                "record_id": "fictional-statute-001",
                "source_id": "fictional-maine-authority-001",
                "source_hash": _sha256(snapshot),
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 20},
                "citation": "Fictional citation",
                "text": "Fictional section text.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {
            "record_counts": {"statutes": 1, "rules": 0, "forms": 0, "opinions": 0},
            "output_files": {"statutes/fictional_sections.jsonl": str(parsed)},
        },
    )
    citation_index = root / "authority_layer" / "citation_index.json"
    source_cards = root / "authority_layer" / "source_cards.jsonl"
    source_cards.parent.mkdir(parents=True, exist_ok=True)
    _write_json(citation_index, [])
    source_cards.write_text("{}\n", encoding="utf-8")
    graph = root / "authority_layer" / "authority_graph.json"
    _write_json(graph, {})
    _write_json(
        root / "authority_layer" / "authority_layer_report.json",
        {
            "status": "pass",
            "outputs": {
                "citation_index": str(citation_index),
                "source_cards": str(source_cards),
                "authority_graph": str(graph),
            },
        },
    )
    retrieval = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval.parent.mkdir(parents=True, exist_ok=True)
    retrieval.write_text("{}\n", encoding="utf-8")
    exact = root / "embedding_store" / "hybrid" / "exact_citation_lookup.json"
    _write_json(exact, {})
    _write_json(
        root / "embedding_store" / "retrieval_index_manifest.json",
        {
            "status": "pass",
            "document_count": 1,
            "outputs": {"hybrid_documents": str(retrieval), "exact_citation_lookup": str(exact)},
        },
    )
    _write_json(
        root / "source_update_report.json",
        {"status": "pass", "freshness_counts": {"fresh": 1, "stale": 0, "unknown": 0}},
    )
    return root, snapshot


def _publish_staged_pair(temporary_root: Path) -> tuple[Path, str, str]:
    root, snapshot = _fixture_root(temporary_root)
    publisher = AuthorityProductPublisher(data_root=root, repo_root=ROOT)
    first = publisher.publish(product_version="fictional-v1", activate=True)
    if first.status != "pass" or not first.build_id:
        raise RuntimeError("fictional_first_build_failed")

    snapshot.write_text("<h1>Fictional authority version two</h1>", encoding="utf-8")
    manifest_path = root / "official_authority_store" / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[0]["hash"] = _sha256(snapshot)
    manifest[0]["retrieved_at"] = "2026-08-30T00:00:00+00:00"
    _write_json(manifest_path, manifest)
    second = publisher.publish(product_version="fictional-v2", activate=False)
    if second.status != "pass" or not second.build_id or second.build_id == first.build_id:
        raise RuntimeError("fictional_staged_build_failed")
    if AuthorityProductVerifier(data_root=root, repo_root=ROOT).verify().status != "pass":
        raise RuntimeError("fictional_active_build_verification_failed")
    if AuthorityProductVerifier(data_root=root, repo_root=ROOT).verify(build_id=second.build_id).status != "pass":
        raise RuntimeError("fictional_staged_build_verification_failed")
    return root, first.build_id, second.build_id


def _active_build(payload: dict[str, Any]) -> str:
    for row in list(payload.get("builds") or []):
        if isinstance(row, dict) and row.get("active") is True:
            return str(row.get("build_id") or "")
    return ""


def _safe_operation(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(payload.get("status") or ""),
        "operation": str(payload.get("operation") or ""),
        "build_id": str(payload.get("build_id") or ""),
        "previous_build_id": str(payload.get("previous_build_id") or ""),
        "review_required": payload.get("review_required") is True,
        "blockers": [str(item)[:160] for item in list(payload.get("blockers") or [])[:20]],
    }


def _start(shared: Any, runtime: Path, *, localappdata: Path, authority_root: Path) -> tuple[Any, Any, str]:
    helper = shared.load_helper()
    port = helper.free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = helper.start_runtime(runtime, port, localappdata=localappdata, authority_data_root=authority_root)
    monitor = helper.RuntimeNetworkMonitor(process.pid)
    monitor.start()
    health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
    if health.get("status") != "ok":
        monitor.stop()
        shared.terminate(process)
        raise RuntimeError("frozen_runtime_health_failed")
    return process, monitor, base_url


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    shared = _shared()
    shared.validate_runtime_pair(runtime, package)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_authority_activation_rollback_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_disposable_external_authority_lifecycle",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_root_external_to_repository_and_msix": True,
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "This demonstrates controlled local build selection only. It does not update a live source, decide "
            "current law or legal effect, prove browser interaction, or establish Store or Enterprise readiness."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-authority-lifecycle-") as temporary:
        temporary_root = Path(temporary)
        authority_root, first_build_id, second_build_id = _publish_staged_pair(temporary_root)
        localappdata = temporary_root / "localappdata"
        first_process = first_monitor = second_process = second_monitor = None
        third_process = third_monitor = None
        first_network: dict[str, Any] = {}
        second_network: dict[str, Any] = {}
        third_network: dict[str, Any] = {}
        try:
            first_process, first_monitor, first_url = _start(
                shared, runtime, localappdata=localappdata, authority_root=authority_root
            )
            initial = shared.request(helper, "GET", first_url, "/api/authority/builds?limit=10")
            staged_diff = shared.request(
                helper, "GET", first_url, f"/api/authority/builds/{second_build_id}/diff"
            )
            unacknowledged = shared.request(
                helper,
                "POST",
                first_url,
                "/api/authority/activate",
                {"build_id": second_build_id, "acknowledged": False},
            )
            activated = shared.request(
                helper,
                "POST",
                first_url,
                "/api/authority/activate",
                {"build_id": second_build_id, "acknowledged": True},
            )
            after_activation = shared.request(helper, "GET", first_url, "/api/authority/builds?limit=10")
            first_network = first_monitor.stop()
            first_monitor = None
            shared.terminate(first_process)
            first_process = None

            second_process, second_monitor, second_url = _start(
                shared, runtime, localappdata=localappdata, authority_root=authority_root
            )
            after_restart = shared.request(helper, "GET", second_url, "/api/authority/builds?limit=10")
            rollback = shared.request(
                helper,
                "POST",
                second_url,
                "/api/authority/rollback",
                {"build_id": first_build_id, "acknowledged": True},
            )
            after_rollback = shared.request(helper, "GET", second_url, "/api/authority/builds?limit=10")
            second_network = second_monitor.stop()
            second_monitor = None
            shared.terminate(second_process)
            second_process = None

            third_process, third_monitor, third_url = _start(
                shared, runtime, localappdata=localappdata, authority_root=authority_root
            )
            after_rollback_restart = shared.request(helper, "GET", third_url, "/api/authority/builds?limit=10")
            third_network = third_monitor.stop()
            third_monitor = None
            shared.terminate(third_process)
            third_process = None

            receipts_path = authority_root / "authority_product" / "activation_receipts.jsonl"
            receipt_rows = []
            if receipts_path.is_file() and not receipts_path.is_symlink():
                for line in receipts_path.read_text(encoding="utf-8").splitlines():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        receipt_rows.append(value)
            total_external = sum(
                int(network.get("external_connection_count") or 0)
                for network in (first_network, second_network, third_network)
            )
            checks = {
                "two_distinct_verified_fictional_builds": first_build_id != second_build_id,
                "initial_build_is_active": _active_build(initial) == first_build_id,
                "staged_diff_is_review_required": staged_diff.get("status") == "needs_review"
                and staged_diff.get("review_required") is True
                and second_build_id == str(staged_diff.get("candidate_build_id") or ""),
                "activation_requires_explicit_acknowledgement": unacknowledged.get("status") == "blocked"
                and "authority_activation_acknowledgement_required" in list(unacknowledged.get("blockers") or []),
                "staged_build_activated": activated.get("status") == "pass"
                and activated.get("review_required") is True
                and _active_build(after_activation) == second_build_id,
                "activation_persists_across_restart": _active_build(after_restart) == second_build_id,
                "rollback_is_explicit_and_review_required": rollback.get("status") == "pass"
                and rollback.get("operation") == "rollback"
                and rollback.get("review_required") is True
                and _active_build(after_rollback) == first_build_id,
                "rollback_persists_across_restart": _active_build(after_rollback_restart) == first_build_id,
                "durable_activation_receipts": [row.get("operation") for row in receipt_rows] == ["activate", "rollback"],
                "zero_external_connections": total_external == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "first_build_id": first_build_id,
                "staged_build_id": second_build_id,
                "operations": {
                    "unacknowledged_activation": _safe_operation(unacknowledged),
                    "activation": _safe_operation(activated),
                    "rollback": _safe_operation(rollback),
                },
                "receipt_count": len(receipt_rows),
                "network_samples": sum(
                    int(network.get("sample_count") or 0)
                    for network in (first_network, second_network, third_network)
                ),
                "external_connection_count": total_external,
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001 - evidence intentionally keeps only a safe type
            report["blockers"] = [f"authority_activation_rollback_exception:{type(exc).__name__}"]
        finally:
            for monitor in (first_monitor, second_monitor, third_monitor):
                if monitor is not None:
                    monitor.stop()
            for process in (first_process, second_process, third_process):
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
    report = run(
        runtime=args.runtime_executable.resolve(strict=True),
        package=args.package.resolve(strict=True),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

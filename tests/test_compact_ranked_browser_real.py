"""Opt-in complete shipped-page research flow, not production admission or MSIX.

Only fictional initial search/startup services, the research client and a
zero-memory fault are injected. Hardware recovery uses the actual host probe
and canonical assessor. Preview/run/cancel execute the canonical ASGI app
through real loopback HTTP, with the real resident model and encrypted audit.
"""

import hashlib
import json
import os
import re
import socket
import subprocess
import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
import uvicorn
from starlette.responses import JSONResponse, Response
from test_compact_network_guard import inject_caught_worker_network_attempt
from test_fast_interchange_host_source_binding import bound_host as bound_host
from test_fast_interchange_host_source_binding import preview

from app.services.local_agent_context_service import LocalAgentAuditStore
from app.services.local_agent_run_service import LocalAgentRunStore
from legal.fast_interchange.compact_cpu import fail, pinned_inventory
from legal.fast_interchange.compact_field_client import CompactFieldResearchClient
from legal.fast_interchange.compact_ranked_review import CompactRankedResearchClient
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from legal.fast_interchange.compact_span_process import IsolatedSpanReader
from maine_family_law_llm import api
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.environ.get("MFL_RUN_RANKED_BROWSER_PROOF") != "1",
    reason="Real browser/model proof requires MFL_RUN_RANKED_BROWSER_PROOF=1",
)
def test_real_shipped_page_ranked_review(bound_host, monkeypatch, tmp_path):
    run_id = os.environ.get("MFL_RANKED_BROWSER_PROOF_ID", "01")
    assert re.fullmatch(r"[a-z0-9-]{1,20}", run_id)
    output = OUTPUT / f"ranked-browser-api-{run_id}.json"
    assert not output.exists(), "Preserve prior evidence"
    host = bound_host
    host["headers"]["X-Tenant-Id"] = "local-desktop"
    host["owner"]["tenant_id"] = "local-desktop"
    field_mode = os.environ.get("MFL_BROWSER_FIELD_MODE") == "1"
    field_sequence = field_mode and os.environ.get("MFL_BROWSER_FIELD_SEQUENCE") == "1"
    sequence_only = field_sequence and os.environ.get("MFL_BROWSER_SEQUENCE_ONLY") == "1"
    text = (
        "The fictional folder cover is blue. The export was printed on Tuesday. "
        'A fictional message says "the cost worksheet is missing" from the enclosure. '
        "A later message promises to send the cost worksheet but does not show delivery. "
        "The envelope weighs five fictional units. The reader used a green bookmark."
    )
    if field_mode:
        text = "The fictional session was scheduled for 09:00 but began at 09:25."
    host["path"].write_text(text, encoding="utf-8")
    host["row"]["source_hash"] = hashlib.sha256(host["path"].read_bytes()).hexdigest()
    scope = api._record_capability_identity.set(host["owner"])
    try:
        token = api._record_open_token(host["root"], "REC-1", "REC-1.txt")
    finally:
        api._record_capability_identity.reset(scope)
    host["body"]["source_refs"][0].update(
        source_sha256=host["row"]["source_hash"],
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        record_token=token,
        end_offset=len(text),
    )
    candidate = os.environ.get("MFL_RANKED_BROWSER_CANDIDATE", "legal-passage-reranker")
    if field_mode:
        candidate = "minilm-span-reader"
    assert candidate in {
        "legal-passage-reranker",
        "mixedbread-reranker-comparison",
        "minilm-span-reader",
    }
    worker = (IsolatedSpanReader if field_mode else IsolatedCompactRanker)(
        pinned_inventory(OUTPUT / candidate, "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    client = (
        CompactFieldResearchClient(
            worker, field_type="clock_time", basis="reported_event", research_only=True
        )
        if field_mode
        else CompactRankedResearchClient(worker, research_only=True)
    )
    monkeypatch.setattr(api, "build_local_client", lambda **_kwargs: client)
    monkeypatch.setattr(api, "_local_agent_runs", LocalAgentRunStore())
    host["body"].update(
        provider=client.provider_id,
        model=client.model_name,
        question="When did the session begin?"
        if field_mode
        else "Find the missing cost worksheet and any later delivery evidence.",
    )
    prepared = preview(host)
    search_fixture = {
        "answer": "Fictional record selected for research testing. Review required.",
        "question": host["body"]["question"],
        "citations": prepared["source_cards"],
        "review_required": True,
        "local_agent_available": True,
        "local_agent_task": "evidence_review",
        "local_agent_source_refs": prepared["source_refs"],
        "local_agent_matter_id": host["body"]["matter_id"],
        "failure_class": "none",
    }
    sequence_fixtures = {}
    if field_sequence:
        # Immutable fictional records only. Change the selected source set, not
        # an original record, so prior source cards retain their own identities.
        record_rows = [host["row"]]
        refs = {"REC-1": prepared["source_refs"][0]}
        for record_id, record_text in {
            "REC-2": "The fictional session was scheduled for 10:00. Its actual start is unknown.",
            "REC-3": "The fictional observer wrote that the session began at 10:20. "
            "This account is disputed.",
            "REC-4": "The fictional session began at 11:10.",
        }.items():
            path = host["path"].with_name(record_id + ".txt")
            path.write_text(record_text, encoding="utf-8")
            row = dict(
                host["row"],
                evidence_id=record_id,
                source_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                private_copy_relpath=path.relative_to(host["root"]).as_posix(),
                source_locator=path.name,
            )
            record_rows.append(row)
            # Make the new record visible to the ordinary capability resolver.
            monkeypatch.setattr(api, "load_case_search_records", lambda _root: record_rows)
            identity = api._record_capability_identity.set(host["owner"])
            try:
                token = api._record_open_token(host["root"], record_id, path.name)
            finally:
                api._record_capability_identity.reset(identity)
            refs[record_id] = dict(
                host["body"]["source_refs"][0],
                source_id=record_id,
                source_sha256=row["source_hash"],
                text_sha256=hashlib.sha256(record_text.encode()).hexdigest(),
                end_offset=len(record_text),
                record_token=token,
            )
        for stage, record_ids in {
            "mixed": ["REC-1", "REC-2"],
            "withheld": ["REC-2", "REC-3"],
            "recovered": ["REC-4"],
        }.items():
            selection = preview(host, dict(host["body"], source_refs=[refs[r] for r in record_ids]))
            sequence_fixtures[stage] = dict(
                search_fixture,
                citations=selection["source_cards"],
                local_agent_source_refs=selection["source_refs"],
            )
    report = {
        "level": "shipped_page_and_canonical_http_with_fictional_search_and_research_provider",
        "fictional_only": True,
        "candidate": candidate,
        "field_mode": field_mode,
        "field_sequence": field_sequence,
        "sequence_only": sequence_only,
        "model_sha256": client.model_binding["model_sha256"],
        "production_factory_tested": False,
        "normal_hardware_gate_tested": True,
        "hardware_fault_injection": (
            "available RAM forced to zero only for initial denial; "
            "recovery uses actual host profile"
        ),
        "frozen_app_tested": False,
        "installed_package_tested": False,
        "production_admitted": False,
        "ga_ready": False,
        "requests": [],
        "fixture_routes": [],
        "worker_starts": 0,
        "worker_observations": [],
    }
    actual_profile = api.profile_hardware
    network_fault = inject_caught_worker_network_attempt(monkeypatch)
    network_fault["enabled"] = False
    blocked_memory = not sequence_only
    timeout_fault = False
    actual_generate = client.generate_bound_response
    verified_files = worker.files

    def generate_with_timeout_fixture(*args, **kwargs):
        nonlocal timeout_fault
        if timeout_fault:
            timeout_fault = False
            assert worker._process is None
            fail("generation_timeout")
        return actual_generate(*args, **kwargs)

    monkeypatch.setattr(client, "generate_bound_response", generate_with_timeout_fixture)

    def hardware_profile(root):
        from dataclasses import replace

        measured = actual_profile(root)
        return replace(measured, available_memory_bytes=0) if blocked_memory else measured

    monkeypatch.setattr(api, "profile_hardware", hardware_profile)

    async def isolated_app(scope, receive, send):
        nonlocal blocked_memory, timeout_fault
        route = scope.get("path", "")
        method = scope.get("method", "")
        if (
            route in {"/", "/workbench"}
            or route.startswith(("/ui-assets/", "/brand-assets/"))
            or route
            in {"/api/local-agent/preview", "/api/local-agent/run", "/api/local-agent/cancel"}
        ):

            async def measured_send(message):
                if message["type"] == "http.response.start":
                    report["requests"].append(
                        {"route": route, "method": method, "status": message["status"]}
                    )
                await send(message)

            await api.app(scope, receive, measured_send)
            return
        report["fixture_routes"].append({"route": route, "method": method})
        if route.startswith("/__qa/field-sequence/") and method == "POST" and field_sequence:
            stage = route.rsplit("/", 1)[-1]
            assert stage in sequence_fixtures
            search_fixture.clear()
            search_fixture.update(sequence_fixtures[stage])
            await JSONResponse({"stage": stage})(scope, receive, send)
        elif route == "/__qa/restore-real-hardware" and method == "POST":
            assert worker._process is None, "Blocked hardware must not start a worker"
            blocked_memory = False
            await JSONResponse({"status": "real_hardware_profile_restored"})(scope, receive, send)
        elif route == "/__qa/arm-timeout-fault" and method == "POST":
            assert worker._process is None and worker.completed_requests == 0
            timeout_fault = True
            await JSONResponse({"status": "single_timeout_fixture_armed"})(scope, receive, send)
        elif route == "/__qa/arm-network-fault" and method == "POST":
            assert worker._process is None and worker.completed_requests == 0
            network_fault["enabled"] = True
            await JSONResponse({"status": "dependency_fault_armed"})(scope, receive, send)
        elif route == "/__qa/arm-inventory-fault" and method == "POST":
            assert worker._process is None and worker.completed_requests == 0
            # No disk mutation/copy: simulate an edited receipt claiming a new
            # tokenizer hash while retaining the allowlisted model weight hash.
            worker.files = tuple(
                replace(r, sha256="0" * 64)
                if r.path.name == ("tokenizer_config.json" if field_mode else "tokenizer.json")
                else r
                for r in verified_files
            )
            await JSONResponse({"status": "receipt_fault_armed"})(scope, receive, send)
        elif route == "/__qa/restore-inventory" and method == "POST":
            assert worker._process is None and worker.completed_requests == 0
            assert worker.last_failure["phase"] == "artifact_verification"
            report["forged_metadata_inventory_rejected"] = True
            worker.files = verified_files
            await JSONResponse({"status": "verified_inventory_restored"})(scope, receive, send)
        elif route == "/__qa/restore-real-ranker" and method == "POST":
            assert worker._process is None and worker.completed_requests == 0
            assert network_fault["injections"] >= 1
            assert worker.last_failure["kind"] == "PythonNetworkDenied"
            report["caught_python_network_attempt_discarded"] = True
            report["os_network_isolation_proven"] = False
            network_fault["enabled"] = False
            await JSONResponse({"status": "real_ranker_restored"})(scope, receive, send)
        elif route == "/ask/stream":
            content = (
                "event: accepted\ndata: {}\n\nevent: result\ndata: "
                + json.dumps({"payload": search_fixture, "duration_ms": 1})
                + "\n\n"
            )
            await Response(content, media_type="text/event-stream")(scope, receive, send)
        elif route == "/__qa/worker-observation":
            observation = {
                "process_started": worker._process is not None,
                "rank_requests": worker.completed_requests,
                "resumed_worker_starts": worker.worker_starts,
                "child_pid": worker._process.pid if worker._process is not None else None,
            }
            report["worker_observations"].append(observation)
            await JSONResponse(observation)(scope, receive, send)
        elif route == "/api/corpus-library":
            await JSONResponse(
                {
                    "active_case_id": host["body"]["matter_id"],
                    "active_case_label": "Fictional QA matter",
                    "cases": [
                        {
                            "case_id": host["body"]["matter_id"],
                            "label": "Fictional QA matter",
                            "indexed_records": 1,
                            "pdf_pages": 0,
                        }
                    ],
                }
            )(scope, receive, send)
        elif route == "/api/local-agent/worker/status":
            await JSONResponse({"status": "stopped", "production_admitted": False})(
                scope, receive, send
            )
        elif method == "GET":
            await JSONResponse(
                {
                    "status": "ok",
                    "models": [],
                    "items": [],
                    "records": [],
                    "case_id": host["body"]["matter_id"],
                    "active_case": "Fictional QA matter",
                }
            )(scope, receive, send)
        else:
            await JSONResponse(
                {"detail": "fictional_harness_unrelated_action_blocked"}, status_code=403
            )(scope, receive, send)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(isolated_app, log_level="critical", access_log=False, lifespan="off")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    started = time.monotonic()
    try:
        thread.start()
        for _ in range(500):
            if server.started:
                break
            time.sleep(0.01)
        assert server.started
        config = tmp_path / "browser-input.json"
        config.write_text(
            json.dumps(
                {
                    "base_url": f"http://127.0.0.1:{sock.getsockname()[1]}",
                    "run_id": run_id,
                    "question": host["body"]["question"],
                    "model_name": client.model_name,
                    "field_mode": field_mode,
                    "field_sequence": field_sequence,
                    "sequence_only": sequence_only,
                    "session": host["headers"]["X-MFLL-Client-Session"],
                    "hardware_fault_test": True,
                    "network_fault_test": not field_mode,
                    "timeout_fault_test": True,
                    "inventory_fault_test": True,
                    "browser_engine": os.environ.get(
                        "MFL_RANKED_BROWSER_ENGINE", "msedge-ephemeral"
                    ),
                }
            ),
            encoding="utf-8",
        )
        node = Path(os.environ["MFL_PROOF_NODE"])
        result = subprocess.run(
            [str(node), str(ROOT / "scripts/verify_compact_ranked_flow.mjs"), str(config)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240 if field_sequence else 200,
            env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        )
        report["browser_exit_code"] = result.returncode
        report["browser_stdout"] = result.stdout[-1500:]
        report["browser_stderr"] = result.stderr[-1500:]
        assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:]
        audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
        raw = audit.path.read_bytes()
        assert text.encode() not in raw
        events = audit.encryptor.decrypt_json(json.loads(raw))["events"]
        report["encrypted_audit_actions"] = [e["action"] for e in events]
        assert "result" in report["encrypted_audit_actions"]
        if not field_mode:
            assert report["caught_python_network_attempt_discarded"]
        assert network_fault["enabled"] is False
        assert worker.completed_requests >= 1
        if field_sequence:
            assert worker.completed_requests == (5 if sequence_only else 6)
        report["assertions_passed"] = True
    finally:
        cleanup_errors = []
        for close in (client.cancel, client.release):
            try:
                close()
            except Exception as error:
                cleanup_errors.append(type(error).__name__)
        server.should_exit = True
        thread.join(10)
        sock.close()
        report.update(
            cleanup_errors=cleanup_errors,
            server_stopped=not thread.is_alive(),
            owned_worker_stopped=worker._process is None,
            worker_starts=worker.worker_starts,
            rank_requests=worker.completed_requests,
            peak_resident_bytes=worker.peak_resident_bytes,
            worker_last_failure=worker.last_failure,
            worker_last_exit_code=worker.last_exit_code,
            duration_seconds=round(time.monotonic() - started, 3),
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

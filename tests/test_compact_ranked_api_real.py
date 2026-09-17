"""Opt-in real ranker through canonical API; research injection is NOT production/UI."""

import hashlib
import json
import os
import re
import time
from dataclasses import replace

import pytest
from test_compact_network_guard import inject_caught_worker_network_attempt
from test_fast_interchange_host_source_binding import approved_body, preview, run
from test_fast_interchange_host_source_binding import bound_host as bound_host

from app.services.local_agent_context_service import LocalAgentAuditStore
from app.services.local_agent_run_service import LocalAgentRunStore
from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranked_review import CompactRankedResearchClient
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from maine_family_law_llm import api
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.environ.get("MFL_RUN_RANKED_API_PROOF") != "1",
    reason="Real local model proof requires MFL_RUN_RANKED_API_PROOF=1",
)
def test_real_ranked_review_canonical_api(bound_host, monkeypatch):
    run_id = os.environ.get("MFL_RANKED_API_PROOF_ID", "01")
    assert re.fullmatch(r"[a-z0-9-]{1,24}", run_id)
    output = OUTPUT / f"ranked-canonical-api-{run_id}.json"
    assert not output.exists(), "Preserve previous proof"
    host = bound_host
    text = (
        "The folder cover is blue. The export was printed on Tuesday. "
        'A fictional message says "the cost worksheet is missing" from the enclosure. '
        "A later message promises to send the cost worksheet but does not show delivery. "
        "The envelope weighs five fictional units. The reader used a green bookmark."
    )
    host["path"].write_text(text, encoding="utf-8")
    host["text"] = text
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
    worker = IsolatedCompactRanker(
        pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    client = CompactRankedResearchClient(worker, research_only=True)
    monkeypatch.setattr(api, "build_local_client", lambda **kwargs: client)
    monkeypatch.setattr(api, "_local_agent_runs", LocalAgentRunStore())
    host["body"].update(
        provider=client.provider_id,
        model=client.model_name,
        task="evidence_review",
        endpoint="http://127.0.0.1:1",
        question="Find the missing cost worksheet and any later delivery evidence.",
    )
    report = {
        "level": "canonical_handlers_with_explicit_research_factory_and_normal_hardware_assessor",
        "normal_hardware_gate_tested": True,
        "fictional_only": True,
        "production_factory_tested": False,
        "production_admitted": False,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "ga_ready": False,
        "routes": ["/api/local-agent/preview", "/api/local-agent/run"],
        "implementation_sha256": hashlib.sha256(
            (ROOT / "legal/fast_interchange/compact_ranked_review.py").read_bytes()
        ).hexdigest(),
    }
    started = time.monotonic()
    try:
        actual_profile = api.profile_hardware
        with monkeypatch.context() as fault:
            fault.setattr(
                api,
                "profile_hardware",
                lambda root: replace(actual_profile(root), available_memory_bytes=0),
            )
            blocked = preview(host)
        assert (
            "insufficient_available_memory_for_specialist"
            in blocked["hardware_readiness"]["blockers"]
        )
        assert worker._process is None and worker.completed_requests == 0
        report["injected_zero_memory_blockers"] = blocked["hardware_readiness"]["blockers"]
        selected = preview(host)
        assert not selected["hardware_readiness"]["blockers"]
        assert selected["hardware_readiness"]["execution_accelerator"] == {"kind": "cpu"}
        report["actual_hardware_readiness"] = selected["hardware_readiness"]
        assert selected["source_cards"][0]["snippet"] == text
        assert selected["model_admission"]["production_admitted"] is False
        body = approved_body(host, selected)
        with monkeypatch.context() as fault:
            fault.setattr(api, "installed_torch_runtime", lambda: {"kind": "unavailable"})
            refused = run(host, body)
        assert refused.status_code == 409
        assert refused.json()["detail"]["code"] == "fast_interchange_hardware_not_ready"
        assert worker._process is None and worker.completed_requests == 0
        report["missing_runtime_blocked_before_worker_start"] = True
        selected = preview(host)
        body = approved_body(host, selected)
        for header, value in (
            ("X-User-Role", "attorney"),
            ("X-Tenant-Id", "other-tenant"),
            ("X-MFLL-Client-Session", "b" * 48),
        ):
            response = run(host, body, {**host["headers"], header: value})
            assert response.status_code in {403, 409} and text not in response.text
        assert worker.completed_requests == 0
        with monkeypatch.context() as fault:
            injected = inject_caught_worker_network_attempt(fault)
            refused = run(host, body)
        assert injected["injections"] == 1
        assert refused.status_code == 200
        refusal = refused.json()
        assert refusal["status"] == "local_model_failed_review_required"
        assert refusal["grounded"] is False
        assert refusal["output_grounding"]["status"] == "withheld"
        assert refusal["output_grounding"]["quoted_text_checked"] is False
        assert "fast_interchange_compact_python_network_denied" in refusal["warnings"]
        assert "Keep Local-only on" in refusal["answer"]
        assert "fictional.invalid" not in refused.text
        assert text not in refusal["answer"]
        assert worker.completed_requests == 0 and worker._process is None
        assert worker.last_failure["kind"] == "PythonNetworkDenied"
        assert run(host, body).status_code == 409
        report["caught_python_network_attempt_discarded"] = True
        report["os_network_isolation_proven"] = False
        selected = preview(host)
        body = approved_body(host, selected)
        response = run(host, body)
        report["http_status"], report["payload"] = response.status_code, response.json()
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed_review_required"
        assert payload["review_required"] is True
        assert payload["grounded"] is False
        assert payload["output_grounding"]["status"] == "quoted_text_only"
        assert payload["output_grounding"]["source_context_available"] is True
        assert payload["output_grounding"]["quoted_text_checked"] is True
        assert payload["output_grounding"]["factual_claims_verified"] is False
        assert payload["output_grounding"]["legal_claims_verified"] is False
        assert payload["output_validation"]["status"] == "candidate_passages_review_required"
        assert len(payload["output_validation"]["source_spans"]) == 3
        assert '"the cost worksheet is missing"' in payload["answer"]
        assert "promises to send" in payload["answer"]
        assert "relevance is unknown" in payload["answer"]
        assert payload["output_validation"]["relevance_verified"] is False
        assert len(payload["citations"]) == 1
        assert payload["citations"][0]["source_reference"] == selected["source_refs"][0]
        assert str(host["root"]) not in response.text
        assert worker.completed_requests == 1
        assert run(host, body).status_code == 409
        wrong = {**host["body"], "matter_id": "other-fictional-matter"}
        assert (
            host["client"]
            .post("/api/local-agent/preview", json=wrong, headers=host["headers"])
            .status_code
            == 409
        )
        audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
        raw = audit.path.read_bytes()
        assert text.encode() not in raw and b"fictional-tenant" not in raw
        state = audit.encryptor.decrypt_json(json.loads(raw))
        assert [row["action"] for row in state["events"]] == [
            "preview",
            "preview",
            "hardware_blocked",
            "preview",
            "dispatch",
            "result",
            "preview",
            "dispatch",
            "result",
        ]
        assert (
            state["events"][-1]["receipt_sha256"] == payload["provenance_receipt"]["receipt_sha256"]
        )
        report.update(
            canonical_assertions_passed=True,
            encrypted_audit=True,
            replay_denied=True,
            wrong_matter_denied=True,
            changed_role_tenant_session_denied=True,
        )
    finally:
        client.release()
        report.update(
            owned_worker_stopped=worker._process is None,
            worker_starts=worker.worker_starts,
            rank_requests=worker.completed_requests,
            peak_resident_bytes=worker.peak_resident_bytes,
            duration_seconds=round(time.monotonic() - started, 3),
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

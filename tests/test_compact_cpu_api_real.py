"""Opt-in real-weight proof of canonical handlers, NOT production admission/UI.

The research factory and CPU hardware adapter are injected only in this test.
The normal factory remains unchanged and cannot select these unsigned candidates.
No generation, source verifier, matter scope, approval or audit is mocked.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time

import psutil
import pytest
from test_fast_interchange_host_source_binding import (
    approved_body,
    preview,
    run,
)
from test_fast_interchange_host_source_binding import (
    bound_host as bound_host,
)

from app.services.local_agent_context_service import LocalAgentAuditStore
from app.services.local_agent_run_service import LocalAgentRunStore
from legal.agent_runtime import LocalAgentRuntime
from legal.fast_interchange.compact_cpu import (
    MAX_RESIDENT_BYTES,
    CompactCpuWorker,
    CompactResearchClient,
    pinned_inventory,
)
from legal.fast_interchange.compact_extracts import CompactExtractResearchClient
from maine_family_law_llm import api
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.environ.get("MFL_RUN_COMPACT_CPU_API_PROOF") != "1",
    reason=(
        "Opt-in real weights: set MFL_RUN_COMPACT_CPU_API_PROOF=1; "
        "CPU/RAM and repo-local candidates required"
    ),
)
@pytest.mark.parametrize("capability", ["evidence_review", "drafting"])
def test_real_cpu_candidate_through_canonical_handlers(bound_host, monkeypatch, capability):
    run_id = os.environ.get("MFL_COMPACT_PROOF_RUN_ID", "01")
    assert re.fullmatch(r"[a-z0-9-]{1,24}", run_id), "invalid proof run ID"
    mode = os.environ.get("MFL_COMPACT_PROOF_MODE", "freeform")
    assert mode in {"freeform", "extract"}
    assert mode != "extract" or capability == "evidence_review", "Extract mode is not Drafting"
    prefix = "canonical-api-extract" if mode == "extract" else "canonical-api"
    output = OUTPUT / f"{prefix}-{capability}-{run_id}.json"
    assert not output.exists(), "Preserve the prior real-model receipt; choose a new run ID"
    scratch = OUTPUT / "scratch"
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(scratch))
    host = bound_host
    fixture_variant = os.environ.get("MFL_COMPACT_PROOF_FIXTURE", "original")
    assert fixture_variant in {"original", "embedded_quote"}
    if fixture_variant == "embedded_quote":
        assert mode == "extract"
        text = (
            'Fictional note: the message says "an attachment is missing" but does not '
            "identify it. Review required."
        )
        host["path"].write_text(text, encoding="utf-8")
        host["text"] = text
        host["row"]["source_hash"] = hashlib.sha256(host["path"].read_bytes()).hexdigest()
        scope_token = api._record_capability_identity.set(host["owner"])
        try:
            host["token"] = api._record_open_token(host["root"], "REC-1", "REC-1.txt")
        finally:
            api._record_capability_identity.reset(scope_token)
        host["body"]["source_refs"][0].update(
            source_sha256=host["row"]["source_hash"],
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            end_offset=len(text),
            record_token=host["token"],
        )
    candidate = os.environ.get("MFL_COMPACT_PROOF_CANDIDATE", "qwen3-compact-comparison")
    assert candidate in {"qwen-drafting-base", "qwen3-compact-comparison"}
    model = next(
        r
        for r in pinned_inventory(OUTPUT / candidate, "acquisition.json")
        if r.path.suffix == ".gguf"
    )
    worker = CompactCpuWorker(
        model=model,
        engine=pinned_inventory(OUTPUT / "cpu-runtime", "engine-inventory.json"),
        scratch=scratch,
        research_only=True,
    )
    client = (
        CompactExtractResearchClient(worker)
        if mode == "extract"
        else CompactResearchClient(worker, capability)
    )
    monkeypatch.setattr(api, "build_local_client", lambda **kwargs: client)
    monkeypatch.setattr(api, "_local_agent_runs", LocalAgentRunStore())
    host["body"].update(
        provider="fast_interchange_local",
        model=client.model_name,
        task=capability,
        endpoint="http://127.0.0.1:8105",
        question=(
            "Review what is missing from the fictional record."
            if capability == "evidence_review"
            else "Draft a short neutral request for the missing attachment. "
            "Do not invent a filename or date."
        ),
    )
    report = {
        "level": "canonical_handlers_with_explicit_research_factory_injection",
        "fictional_only": True,
        "capability": capability,
        "candidate": candidate,
        "output_mode": mode,
        "fixture_variant": fixture_variant,
        "model_sha256": model.sha256,
        "production_factory_tested": False,
        "production_admitted": False,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "ga_ready": False,
        "routes": ["/api/local-agent/preview", "/api/local-agent/run"],
        "implementation_sha256": hashlib.sha256(
            (ROOT / "legal/fast_interchange/compact_cpu.py").read_bytes()
        ).hexdigest(),
    }
    started = time.monotonic()
    try:
        report["warm"] = LocalAgentRuntime(client).warm()
        assert worker.completed_requests == 1
        assert client.last_raw_response == ""
        # Prove the normal hardware integration does not silently accept this
        # new ABI. A separate signed native runtime integration is still needed.
        unadapted = preview(host)
        assert unadapted["hardware_readiness"]["blockers"]
        report["unadapted_hardware_blockers"] = unadapted["hardware_readiness"]["blockers"]

        def research_cpu_readiness(_runtime):
            available = psutil.virtual_memory().available
            blockers = [] if available >= MAX_RESIDENT_BYTES + 1024**3 else ["insufficient_memory"]
            return {
                "status": "research_cpu_only",
                "blockers": blockers,
                "available_memory_bytes": available,
                "max_resident_bytes": MAX_RESIDENT_BYTES,
                "production_admitted": False,
                "review_required": True,
            }

        monkeypatch.setattr(api, "_local_agent_hardware_readiness", research_cpu_readiness)
        selected = preview(host)
        assert not selected["hardware_readiness"]["blockers"]
        assert selected["source_cards"][0]["snippet"] == host["text"]
        assert selected["model_admission"]["production_admitted"] is False
        body = approved_body(host, selected)
        response = run(host, body)
        report["http_status"] = response.status_code
        report["payload"] = response.json()
        report["raw_fictional_response"] = client.last_raw_response
        if mode == "extract":
            report["selection_report"] = client.last_selection_report
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed_review_required"
        assert payload["review_required"] is True
        assert payload["output_validation"]["source_spans"]
        if fixture_variant == "embedded_quote":
            assert '"an attachment is missing"' in payload["answer"]
        assert payload["citations"][0]["source_reference"] == selected["source_refs"][0]
        assert str(host["root"]) not in response.text
        assert worker._token not in response.text
        assert worker.completed_requests == 2  # one non-matter warm, one approved generation
        assert run(host, body).status_code == 409  # no replayed model generation
        wrong_matter = {**host["body"], "matter_id": "another-fictional-matter"}
        assert (
            host["client"]
            .post("/api/local-agent/preview", json=wrong_matter, headers=host["headers"])
            .status_code
            == 409
        )
        assert worker.completed_requests == 2
        audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
        raw = audit.path.read_bytes()
        assert host["text"].encode() not in raw
        state = audit.encryptor.decrypt_json(json.loads(raw))
        assert [row["action"] for row in state["events"]] == [
            "preview",
            "preview",
            "dispatch",
            "result",
        ]
        report.update(
            canonical_handler_assertions_passed=True,
            audit_encrypted=True,
            replay_denied=True,
            wrong_matter_denied=True,
            model_process_peak_resident_bytes=worker.peak_resident_bytes,
            semantic_quality_review="not_accepted_from_quote_binding",
        )
    finally:
        worker.close()
        report["owned_worker_stopped"] = worker._process is None
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

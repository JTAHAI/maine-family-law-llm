"""Canonical failure serialization, audit and consumed approval; fictional only."""

import json

import pytest
from test_fast_interchange_host_source_binding import approved_body, preview, run
from test_fast_interchange_host_source_binding import bound_host as bound_host

from app.services.local_agent_context_service import LocalAgentAuditStore
from legal.fast_interchange.compact_cpu import LocalModelError


@pytest.mark.parametrize(
    "exception_detail",
    [
        "PRIVATE_MODEL_EXCEPTION_CANARY",
        "C:\\private\\records\\never-display.txt",
    ],
)
def test_integrity_failure_returns_safe_recovery_and_preserves_records(
    bound_host, monkeypatch, exception_detail
):
    host = bound_host
    original = host["path"].read_bytes()

    def corrupted(_prompt):
        raise LocalModelError("fast_interchange_compact_model_integrity_failed", exception_detail)

    monkeypatch.setattr(host["worker"], "generate_response", corrupted)
    prepared = preview(host)
    body = approved_body(host, prepared)
    response = run(host, body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "local_model_failed_review_required"
    assert payload["warnings"] == ["fast_interchange_compact_model_integrity_failed"]
    assert "Restore the original verified model package" in payload["answer"]
    assert "Do not edit its receipt" in payload["answer"]
    assert exception_detail not in json.dumps(payload)
    assert payload["output_grounding"]["status"] == "withheld"
    assert payload["review_required"] is True
    assert host["path"].read_bytes() == original
    assert run(host, body).status_code == 409
    audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
    raw = audit.path.read_bytes()
    assert original not in raw and exception_detail.encode() not in raw
    events = audit.encryptor.decrypt_json(json.loads(raw))["events"]
    assert "result" in [event["action"] for event in events]

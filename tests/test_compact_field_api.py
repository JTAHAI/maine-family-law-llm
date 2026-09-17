"""Canonical contract tests with span/hardware doubles, not live inference."""

import json
from hashlib import sha256

import pytest
from test_compact_field_client import SpanDouble
from test_fast_interchange_host_source_binding import approved_body, preview, run
from test_fast_interchange_host_source_binding import bound_host as bound_host

from app.services.local_agent_context_service import LocalAgentAuditStore
from legal.fast_interchange.compact_field_client import CompactFieldResearchClient
from maine_family_law_llm import api


@pytest.fixture
def field_host(bound_host, monkeypatch):
    host = bound_host
    text = "The fictional session was scheduled for 09:00 but began at 09:25."
    host["path"].write_text(text, encoding="utf-8")
    host["row"]["source_hash"] = sha256(host["path"].read_bytes()).hexdigest()
    identity = api._record_capability_identity.set(host["owner"])
    try:
        token = api._record_open_token(host["root"], "REC-1", "REC-1.txt")
    finally:
        api._record_capability_identity.reset(identity)
    host["body"]["source_refs"][0].update(
        source_sha256=host["row"]["source_hash"],
        text_sha256=sha256(text.encode()).hexdigest(),
        end_offset=len(text),
        record_token=token,
    )
    worker = SpanDouble()
    client = CompactFieldResearchClient(
        worker, field_type="clock_time", basis="reported_event", research_only=True
    )
    monkeypatch.setattr(api, "build_local_client", lambda **kwargs: client)
    monkeypatch.setattr(
        api,
        "_local_agent_hardware_readiness",
        lambda runtime: dict(blockers=[], review_required=True),
    )
    host["body"].update(
        question="When did the session begin?",
        provider=client.provider_id,
        model=client.model_name,
        endpoint="http://127.0.0.1:1",
    )
    host.update(span_worker=worker, field_client=client, text=text)
    return host


def test_canonical_exact_field_full_source_and_encrypted_audit(field_host):
    host = field_host
    prepared = preview(host)
    assert prepared["model_admission"]["field_type"] == "clock_time"
    assert prepared["model_admission"]["basis"] == "reported_event"
    assert prepared["source_cards"][0]["snippet"] == host["text"]
    body = approved_body(host, prepared)
    response = run(host, body)
    assert response.status_code == 200
    result = response.json()
    assert result["output_validation"]["fields"][0]["candidate"]["text"] == "09:25"
    assert "Not a verified fact" in result["answer"] and not result["grounded"]
    assert result["citations"][0]["snippet"] == host["text"]
    assert result["citations"][0]["source_reference"] == prepared["source_refs"][0]
    assert run(host, body).status_code == 409
    assert host["span_worker"].calls == 1
    audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
    raw = audit.path.read_bytes()
    assert host["text"].encode() not in raw
    events = audit.encryptor.decrypt_json(json.loads(raw))["events"]
    assert [e["action"] for e in events] == ["preview", "dispatch", "result"]
    assert events[-1]["receipt_sha256"] == result["provenance_receipt"]["receipt_sha256"]


@pytest.mark.parametrize(
    "header,value",
    [("X-User-Role", "attorney"), ("X-Tenant-Id", "other"), ("X-MFLL-Client-Session", "b" * 48)],
)
def test_changed_identity_cannot_use_field_approval(field_host, header, value):
    host = field_host
    body = approved_body(host, preview(host))
    response = run(host, body, {**host["headers"], header: value})
    assert response.status_code in {403, 409}
    assert host["text"] not in response.text
    assert host["span_worker"].calls == 0


def test_binding_change_invalidates_canonical_approval(field_host):
    host = field_host
    body = approved_body(host, preview(host))
    host["field_client"].model_binding["basis"] = "source_field"
    assert run(host, body).status_code == 409
    assert host["span_worker"].calls == 0


def test_wrong_matter_and_stale_record_fail_closed(field_host):
    host = field_host
    body = approved_body(host, preview(host))
    wrong = dict(body, matter_id="other-fictional-matter")
    assert run(host, wrong).status_code == 409
    host["path"].write_text("Fictional changed record.", encoding="utf-8")
    assert run(host, body).status_code in {403, 409}
    assert host["span_worker"].calls == 0


def test_safe_abstention_retains_original_source_card(field_host):
    host = field_host
    host["span_worker"].selection = None
    result = run(host, approved_body(host, preview(host))).json()
    assert "does not establish absence" in result["answer"]
    assert result["output_grounding"]["quoted_text_checked"] is False
    assert result["citations"][0]["snippet"] == host["text"]

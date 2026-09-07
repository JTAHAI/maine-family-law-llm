"""Browser-bound private chat works without weakening the legal authority gate."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import local_agent_context_service as context_module
from app.services.local_agent_context_service import LocalAgentContextError
from maine_family_law_llm import api
from maine_family_law_llm.case_corpus_builder import create_sample_case_build


@pytest.mark.parametrize("route", ["/ask", "/ask/stream"])
def test_browser_private_chat_with_unavailable_authority(tmp_path, monkeypatch, route):
    result = create_sample_case_build(
        Path(__file__).resolve().parents[1], output_root=tmp_path / "fictional-build",
        case_name="FICTIONAL 802 boundary matter",
    )
    monkeypatch.setattr(api, "active_case_root", lambda: result.case_root)
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    calls = []

    def unavailable_authority():
        calls.append(True)
        raise ValueError("authority_data_root_must_be_external")

    monkeypatch.setattr(context_module, "AuthorityProductService", unavailable_authority)
    monkeypatch.setattr(api, "AuthorityProductService", unavailable_authority)
    headers = {"X-MFLL-Client-Session": "a" * 48,
               "X-User-Role": "reviewer", "X-Tenant-Id": "fictional-802"}
    with TestClient(api.app) as client:
        response = client.post(route, headers=headers, json={
            "question": "What do the fictional records say about school attendance and records access?",
            "search_mode": "my_records", "child_impact_lens": True,
            "session_id": "fictional-802-browser-session",
        })
    assert response.status_code == 200
    if route.endswith("/stream"):
        frame = next(frame for frame in response.text.split("\n\n")
                     if frame.startswith("event: result\n"))
        payload = json.loads(frame.split("data: ", 1)[1])["payload"]
    else:
        payload = response.json()
    assert payload["failure_class"] == "none"
    assert payload["response_kind"] == "private_record_answer"
    assert payload["source_card_count"] > 0
    assert payload["review_required"] is True
    assert payload["local_agent_source_refs"]
    assert all(ref["lane"] == "private_record" for ref in payload["local_agent_source_refs"])
    assert all(ref["record_token"] for ref in payload["local_agent_source_refs"])
    assert not calls
    assert str(result.case_root) not in response.text


def test_lazy_legal_authority_still_fails_closed(monkeypatch):
    calls = []

    def unavailable_authority():
        calls.append(True)
        raise ValueError("untrusted_authority_root")

    monkeypatch.setattr(context_module, "AuthorityProductService", unavailable_authority)
    service = context_module.LocalAgentContextService(record_loader=lambda _token: {})
    assert service._authority_rows(set()) == {}
    assert not calls
    with pytest.raises(LocalAgentContextError, match="local_agent_authority_unavailable"):
        service._authority_rows({"FICTIONAL-MAINE-AUTHORITY"})
    assert len(calls) == 1

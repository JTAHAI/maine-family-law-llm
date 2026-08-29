"""Canonical host UI/API contract and matter-scoped cancellation tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_fast_interchange_host_source_binding import (  # noqa: F401
    RecordingClient,
    approved_body,
    bound_host,
    preview,
)

from app.services.local_agent_context_service import LocalAgentAuditStore
from app.services.local_agent_run_service import LocalAgentRunStore
from legal.agent_runtime.providers import LocalModelError
from maine_family_law_llm import api


@pytest.fixture
def controlled_host(bound_host, monkeypatch):  # noqa: F811 - pytest fixture injection
    class ControlledClient(RecordingClient):
        model_binding = {
            "release_id": "fictional-release",
            "capability": "evidence_review",
            "release_fingerprint": "a" * 64,
            "catalog_sha256": "b" * 64,
            "evidence_basis": "synthetic_test_only",
            "review_required": True,
        }

        def __init__(self):
            super().__init__()
            self.canceled = Event()
            self.entered = Event()
            self.delay = False

        def cancel(self):
            self.canceled.set()
            return {"status": "canceling" if self.entered.is_set() else "canceled"}

        def generate_response(self, prompt):
            self.entered.set()
            if self.delay:
                assert self.canceled.wait(timeout=8)
            if self.canceled.is_set():
                raise LocalModelError("fast_interchange_generation_canceled", "Canceled.")
            return super().generate_response(prompt)

    worker = ControlledClient()
    monkeypatch.setattr(api, "build_local_client", lambda **kwargs: worker)
    monkeypatch.setattr(api, "_local_agent_runs", LocalAgentRunStore())
    bound_host["worker"] = worker
    return bound_host


def cancel(host, prepared, **changes):
    return host["client"].post(
        "/api/local-agent/cancel",
        headers=changes.get("headers", host["headers"]),
        json={
            "matter_id": changes.get("matter_id", host["body"]["matter_id"]),
            "run_id": prepared["context_manifest"]["run_id"],
        },
    )


def test_preview_binds_admission_and_cancel_before_dispatch(controlled_host):
    host = controlled_host
    prepared = preview(host)
    assert prepared["cancellation_supported"] is True
    assert prepared["model_admission"]["evidence_basis"] == "synthetic_test_only"
    assert cancel(host, prepared).json()["status"] == "canceled"
    response = host["client"].post(
        "/api/local-agent/run", json=approved_body(host, prepared), headers=host["headers"]
    )
    assert response.status_code == 409 and "generation_canceled" in response.text
    assert not host["worker"].prompts


@pytest.mark.parametrize(
    "change,value",
    [
        ("matter_id", "wrong-matter"),
        ("X-Tenant-Id", "wrong-tenant"),
        ("X-User-Role", "viewer"),
        ("X-MFLL-Client-Session", "c" * 48),
    ],
)
def test_cancel_fails_closed_across_matter_role_tenant_and_session(controlled_host, change, value):
    host = controlled_host
    prepared = preview(host)
    options = (
        {"matter_id": value}
        if change == "matter_id"
        else {"headers": {**host["headers"], change: value}}
    )
    response = cancel(host, prepared, **options)
    assert response.status_code in {403, 404, 409}
    assert not host["worker"].canceled.is_set()


def test_running_cancel_withholds_answer_and_is_audited(controlled_host):
    host = controlled_host
    host["worker"].delay = True
    prepared = preview(host)
    with ThreadPoolExecutor(max_workers=1) as pool:
        work = pool.submit(
            host["client"].post,
            "/api/local-agent/run",
            json=approved_body(host, prepared),
            headers=host["headers"],
        )
        assert host["worker"].entered.wait(timeout=5)
        assert cancel(host, prepared).status_code == 200
        response = work.result(timeout=5)
    assert response.status_code == 409 and "generation_canceled" in response.text
    assert not host["worker"].prompts
    audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
    import json

    raw = audit.path.read_bytes()
    assert host["text"].encode() not in raw
    events = audit.encryptor.decrypt_json(json.loads(raw))["events"]
    assert {"preview", "dispatch", "cancel_requested", "canceled"} <= {
        row["action"] for row in events
    }


def test_catalog_changed_after_preview_requires_new_approval(controlled_host):
    host = controlled_host
    prepared = preview(host)
    host["worker"].model_binding = {**host["worker"].model_binding, "catalog_sha256": "d" * 64}
    response = host["client"].post(
        "/api/local-agent/run", json=approved_body(host, prepared), headers=host["headers"]
    )
    assert response.status_code == 409
    assert "approval_context_changed" in response.text
    assert not host["worker"].prompts


def test_no_private_model_paths_or_tokens_in_preview_or_results(controlled_host):
    host = controlled_host
    prepared = preview(host)
    response = host["client"].post(
        "/api/local-agent/run", json=approved_body(host, prepared), headers=host["headers"]
    )
    assert response.status_code == 200
    assert response.json()["review_required"] is True
    assert response.json()["citations"][0]["snippet"] == host["text"]
    assert str(host["root"]) not in response.text


def test_production_mirrors_expose_real_cancellation_and_admission():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for relative in ("api.py", "ui/workbench.js"):
        assert (root / "maine_family_law_llm" / relative).read_bytes() == (
            root / "src/maine_family_law_llm" / relative
        ).read_bytes()
    js = (root / "maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "/api/local-agent/cancel" in js and "Cancel generation" in js
    assert "preview.model_admission.release_fingerprint" in js
    assert "err.safeCode === 'fast_interchange_generation_canceled'" in js
    assert "does not cancel generation" in js  # Honest limitation for unrelated providers.

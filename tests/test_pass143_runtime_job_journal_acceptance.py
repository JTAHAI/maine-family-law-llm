from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.production import app as production_app
from legal.runtime.job_journal import JobJournalError, JobJournalReceiptStore, collect_job_journal
from maine_family_law_llm import api


class _FictionalKernel:
    def list_jobs(self, *, matter_id: str, limit: int) -> list[dict]:
        assert matter_id == "fictional-matter"
        assert limit == 500
        return [
            {
                "job_id": "job-" + "a" * 32,
                "job_type": "local_ocr",
                "status": "completed",
                "progress": 1.0,
                "attempt": 1,
                "payload": {"record_path": r"C:\\fictional\\private.pdf", "prompt": "private fictional text"},
                "result": {"private_result": "fictional outcome"},
                "created_at": "2026-08-27T00:00:00Z",
                "updated_at": "2026-08-27T00:01:00Z",
                "completed_at": "2026-08-27T00:01:00Z",
            },
            {
                "job_id": "job-" + "b" * 32,
                "job_type": "model_review",
                "status": "cancel_requested",
                "progress": 0.5,
                "attempt": 2,
                "payload": {"question": "private fictional question"},
                "error": {"detail": "private fictional error"},
                "created_at": "2026-08-27T00:00:00Z",
                "updated_at": "2026-08-27T00:02:00Z",
                "completed_at": None,
            },
        ]

    def events(self, job_id: str) -> list[dict]:
        if job_id.endswith("a" * 32):
            return [{"event_id": 1, "event_type": "job_created", "payload": {"private": "hidden"}, "created_at": "2026-08-27T00:00:00Z"}, {"event_id": 2, "event_type": "job_completed", "created_at": "2026-08-27T00:01:00Z"}]
        return [{"event_id": 3, "event_type": "cancel_requested", "created_at": "2026-08-27T00:02:00Z"}]


def test_job_journal_hashes_private_inputs_and_preserves_cancellation_retry_state(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    journal = collect_job_journal(kernel=_FictionalKernel(), matter_id="fictional-matter")
    assert journal["counts"] == {"total": 2, "active": 1, "cancelled": 0, "retried": 1, "terminal": 1}
    assert journal["job_inputs_exposed"] is False
    assert journal["job_results_exposed"] is False
    assert "private fictional" not in str(journal)
    assert r"C:\fictional" not in str(journal)
    assert journal["jobs"][1]["cancellation_requested"] is True
    assert journal["jobs"][1]["attempt"] == 2
    assert journal["jobs"][0]["stage"] == "job_completed"

    store = JobJournalReceiptStore(matter, encryption_key="fictional-job-journal-key")
    first = store.record(journal, actor_role="reviewer", tenant_id="fictional-tenant")
    second = store.record(journal, actor_role="reviewer", tenant_id="fictional-tenant")
    assert first["audit_receipt"]["journal_id"] != second["audit_receipt"]["journal_id"]
    assert store.verify()["status"] == "pass"
    assert b"private fictional" not in store.path.read_bytes()
    with pytest.raises(JobJournalError, match="tenant_mismatch"):
        store.record(journal, actor_role="reviewer", tenant_id="other-tenant")


def test_canonical_job_journal_route_and_production_ui_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-job-journal-key")
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    monkeypatch.setattr(api, "_case_id", lambda _root: "fictional-matter")
    monkeypatch.setattr(api, "get_runtime_kernel", lambda: _FictionalKernel())
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "e" * 48,
    }
    client = TestClient(api.app)
    response = client.get("/api/runtime/job-journal", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["matter_scope"] == "active_matter_only"
    assert payload["audit_receipt"]["journal_id"].startswith("journal_")
    assert payload["jobs"][1]["cancellation_requested"] is True
    assert "private fictional" not in response.text

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    assert client.get("/api/runtime/job-journal", headers=headers).status_code == 409
    assert client.get("/api/runtime/job-journal", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}).status_code == 403

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        directory = root / relative
        assert 'id="runtime-job-journal-refresh"' in (directory / "workbench.html").read_text(encoding="utf-8")
        assert "/api/runtime/job-journal" in (directory / "workbench.js").read_text(encoding="utf-8")

    registered = {
        (method, str(getattr(route, "path", "")))
        for route in production_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }
    report = EndpointInventory().compare_to_registered(registered, surface="production")
    assert report["status"] == "pass", report
    assert ("GET", "/api/runtime/job-journal") in registered

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.print_review import PrintReviewStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def _payload() -> dict:
    return {
        "preview_id": "print_preview_001",
        "title": "Fictional evidence review",
        "confidentiality_marking": "CONFIDENTIAL — REVIEW REQUIRED",
        "source_hash": HASH_A,
        "source_ref": {"record_id": "record_001", "span": "p. 1"},
        "summary": "Fictional source-bound print review; not a finding.",
        "privacy_acknowledged": True,
    }


def test_pass179_print_preview_is_encrypted_accessible_and_never_silent(tmp_path: Path) -> None:
    store = PrintReviewStore(tmp_path, encryption_key="0123456789abcdef")
    created = store.create(_payload())
    assert created["status"] == "review_required"
    assert created["silent_print"] is False
    assert created["accessibility"] == {"high_contrast_print": True, "headers": True, "source_review_footer": True}
    opened = store.get("print_preview_001")
    assert opened["preview"]["source_ref"]["record_id"] == "record_001"
    requested = store.request_print("print_preview_001", {"privacy_acknowledged": True})
    assert requested["system_print_invoked"] is False
    assert store.inventory()["previews"][0]["print_request_count"] == 1
    encrypted = next((tmp_path / "51_PRINT_REVIEW").glob("*.enc"))
    assert b"Fictional source-bound" not in encrypted.read_bytes()
    with pytest.raises(IntakeWorkbenchError, match="privacy_acknowledgement_required"):
        store.request_print("print_preview_001", {"privacy_acknowledged": False})


def test_pass179_production_routes_deny_viewer_and_ship_print_accessibility(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "j" * 32}
    assert client.post("/api/print-review/previews", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass179-denied"}, json=_payload()).status_code == 403
    created = client.post("/api/print-review/previews", headers={**headers, "X-MFLL-Idempotency-Key": "pass179-create"}, json=_payload())
    assert created.status_code == 200, created.text
    request = client.post("/api/print-review/previews/print_preview_001/request-print", headers={**headers, "X-MFLL-Idempotency-Key": "pass179-request"}, json={"privacy_acknowledged": True})
    assert request.status_code == 200 and request.json()["system_print_invoked"] is False
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "print-review-controls" in text and "/api/print-review/previews" in text
        assert "@media print" in text and "window.print()" in text
        assert "no silent print" in text

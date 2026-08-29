from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api.production import app as production_app
from legal.matter.archival_pdf_export import ArchivalPdfExportStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def _payload() -> dict:
    return {
        "export_id": "pdf_export_001",
        "title": "Fictional evidence review",
        "acknowledged_pdf_a_limitations": True,
        "items": [
            {
                "item_id": "pdf_item_001",
                "source_hash": HASH_A,
                "source_ref": {"record_id": "record_001", "span": "p. 1"},
                "summary": "Fictional source-bound review summary; no factual or legal conclusion.",
            }
        ],
    }


def test_pass177_creates_readable_pdf_with_honest_pdfa_limitation(tmp_path: Path) -> None:
    store = ArchivalPdfExportStore(tmp_path, encryption_key="0123456789abcdef")
    created = store.create(_payload())
    assert created["status"] == "review_required"
    assert created["pdf_a_conformance"] == "not_verified"
    assert created["automatic_download"] is False
    assert created["receipt"]["pdf_sha256"]
    reader = PdfReader(io.BytesIO(base64.b64decode(created["export"]["pdf_base64"])))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "NOT A FILING" in text
    assert "PDF/A conformance is NOT verified" in text
    assert "record_001" in text and HASH_A in text
    encrypted = next((tmp_path / "49_ARCHIVAL_PDF_EXPORTS").glob("*.enc"))
    assert b"Fictional source-bound" not in encrypted.read_bytes()
    with pytest.raises(IntakeWorkbenchError, match="limitations_acknowledgement_required"):
        store.create({**_payload(), "export_id": "pdf_export_002", "acknowledged_pdf_a_limitations": False})


def test_pass177_production_route_denies_viewer_and_ships_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "h" * 32}
    assert client.post("/api/archival-pdf/exports", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass177-denied"}, json=_payload()).status_code == 403
    created = client.post("/api/archival-pdf/exports", headers={**headers, "X-MFLL-Idempotency-Key": "pass177-create"}, json=_payload())
    assert created.status_code == 200, created.text
    assert created.json()["receipt"]["pdf_a_status"] == "not_verified"
    inventory = client.get("/api/archival-pdf/exports", headers=headers)
    assert inventory.status_code == 200 and inventory.json()["exports"][0]["export_id"] == "pdf_export_001"
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "archival-pdf-review-controls" in text
        assert "/api/archival-pdf/exports" in text
        assert "PDF/A conformance not verified" in text

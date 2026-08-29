from __future__ import annotations

import base64
import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.structured_evidence_export import StructuredEvidenceExportStore
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def _payload() -> dict:
    return {
        "export_id": "evidence_export_001",
        "scope_id": "review_scope_001",
        "formats": ["csv", "json"],
        "privacy_acknowledged": True,
        "rows": [
            {
                "evidence_id": "evidence_001",
                "source_hash": HASH_A,
                "source_ref": {"record_id": "record_001", "span": "p. 1"},
                "review_state": "unresolved",
                "label": "Fictional source-bound observation; not a finding.",
            }
        ],
    }


def test_pass178_csv_json_exports_keep_schema_hash_locator_and_review_state(tmp_path: Path) -> None:
    store = StructuredEvidenceExportStore(tmp_path, encryption_key="0123456789abcdef")
    created = store.create(_payload())
    assert created["status"] == "review_required"
    assert created["raw_matter_store_exported"] is False
    assert created["automatic_download"] is False
    exported_json = json.loads(base64.b64decode(created["export"]["artifacts"]["json"]["base64"]))
    assert exported_json["schema"].endswith("package.v1")
    assert exported_json["evidence"][0]["source_ref"]["record_id"] == "record_001"
    assert exported_json["evidence"][0]["review_state"] == "unresolved"
    csv_rows = list(csv.DictReader(io.StringIO(base64.b64decode(created["export"]["artifacts"]["csv"]["base64"]).decode())))
    assert csv_rows[0]["source_hash"] == HASH_A
    assert csv_rows[0]["review_required"] == "true"
    encrypted = next((tmp_path / "50_STRUCTURED_EVIDENCE_EXPORTS").glob("*.enc"))
    assert b"Fictional source-bound" not in encrypted.read_bytes()
    with pytest.raises(IntakeWorkbenchError, match="privacy_acknowledgement_required"):
        store.create({**_payload(), "export_id": "evidence_export_002", "privacy_acknowledged": False})


def test_pass178_production_route_denies_viewer_and_ships_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "i" * 32}
    assert client.post("/api/evidence-exports/structured", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass178-denied"}, json=_payload()).status_code == 403
    created = client.post("/api/evidence-exports/structured", headers={**headers, "X-MFLL-Idempotency-Key": "pass178-create"}, json=_payload())
    assert created.status_code == 200, created.text
    assert set(created.json()["export"]["artifacts"]) == {"csv", "json"}
    inventory = client.get("/api/evidence-exports/structured", headers=headers)
    assert inventory.status_code == 200 and inventory.json()["exports"][0]["row_count"] == 1
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "structured-evidence-export-controls" in text
        assert "/api/evidence-exports/structured" in text
        assert "no raw matter database export" in text

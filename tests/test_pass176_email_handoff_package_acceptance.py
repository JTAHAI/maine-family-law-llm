from __future__ import annotations

import base64
import io
import zipfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.email_integrity import EmailIntegrityStore
from legal.matter.intake_workbench import IntakeWorkbenchError
from maine_family_law_llm import api as local_api


ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64
HASH_B = "b" * 64


def _export_payload() -> dict:
    return {
        "exports": [
            {
                "export_id": "email_export_001",
                "source_hash": HASH_A,
                "header_hash": HASH_B,
                "attachment_hashes": [HASH_A],
                "format": "eml",
                "source_ref": {"record_id": "record_001", "source_hash": HASH_A},
            }
        ]
    }


def _package_payload() -> dict:
    return {
        "package_id": "email_package_001",
        "export_ids": ["email_export_001"],
        "recipient_label": "Fictional reviewer",
        "subject": "Fictional review-only handoff",
        "privacy_acknowledged": True,
    }


def test_pass176_local_eml_zip_package_is_review_only_and_encrypted(tmp_path: Path) -> None:
    store = EmailIntegrityStore(tmp_path, encryption_key="0123456789abcdef")
    store.add(_export_payload())
    package = store.build_handoff_package(_package_payload())

    assert package["status"] == "review_required"
    assert package["mail_send"] is False
    assert package["automatic_download"] is False
    assert package["receipt"]["external_delivery"] == "not_performed"

    message = BytesParser(policy=policy.default).parsebytes(
        base64.b64decode(package["package"]["eml_base64"])
    )
    assert message["X-MFL-Review-Required"] == "true"
    assert "No email was sent" in message.get_body(preferencelist=("plain",)).get_content()
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(package["package"]["zip_base64"])))
    assert set(archive.namelist()) == {"review-handoff.eml", "review-manifest.json"}
    assert package["package"]["manifest"]["exports"][0]["source_ref"]["record_id"] == "record_001"
    encrypted = next((tmp_path / "40_EMAIL_INTEGRITY").glob("*.enc"))
    assert b"Fictional reviewer" not in encrypted.read_bytes()
    with pytest.raises(IntakeWorkbenchError, match="privacy_acknowledgement_required"):
        store.build_handoff_package({**_package_payload(), "package_id": "email_package_002", "privacy_acknowledged": False})


def test_pass176_production_route_denies_viewer_and_ships_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "f" * 32,
    }
    assert client.post(
        "/api/email-integrity/exports",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass176-export"},
        json=_export_payload(),
    ).status_code == 200
    denied = client.post(
        "/api/email-integrity/handoff-package",
        headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass176-denied"},
        json=_package_payload(),
    )
    assert denied.status_code == 403
    created = client.post(
        "/api/email-integrity/handoff-package",
        headers={**headers, "X-MFLL-Idempotency-Key": "pass176-create"},
        json=_package_payload(),
    )
    assert created.status_code == 200, created.text
    assert created.json()["receipt"]["external_delivery"] == "not_performed"
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "email-handoff-package-controls" in text
        assert "/api/email-integrity/handoff-package" in text
        assert "no mail sent" in text

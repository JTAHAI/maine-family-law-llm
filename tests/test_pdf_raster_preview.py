"""Fictional PDF render, encrypted IPC, capability, audit and failure boundaries."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fpdf import FPDF
from PIL import Image

from legal.document_intelligence import pdf_preview as preview
from legal.document_intelligence import service
from maine_family_law_llm import api


def fictional_pdf() -> bytes:
    pdf = FPDF()
    for page in (1, 2):
        pdf.add_page()
        pdf.set_font("Helvetica", size=22)
        pdf.set_text_color(20, 60, 90)
        pdf.cell(0, 15, txt=f"FICTIONAL PAGE {page} - NO REAL MATTER DATA")
        pdf.set_fill_color(220 if page == 1 else 20, 60, 200)
        pdf.rect(25, 45, 80, 55, style="F")
    output = pdf.output(dest="S")
    return output.encode("latin-1") if isinstance(output, str) else bytes(output)


def test_real_worker_renders_distinct_bounded_png_pages():
    source = fictional_pdf()
    results = [preview.render_pdf_preview(source, page) for page in (1, 2)]
    assert results[0]["sha256"] != results[1]["sha256"]
    for page, result in enumerate(results, 1):
        assert result["page"] == page and result["page_count"] == 2
        assert result["source_sha256"] == hashlib.sha256(source).hexdigest()
        assert result["review_required"] is True
        with Image.open(io.BytesIO(result["data"])) as image:
            assert image.format == "PNG" and max(image.size) <= preview.MAX_EDGE
            assert len(image.getcolors(image.width * image.height)) > 2


def test_private_ipc_is_encrypted_and_cleaned(monkeypatch):
    real = service._run_worker
    paths = []

    def observe(adapter, path, *, timeout, worker_env):
        assert adapter == "pdf_preview" and timeout == 25
        paths.append(path)
        raw = path.read_bytes()
        assert b"%PDF-" not in raw and b"FICTIONAL" not in raw
        assert preview.KEY_ENV not in os.environ
        reply = real(adapter, path, timeout=timeout, worker_env=worker_env)
        assert reply["status"] == "pass"
        assert "png" not in reply and "source_sha256" not in reply
        assert "FICTIONAL" not in json.dumps(reply)
        return reply

    monkeypatch.setattr(service, "_run_worker", observe)
    preview.render_pdf_preview(fictional_pdf(), 1)
    assert paths and all(not p.parent.exists() for p in paths)


@pytest.mark.parametrize("page", [0, -1, 100001, True, "1"])
def test_page_input_bounds(page):
    with pytest.raises(preview.PdfPreviewError, match="record_preview_page_invalid"):
        preview.render_pdf_preview(fictional_pdf(), page)


@pytest.mark.parametrize("data,code", [(b"<html>EXECUTE</html>", "pdf_required"),
                                       (b"%PDF- broken", "render_failed")])
def test_malformed_or_mismatched_source_fails_closed(data, code):
    with pytest.raises(preview.PdfPreviewError, match=code):
        preview.render_pdf_preview(data, 1)


def test_page_out_of_actual_document_range():
    with pytest.raises(preview.PdfPreviewError, match="record_preview_page_invalid"):
        preview.render_pdf_preview(fictional_pdf(), 3)


def test_oversized_pdf_rejected_before_worker(monkeypatch):
    monkeypatch.setattr(preview, "MAX_PDF_BYTES", 8)
    with pytest.raises(preview.PdfPreviewError, match="input_too_large"):
        preview.render_pdf_preview(b"%PDF- oversized", 1)


def test_busy_and_timeout_release_slot_and_cleanup(monkeypatch):
    preview._SLOT.acquire()
    try:
        with pytest.raises(preview.PdfPreviewError, match="record_preview_busy"):
            preview.render_pdf_preview(fictional_pdf(), 1)
    finally:
        preview._SLOT.release()
    paths = []

    def timeout(adapter, path, **kwargs):
        paths.append(path)
        return {"status": "timeout"}

    monkeypatch.setattr(service, "_run_worker", timeout)
    for _ in range(2):
        with pytest.raises(preview.PdfPreviewError, match="record_preview_timeout"):
            preview.render_pdf_preview(fictional_pdf(), 1)
    assert all(not p.parent.exists() for p in paths)


@pytest.mark.parametrize("fault", ["page", "source_sha256", "sha256", "dimensions", "ciphertext"])
def test_untrusted_worker_reply_cannot_rebind_page_or_source(monkeypatch, fault):
    real = service._run_worker

    def corrupt(adapter, path, *, timeout, worker_env):
        reply = real(adapter, path, timeout=timeout, worker_env=worker_env)
        key = bytes.fromhex(worker_env[preview.KEY_ENV])
        raw = base64.b64decode(reply["ciphertext"])
        result = json.loads(preview._decrypt(key, raw, preview._RESPONSE_AAD))
        if fault == "page":
            result["page"] = 2
        elif fault in {"source_sha256", "sha256"}:
            result[fault] = "0" * 64
        elif fault == "dimensions":
            result["width"] = 1000000
        modified = preview._encrypt(key, json.dumps(result).encode(), preview._RESPONSE_AAD)
        if fault == "ciphertext":
            modified = modified[:-1] + bytes([modified[-1] ^ 1])
        reply["ciphertext"] = base64.b64encode(modified).decode()
        return reply

    monkeypatch.setattr(service, "_run_worker", corrupt)
    with pytest.raises(preview.PdfPreviewError):
        preview.render_pdf_preview(fictional_pdf(), 1)


def test_worker_rejects_plaintext_and_drops_ephemeral_key(monkeypatch, tmp_path):
    path = tmp_path / "request.enc"
    path.write_bytes(fictional_pdf())
    monkeypatch.setenv(preview.KEY_ENV, "ab" * 32)
    result = preview.render_worker(path)
    assert result == {"status": "blocked", "code": "record_preview_render_failed"}
    assert preview.KEY_ENV not in os.environ
    assert str(tmp_path) not in json.dumps(result)


@pytest.fixture
def protected_pdf(monkeypatch, tmp_path):
    root = tmp_path / "FICTIONAL-matter"
    record = root / "02_PRIVATE_FORENSIC_MASTER/files/FICTIONAL.pdf"
    record.parent.mkdir(parents=True)
    data = fictional_pdf()
    record.write_bytes(data)
    row = {"evidence_id": "FICTIONAL-PDF", "private_copy_relpath": record.relative_to(root).as_posix(),
           "source_hash": hashlib.sha256(data).hexdigest(), "source_type": "pdf",
           "source_locator": record.name, "page_count": 2, "text_excerpt": "FICTIONAL indexed text"}
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _: [row])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-encryption-key-not-for-release")
    api._record_open_tokens.clear()
    owner = {"role": "reviewer", "tenant_id": "fictional-tenant", "client_session_id": "a" * 48}
    ctx = api._record_capability_identity.set(owner)
    try:
        token = api._record_open_token(root, row["evidence_id"], record.name, allowed_actions={"record_inspect"})
    finally:
        api._record_capability_identity.reset(ctx)
    headers = {"X-User-Role": owner["role"], "X-Tenant-Id": owner["tenant_id"],
               "X-MFLL-Client-Session": owner["client_session_id"]}
    yield TestClient(api.app), root, record, token, headers
    api._record_open_tokens.clear()


def test_canonical_preview_renders_audits_and_preserves_original(protected_pdf):
    client, root, record, token, headers = protected_pdf
    before = record.read_bytes()
    metadata = client.get(f"/api/records/inspect/{token}", headers=headers).json()
    assert metadata["page"] == 1 and metadata["review_required"]
    assert metadata["preview_url"] == f"/api/records/preview/{token}?page=1"
    response = client.get(metadata["preview_url"], headers=headers)
    assert response.status_code == 200, response.text[:200] if response.status_code != 200 else ""
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-mfl-source-hash"] == hashlib.sha256(before).hexdigest()
    assert response.headers["x-mfl-preview-hash"] == hashlib.sha256(response.content).hexdigest()
    assert response.headers["x-mfl-page"] == "1" and response.headers["x-mfl-page-count"] == "2"
    assert response.headers["x-mfl-review-required"] == "true"
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["content-security-policy"] == "default-src 'none'; sandbox"
    from app.services.local_agent_context_service import LocalAgentAuditStore
    store = LocalAgentAuditStore(root, encryption_key=os.environ["MAINE_MATTER_STORE_KEY"])
    encrypted = store.path.read_text()
    assert "FICTIONAL" not in encrypted and "record_pdf_preview" not in encrypted
    events = store.encryptor.decrypt_json(json.loads(encrypted))["events"]
    assert events[-1]["action"] == "record_pdf_preview"
    assert events[-1]["event_sha256"] == response.headers["x-mfl-audit-receipt"]
    assert record.read_bytes() == before
    assert not list(root.rglob("*.png"))  # Page images never persist in the matter.
    assert client.get(metadata["open_url"], headers=headers).status_code == 404  # Inspect is not open permission.


@pytest.mark.parametrize("fault,status", [("role", 404), ("tenant", 404), ("session", 404),
    ("no_headers", 403), ("invalid_role", 403), ("matter", 404), ("hash", 409),
    ("expired", 404), ("action", 404), ("encryption", 503), ("page", 422)])
def test_preview_access_boundaries(protected_pdf, monkeypatch, fault, status):
    client, root, record, token, headers = protected_pdf
    headers = dict(headers)
    page = 1
    if fault in {"role", "tenant", "session", "invalid_role"}:
        key, value = {"role": ("X-User-Role", "attorney"), "tenant": ("X-Tenant-Id", "another"),
                      "session": ("X-MFLL-Client-Session", "b" * 48),
                      "invalid_role": ("X-User-Role", "guest")}[fault]
        headers[key] = value
    elif fault == "no_headers":
        headers = {}
    elif fault == "matter":
        monkeypatch.setattr(api, "active_case_root", lambda: root.parent / "other")
    elif fault == "hash":
        record.write_bytes(b"%PDF- changed")
    elif fault == "expired":
        api._record_open_tokens[token]["created_at"] = 0
    elif fault == "action":
        api._record_open_tokens[token]["allowed_actions"] = ["record_open"]
    elif fault == "encryption":
        monkeypatch.delenv("MAINE_MATTER_STORE_KEY")
        from legal.security import local_encryption

        def unavailable():
            raise ValueError("FICTIONAL vault unavailable")

        monkeypatch.setattr(local_encryption, "default_matter_passphrase", unavailable)
    elif fault == "page":
        page = 0
    response = client.get(f"/api/records/preview/{token}?page={page}", headers=headers)
    assert response.status_code == status, response.text
    assert response.headers["content-type"] != "image/png"
    assert str(root) not in response.text and "FICTIONAL indexed text" not in response.text


def test_audit_failure_blocks_raster_release(protected_pdf):
    client, root, _, token, headers = protected_pdf
    audit = root / "40_RUNTIME/local-agent/audit.json.enc"
    audit.parent.mkdir(parents=True)
    audit.write_text('{"tampered":"FICTIONAL"}')
    response = client.get(f"/api/records/preview/{token}?page=1", headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == "record_preview_audit_unavailable"


def test_managed_vault_preview_without_environment_key(protected_pdf, monkeypatch, tmp_path):
    client, root, _, token, headers = protected_pdf
    monkeypatch.delenv("MAINE_MATTER_STORE_KEY")
    vault = tmp_path / "FICTIONAL-vault"
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(vault))
    response = client.get(f"/api/records/preview/{token}?page=1", headers=headers)
    assert response.status_code == 200, response.text[:200] if response.status_code != 200 else ""
    from app.services.local_agent_context_service import LocalAgentAuditStore
    from legal.security import local_encryption
    store = LocalAgentAuditStore(root, encryption_key=local_encryption.LocalEnvelopeEncryptor.development_default)
    assert store.encryptor.passphrase != local_encryption.LocalEnvelopeEncryptor.development_default.encode()
    # Clear the process cache: unlock the actual persisted OS-protected secret.
    local_encryption._VAULT_KEY_CACHE.clear()
    reopened = LocalAgentAuditStore(root, encryption_key=local_encryption.LocalEnvelopeEncryptor.development_default)
    assert reopened.encryptor.decrypt_json(json.loads(store.path.read_text()))["events"][-1]["action"] == "record_pdf_preview"
    keys = list(vault.iterdir())
    assert len(keys) == 1
    if os.name == "nt":
        assert keys[0].name == "master-key.dpapi"
        assert keys[0].read_bytes() != base64.urlsafe_b64decode(store.encryptor.passphrase)


def test_missing_recorded_hash_does_not_become_verified(protected_pdf, monkeypatch):
    client, root, _, token, headers = protected_pdf
    rows = api.load_case_search_records(root)
    rows[0]["source_hash"] = ""
    monkeypatch.setattr(api, "load_case_search_records", lambda _: rows)
    response = client.get(f"/api/records/preview/{token}?page=1", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "record_preview_source_hash_required"
    assert not (root / "40_RUNTIME").exists()


def test_unknown_pdf_page_count_does_not_invoke_in_process_parser(protected_pdf, monkeypatch):
    client, root, _, token, headers = protected_pdf
    rows = api.load_case_search_records(root)
    rows[0]["page_count"] = 0
    monkeypatch.setattr(api, "load_case_search_records", lambda _: rows)

    def forbidden(*args, **kwargs):
        raise AssertionError("PDF metadata must not parse untrusted content in the API")

    monkeypatch.setattr(api, "parse_bytes", forbidden)
    metadata = client.get(f"/api/records/inspect/{token}", headers=headers)
    assert metadata.status_code == 200 and metadata.json()["page_count"] == 0
    raster = client.get(metadata.json()["preview_url"], headers=headers)
    assert raster.status_code == 200 and raster.headers["x-mfl-page-count"] == "2"


def test_matter_switch_during_render_fails_closed(protected_pdf, monkeypatch):
    client, root, _, token, headers = protected_pdf
    real = preview.render_pdf_preview

    def switch(data, page):
        result = real(data, page)
        monkeypatch.setattr(api, "active_case_root", lambda: root.parent / "other")
        return result

    monkeypatch.setattr(preview, "render_pdf_preview", switch)
    response = client.get(f"/api/records/preview/{token}?page=1", headers=headers)
    assert response.status_code == 404
    assert not (root / "40_RUNTIME").exists()


def test_exactly_one_canonical_preview_route_and_shipped_assets_match():
    routes = [(r.path, method) for r in api.app.routes for method in getattr(r, "methods", [])]
    assert routes.count(("/api/records/preview/{token}", "GET")) == 1
    root = Path(__file__).resolve().parents[1]
    for relative in ("api.py", "ui/workbench.js", "ui/workbench.css"):
        assert (root / "src/maine_family_law_llm" / relative).read_bytes() == (root / "maine_family_law_llm" / relative).read_bytes()

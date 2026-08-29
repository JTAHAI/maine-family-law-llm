from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


Image = pytest.importorskip("PIL.Image")


def _headers(*, role: str = "attorney") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-pass66"}


def _routes() -> set[tuple[str, str]]:
    return {(method, getattr(route, "path", "")) for route in api_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}


def _fixture_image(case_root: Path) -> tuple[Path, str]:
    evidence = case_root / "evidence"; evidence.mkdir()
    path = evidence / "fictional-image.jpg"
    image = Image.new("RGB", (12, 8), (20, 40, 60))
    exif = Image.Exif(); exif[306] = "2026:01:02 03:04:05"; exif[271] = "FictionalMake"; exif[272] = "FictionalModel"
    image.save(path, exif=exif)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_image(client: TestClient, source_hash: str) -> None:
    response = client.post("/api/hearing-media/import", json={"media": [{"media_id": "fictional-image", "title": "Fictional image", "filename": "fictional-image.jpg", "media_kind": "image", "source_hash": source_hash, "confidentiality": "private_record"}]}, headers=_headers())
    assert response.status_code == 200


def test_pass66_inspects_image_exif_and_exposes_claim_conflicts(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    image_path, source_hash = _fixture_image(case_root)
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app); _seed_image(client, source_hash)
    response = client.post("/api/hearing-media/media/fictional-image/metadata-inspections", json={"source_file": "evidence/fictional-image.jpg", "claimed_metadata": {"captured_at": "2027-01-01", "source_hash": "f" * 64, "device_label": "Fictional reviewer label"}}, headers=_headers())
    assert response.status_code == 200
    payload = response.json(); inspection = payload["inspection"]
    assert payload["review_required"] is True
    assert payload["no_authenticity_determination"] is True
    assert inspection["media_hash"] == source_hash
    assert inspection["technical_metadata"]["width"] == 12
    assert inspection["technical_metadata"]["height"] == 8
    assert inspection["exif_metadata"]["status"] == "available"
    assert inspection["exif_metadata"]["capture_time"] == "2026:01:02 03:04:05"
    assert inspection["exif_metadata"]["gps_metadata"] == "not_present"
    assert {row["field"] for row in inspection["conflicts"]} == {"source_hash", "captured_at"}
    source = client.get(f"/api/hearing-media/media/fictional-image/metadata-inspections/{inspection['inspection_id']}", headers=_headers())
    assert source.status_code == 200
    assert source.json()["source"]["media_hash"] == source_hash
    assert image_path.read_bytes()
    encrypted_state = case_root / "23_HEARING_MEDIA_WORKBENCH" / "hearing-media-workbench.json.enc"
    assert "Fictional reviewer label" not in encrypted_state.read_text(encoding="utf-8")


def test_pass66_refuses_wrong_role_path_escape_hash_change_and_cross_matter(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "matter-a"; matter_b = tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    _path, source_hash = _fixture_image(matter_a)
    current = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: current["root"])
    client = TestClient(api_app); _seed_image(client, source_hash)
    denied = client.post("/api/hearing-media/media/fictional-image/metadata-inspections", json={"source_file": "evidence/fictional-image.jpg"}, headers=_headers(role="viewer"))
    assert denied.status_code == 403
    escaped = client.post("/api/hearing-media/media/fictional-image/metadata-inspections", json={"source_file": "../fictional-image.jpg"}, headers=_headers())
    assert escaped.status_code == 400
    changed = matter_a / "evidence" / "changed.jpg"; changed.write_bytes(b"not the imported image")
    mismatch = client.post("/api/hearing-media/media/fictional-image/metadata-inspections", json={"source_file": "evidence/changed.jpg"}, headers=_headers())
    assert mismatch.status_code == 409
    current["root"] = matter_b
    isolated = client.get("/api/hearing-media/media/fictional-image/metadata-inspections/missing", headers=_headers())
    assert isolated.status_code == 404


def test_pass66_registers_canonical_routes_and_production_control() -> None:
    assert EndpointInventory().compare_to_registered(_routes())["status"] == "pass"
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Media metadata inspection" in source
    assert "/api/hearing-media/media/${encodeURIComponent(mediaId)}/metadata-inspections" in source
    assert "Metadata does not authenticate this file" in source

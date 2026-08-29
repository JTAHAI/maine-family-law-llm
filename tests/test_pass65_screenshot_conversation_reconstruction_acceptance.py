from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


def _headers(*, role: str = "reviewer") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-pass65"}


def _routes() -> set[tuple[str, str]]:
    return {(method, getattr(route, "path", "")) for route in api_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}


def _payload(conversation_id: str = "conversation_review_001") -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "screenshots": [
            {"screenshot_id": "shot_later", "source_hash": "b" * 64, "visible_timestamp": "2026-01-02T09:00:00-05:00", "timezone": "America/New_York", "review_annotation": "Fictional later screenshot.", "order_hint": 2},
            {"screenshot_id": "shot_earlier", "source_hash": "a" * 64, "visible_timestamp": "2026-01-01T09:00:00-05:00", "timezone": "America/New_York", "review_annotation": "Fictional earlier screenshot.", "order_hint": 1},
            {"screenshot_id": "shot_unknown", "source_hash": "c" * 64, "visible_timestamp": "not_visible", "timezone": "unknown", "review_annotation": "Fictional timestamp not visible.", "order_hint": 3},
        ],
    }


def test_pass65_orders_source_bound_screenshots_and_exposes_gaps(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    response = client.post("/api/hearing-media/screenshot-conversations", json=_payload(), headers=_headers())
    assert response.status_code == 200
    payload = response.json(); reconstruction = payload["reconstruction"]
    assert payload["review_required"] is True
    assert reconstruction["no_authenticity_determination"] is True
    assert reconstruction["no_message_completeness_inference"] is True
    assert reconstruction["no_sender_identity_inference"] is True
    assert [row["screenshot_id"] for row in reconstruction["ordered_screenshots"]] == ["shot_earlier", "shot_later", "shot_unknown"]
    assert any(row["kind"] == "large_visible_timestamp_gap" for row in reconstruction["gaps"])
    assert any(row["kind"] == "not_visible" for row in reconstruction["uncertainties"])

    source = client.get("/api/hearing-media/screenshot-conversations/conversation_review_001/screenshots/shot_earlier", headers=_headers())
    assert source.status_code == 200
    assert source.json()["source"]["source_hash"] == "a" * 64
    assert source.json()["observation"]["visible_timestamp"] == "2026-01-01T09:00:00-05:00"
    listed = client.get("/api/hearing-media/screenshot-conversations", headers=_headers())
    assert listed.status_code == 200
    assert listed.json()["conversations"][0]["conversation_id"] == "conversation_review_001"

    encrypted_state = case_root / "23_HEARING_MEDIA_WORKBENCH" / "hearing-media-workbench.json.enc"
    assert "Fictional earlier screenshot." not in encrypted_state.read_text(encoding="utf-8")


def test_pass65_refuses_invalid_duplicate_cross_matter_and_wrong_role(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "matter-a"; matter_b = tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    current = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: current["root"])
    client = TestClient(api_app)
    denied = client.post("/api/hearing-media/screenshot-conversations", json=_payload(), headers=_headers(role="viewer"))
    assert denied.status_code == 403
    assert client.post("/api/hearing-media/screenshot-conversations", json=_payload(), headers=_headers()).status_code == 200
    duplicate = client.post("/api/hearing-media/screenshot-conversations", json=_payload(), headers=_headers())
    assert duplicate.status_code == 409
    invalid = client.post("/api/hearing-media/screenshot-conversations", json={"conversation_id": "bad conversation", "screenshots": []}, headers=_headers())
    assert invalid.status_code == 400
    current["root"] = matter_b
    isolated = client.get("/api/hearing-media/screenshot-conversations/conversation_review_001/screenshots/shot_earlier", headers=_headers())
    assert isolated.status_code == 404


def test_pass65_registers_production_ui_and_canonical_routes() -> None:
    assert EndpointInventory().compare_to_registered(_routes())["status"] == "pass"
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Screenshot conversation review" in source
    assert "/api/hearing-media/screenshot-conversations" in source
    assert "Screenshot source binding" in source

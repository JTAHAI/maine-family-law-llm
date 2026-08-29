from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.ops.release_pilot_hardening import PrivacySafeObservabilityStore, ReleasePilotHardeningError
from maine_family_law_llm import api


def test_local_telemetry_is_off_by_default_and_refuses_private_content(tmp_path: Path) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    store = PrivacySafeObservabilityStore(matter)

    assert store.preference()["mode"] == "off"
    skipped = store.record("retrieval", metrics={"duration_ms": 12}, labels={"status": "pass"})
    assert skipped["status"] == "not_recorded"
    assert not store.path.exists()

    with pytest.raises(ReleasePilotHardeningError, match="approval_required"):
        store.configure(mode="local_metrics", approved=False)
    with pytest.raises(ReleasePilotHardeningError, match="mode_invalid"):
        store.configure(mode="remote_export", approved=True)

    enabled = store.configure(mode="local_metrics", approved=True)
    assert enabled["mode"] == "local_metrics"
    row = store.record("retrieval", metrics={"duration_ms": 12}, labels={"component": "retrieval", "status": "pass"})
    assert row["contains_user_text"] is False
    assert store.verify()["status"] == "pass"
    with pytest.raises(ReleasePilotHardeningError, match="private_or_path"):
        store.record("error", labels={"error_class": r"C:\fictional\private.pdf"})

    disabled = store.configure(mode="off", approved=True)
    assert disabled["mode"] == "off"
    assert store.record("retrieval", metrics={"count": 1})["status"] == "not_recorded"


def test_canonical_privacy_api_and_shipped_ui_expose_explicit_local_only_choice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(api, "active_case_root", lambda: matter)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant"}
    client = TestClient(api.app)

    initial = client.get("/api/security/privacy/telemetry", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["preference"]["mode"] == "off"
    enabled = client.post(
        "/api/security/privacy/telemetry",
        headers={**headers, "Content-Type": "application/json"},
        json={"mode": "local_metrics", "approved": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["preference"]["mode"] == "local_metrics"
    assert enabled.json()["local_only"] is True
    assert enabled.json()["review_required"] is True
    disabled = client.post(
        "/api/security/privacy/telemetry",
        headers={**headers, "Content-Type": "application/json"},
        json={"mode": "off", "approved": True},
    )
    assert disabled.status_code == 200
    assert disabled.json()["preference"]["mode"] == "off"

    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui", "maine_family_law_llm/ui"):
        directory = root / relative
        html = (directory / "workbench.html").read_text(encoding="utf-8")
        script = (directory / "workbench.js").read_text(encoding="utf-8")
        assert 'id="telemetry-preference-title"' in html
        assert 'id="save-telemetry-preference"' in html
        assert "/api/security/privacy/telemetry" in script
        assert "Local telemetry is off" in script

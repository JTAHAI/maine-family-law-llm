from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.main import app
from app.api.routes import deliberation as deliberation_routes
from app.web.ui_inventory import UIViewInventory
from legal.deliberation import DeliberationHost

ROOT = Path(__file__).resolve().parents[1]


def _registered_routes() -> set[tuple[str, str]]:
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and str(path).startswith("/api"):
                registered.add((method, str(path)))
    return registered


def _host(tmp_path: Path) -> DeliberationHost:
    return DeliberationHost(project_root=ROOT, root=tmp_path / "deliberation_store")


def _headers() -> dict[str, str]:
    return {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-a"}


def test_deliberation_host_completes_quick_preset_locally(tmp_path: Path) -> None:
    host = _host(tmp_path)
    draft = host.create_run(
        {
            "preset_id": "quick_local_second_opinion",
            "matter_id": "matter-1",
            "question": "What does the local packet support?",
            "user_role": "reviewer",
            "jurisdiction": "maine",
            "desired_output": "review_required_synthesis",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "tool_call_limit": 24,
            "worker_call_limit": 24,
        }
    )
    assert draft["status"] == "draft_scope"

    confirmed = host.confirm_run(
        draft["run_id"],
        {
            "local_only": True,
            "exact_question": "What does the local packet support?",
            "included_authority_sources": [
                {
                    "source_id": "auth-1",
                    "citation": "Me. Rev. Stat. tit. 19-A, § 1653",
                    "citation_kind": "maine_statute",
                    "title": "Shared parenting statute",
                    "text": "The best interest factors are reviewed under Maine law.",
                    "authority_status": "current",
                    "freshness_status": "fresh",
                }
            ],
            "included_records": [
                {
                    "record_id": "record-1",
                    "title": "Family record note",
                    "text": "The record includes one bounded factual slice for the local review.",
                }
            ],
            "output_type": "review_required_synthesis",
        },
    )
    assert confirmed["status"] == "awaiting_local_confirmation"

    finished = host.start_run(draft["run_id"], {"local_only": True})
    assert finished["run_status"] == "completed_review_required"
    assert finished["review_required"] is True
    assert finished["synthesis"]["review_status"] == "review_required"
    assert finished["events"]
    assert finished["claims"]
    assert finished["positions"]


def test_deliberation_api_and_ui_surface_are_registered(tmp_path: Path, monkeypatch) -> None:
    host = _host(tmp_path)
    monkeypatch.setattr(deliberation_routes, "HOST", host)
    client = TestClient(app)

    presets = client.get("/api/deliberation/presets", headers=_headers())
    assert presets.status_code == 200
    assert presets.json()["review_required"] is True
    assert any(item["preset_id"] == "quick_local_second_opinion" for item in presets.json()["presets"])

    created = client.post(
        "/api/deliberation/runs",
        headers=_headers(),
        json={
            "preset_id": "quick_local_second_opinion",
            "matter_id": "matter-2",
            "question": "Is there support in the local packet?",
            "user_role": "reviewer",
            "jurisdiction": "maine",
            "desired_output": "review_required_synthesis",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "tool_call_limit": 24,
            "worker_call_limit": 24,
        },
    )
    assert created.status_code == 200
    assert created.json()["review_required"] is True

    run_id = created.json()["run_id"]
    confirmed = client.post(
        f"/api/deliberation/runs/{run_id}/confirm",
        headers=_headers(),
        json={
            "local_only": True,
            "included_authority_sources": [
                {
                    "source_id": "auth-2",
                    "citation": "Me. Rev. Stat. tit. 19-A, § 1653",
                    "title": "Shared parenting statute",
                    "text": "The best interest factors are reviewed under Maine law.",
                    "authority_status": "current",
                    "freshness_status": "fresh",
                }
            ],
            "included_records": [
                {
                    "record_id": "record-2",
                    "title": "Local note",
                    "text": "The record includes a bounded factual slice for review.",
                }
            ],
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "awaiting_local_confirmation"

    started = client.post(f"/api/deliberation/runs/{run_id}/start", headers=_headers(), json={"local_only": True})
    assert started.status_code == 200
    body = started.json()
    assert body["review_required"] is True
    assert body["run_status"] == "completed_review_required"
    assert body["synthesis"]["review_status"] == "review_required"
    assert body["events"]

    route_report = EndpointInventory().compare_to_registered(_registered_routes())
    assert route_report["status"] == "pass", route_report

    ui_report = UIViewInventory("app/web/pages").validate()
    assert ui_report["status"] == "pass", ui_report
    assert any(view["path"] == "/deliberation" for view in ui_report["views"])

    app_source = Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    assert "/deliberation" in app_source

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.api.main import app
from app.api.production import app as production_app
from app.api.routes import deliberation as deliberation_routes
from app.web.ui_inventory import UIViewInventory
from legal.deliberation import DeliberationHost
from app.services.authority_product_service import AuthorityProductService
from test_trusted_filing_review import build_filing_fixture

ROOT = Path(__file__).resolve().parents[1]


def _registered_routes() -> set[tuple[str, str]]:
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method not in {"HEAD", "OPTIONS"} and str(path).startswith("/api"):
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


def test_production_tool_grants_and_budgets_survive_restart(tmp_path: Path, monkeypatch) -> None:
    host = _host(tmp_path)
    monkeypatch.setattr(deliberation_routes, "HOST", host)
    client = TestClient(production_app)
    headers = _headers()

    def confirmed(allowed_tools, budget=1):
        create = client.post("/api/deliberation/runs", headers=headers, json={
            "matter_id": "fictional-matter", "question": "What does the fictional record say?",
            "tool_call_limit": budget, "preset_id": "quick_local_second_opinion",
        })
        assert create.status_code == 200
        run = f"/api/deliberation/runs/{create.json()['run_id']}"
        confirm = client.post(run + "/confirm", headers=headers, json={
            "local_only": True, "allowed_tools": allowed_tools,
            "included_records": [{"record_id": "seed", "text": "Fictional reviewed excerpt."}],
        })
        assert confirm.status_code == 200
        assert confirm.json()["scope_freeze"]["allowed_tools"] == allowed_tools
        return run

    def tool(run, name="records.get_slice", **kwargs):
        return client.post(run + "/tools/" + name, headers=headers, json={
            "args": {"record_id": "seed", "start": 0, "end": 9}, **kwargs,
        })

    no_grants = confirmed([])
    assert tool(no_grants).status_code == 403
    assert client.post(no_grants + "/confirm", headers=headers, json={
        "local_only": True, "allowed_tools": ["records.get_slice"],
    }).status_code == 409
    assert client.post(no_grants + "/start", headers=headers, json={"local_only": True}).json()["review_required"] is True
    first = confirmed(["records.get_slice"])
    second = confirmed(["records.get_slice"])
    assert tool(first, "authority.get_span").status_code == 403
    assert tool(first, tool_token="not-issued").status_code == 403
    assert tool(first, worker_id="system_verifier").status_code == 403
    result = tool(first)
    assert result.status_code == 200
    assert result.json()["returned_source_ids"] == ["seed"]
    assert result.json()["review_required"] is True
    assert "token_id" not in result.json()["tool_audit"]
    assert tool(second).status_code == 200  # First run did not spend this run's budget.
    per_tool = confirmed(["records.get_slice"], budget=10)
    for _ in range(3):
        assert tool(per_tool).status_code == 200
    monkeypatch.setattr(deliberation_routes, "HOST", _host(tmp_path))
    assert tool(first).status_code == 409
    assert tool(second).status_code == 409
    assert tool(per_tool).status_code == 409


def test_deliberation_claims_require_exact_support_from_the_frozen_scope(tmp_path: Path) -> None:
    host = _host(tmp_path)
    claim = "The fictional receipt records a blue envelope delivered on Tuesday."
    run_id = host.create_run({"matter_id": "fictional-matter", "question": "Review the receipt."})["run_id"]
    host.confirm_run(run_id, {
        "local_only": True,
        "included_records": [{"record_id": "receipt", "text": claim}],
        "included_authority_sources": [{"source_id": "fake", "text": claim, "freshness_status": "fresh",
                                         "authority_status": "verified_official_maine"}],
    })
    run = host._load_or_raise(run_id)
    assert host._claim_verifier_status(run, claim, [{"source_id": "receipt"}]) == "evidence_supported"
    assert host._claim_verifier_status(run, claim, [{"source_id": "invented"}]) == "unverified"
    assert host._claim_verifier_status(run, "Everything is settled forever.", [{"source_id": "receipt"}]) == "unverified"
    assert host._claim_verifier_status(run, claim, []) == "unverified"
    assert host._claim_verifier_status(run, claim, [{"source_id": "fake"}], claim_type="legal") == "unverified"
    assert host._claim_verifier_status(run, claim, [{"source_id": "receipt"}], claim_type="legal") == "unverified"


def test_deliberation_uses_admitted_text_not_caller_supplied_authority(tmp_path: Path) -> None:
    authority, _case, _doc, _source, _fact, official_text, _cite, source_id = build_filing_fixture(tmp_path)
    service = AuthorityProductService(data_root=authority)
    host = DeliberationHost(project_root=ROOT, root=tmp_path / "deliberation_store", authority_verifier=service.verify_output)
    forged = "The fictional legislature requires all filings to include a blue envelope."
    run_id = host.create_run({"matter_id": "fictional-matter", "question": "Verify the proposition."})["run_id"]
    host.confirm_run(run_id, {"local_only": True, "included_authority_sources": [{"source_id": source_id, "text": forged}]})
    run = host._load_or_raise(run_id)
    refs = [{"source_id": source_id}]
    assert host._claim_verifier_status(run, official_text, refs, claim_type="legal") == "source_supported"
    assert host._claim_verifier_status(run, forged, refs, claim_type="legal") == "unverified"

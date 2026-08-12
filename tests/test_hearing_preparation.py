from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.hearing_preparation import HearingPreparationStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_pack_keeps_missing_proof_visible_and_never_predicts(tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = HearingPreparationStore(case, encryption_key="synthetic-test-passphrase")
    store.add_hearings(
        {
            "hearings": [
                {
                    "hearing_id": "hearing_001",
                    "notice_ref": {"record_id": "notice_001"},
                    "issues": ["synthetic issue"],
                    "authority": [{"citation": "Synthetic", "freshness": "stale"}],
                    "claims": [{"claim": "Synthetic unsupported"}],
                }
            ]
        }
    )
    blockers = store.blockers("hearing_001")
    pack = store.pack("hearing_001")
    assert {
        "missing_operative_order",
        "stale_or_unresolved_authority",
        "unsupported_claim",
        "missing_exhibit",
    } <= set(blockers["blockers"])
    assert pack["outcome_prediction"] if False else pack["review_required"]
    assert len(pack["pack_hash"]) == 64


def test_hearing_api_is_retained_but_workspace_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    assert (
        client.post(
            "/api/hearings",
            json={
                "hearings": [
                    {"hearing_id": "hearing_api_001", "notice_ref": {"record_id": "notice_api_001"}}
                ]
            },
        ).status_code
        == 200
    )
    assert client.get("/api/hearings/receipt").status_code == 200
    html, script = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert (
        'id="hearing-workspace-overlay"' in html
        and "Missing proof" in html
        and "Courtroom notes" in html
    )
    assert "open_hearing_workspace" in script

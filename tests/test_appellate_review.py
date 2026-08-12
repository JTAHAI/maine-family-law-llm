from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.appellate_review import AppellateReviewStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_appellate_blockers_are_review_only(tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    s = AppellateReviewStore(case, encryption_key="synthetic-test-passphrase")
    s.add(
        {
            "appeals": [
                {
                    "appeal_id": "appeal_001",
                    "judgment_ref": {"record_id": "judgment_001"},
                    "issues": [{"issue": "Synthetic"}],
                    "authority": [{"citation": "Synthetic", "freshness": "stale"}],
                    "citations": [{"locator": "A-1"}],
                }
            ]
        }
    )
    r = s.verify("appeal_001")
    assert {"missing_ruling", "stale_or_unresolved_authority", "unresolved_citation"} <= set(
        r["blockers"]
    )
    assert r["merit_prediction"] == "not_available"
    assert len(s.packet("appeal_001")["packet_hash"]) == 64


def test_appellate_api_is_retained_but_ui_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    c = TestClient(api_module.app)
    assert (
        c.post(
            "/api/appellate",
            json={
                "appeals": [
                    {
                        "appeal_id": "appeal_api_001",
                        "judgment_ref": {"record_id": "judgment_api_001"},
                    }
                ]
            },
        ).status_code
        == 200
    )
    assert len(c.get("/api/appellate/receipt").json()["receipt_hash"]) == 64
    h, j = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert 'id="appellate-workspace-overlay"' in h
    assert "Record-citation verifier" in h
    assert "open_appellate_workspace" in j

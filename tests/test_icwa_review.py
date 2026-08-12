from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.icwa_review import IcwaReviewStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def test_icwa_inquiry_never_decides_status(tmp_path: Path) -> None:
    c = tmp_path / "synthetic"
    c.mkdir()
    s = IcwaReviewStore(c, encryption_key="synthetic-test-passphrase")
    s.inquiry(
        {
            "inquiries": [
                {
                    "inquiry_id": "inquiry_001",
                    "child_id": "child_001",
                    "person_safe_id": "person_001",
                    "question": "Synthetic question",
                    "source_ref": {"record_id": "record_001"},
                }
            ]
        }
    )
    i = s.inventory()
    assert (
        i["indian_child_determination"] == "not_determined"
        and i["membership_eligibility"] == "not_determined"
    )
    assert s.completeness()["missing_notice_record"] is True


def test_icwa_api_is_retained_but_ui_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    c = tmp_path / "synthetic"
    c.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: c)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    x = TestClient(api_module.app)
    assert (
        x.post(
            "/api/icwa/inquiries",
            json={
                "inquiries": [
                    {
                        "inquiry_id": "inquiry_api_001",
                        "child_id": "child_api_001",
                        "person_safe_id": "person_api_001",
                        "source_ref": {"record_id": "record_api_001"},
                    }
                ]
            },
        ).status_code
        == 200
    )
    assert len(x.get("/api/icwa/receipt").json()["receipt_hash"]) == 64
    h, j = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert 'id="icwa-workspace-overlay"' in h
    assert "Notice review" in h
    assert "open_icwa_workspace" not in j

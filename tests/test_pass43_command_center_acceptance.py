from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-ONE",
            "title": "Fictional order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "A fictional order was entered on January 3, 2026.",
            "page_number": 1,
            "privacy_status": "review_required",
            "parser_status": "pass",
        },
        {
            "evidence_id": "SCAN-ONE",
            "title": "Fictional scanned document",
            "source_type": "scan",
            "source_hash": "b" * 64,
            "text": "A fictional scanned document requires an OCR review.",
            "page_number": 2,
            "privacy_status": "cleared",
            "ocr_status": "review_required",
        },
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows)
    return TestClient(api_module.app)


def test_command_center_aggregates_corrective_blockers_and_hash_chained_health_history(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root, _records())

    initial = client.get("/api/matters/FICTIONAL-42/command-center")
    assert initial.status_code == 200
    health = initial.json()["health"]
    blocker_ids = {row["blocker_id"] for row in health["blockers"]}
    assert {"no_frozen_snapshot", "no_evidence_packet", "privacy_review_required", "parser_or_ocr_review_required"} <= blocker_ids
    assert all(row["corrective_action"]["scope"] == "active_matter_only" for row in health["blockers"])
    assert initial.json()["health_history"][-1]["entry_sha256"]

    repeated = client.get("/api/matters/FICTIONAL-42/command-center")
    assert repeated.status_code == 200
    assert len(repeated.json()["health_history"]) == 1

    source = client.get("/api/matters/FICTIONAL-42/command-center/records/ORDER-ONE/source")
    assert source.status_code == 200
    assert source.json()["source"]["record_id"] == "ORDER-ONE"
    assert len(source.json()["source"]["source_token"]) == 64

    snapshot = client.post(
        "/api/matters/FICTIONAL-42/review-snapshot",
        json={"approved": True, "variant": "metadata_only"},
    )
    assert snapshot.status_code == 200
    after_snapshot = client.get("/api/matters/FICTIONAL-42/command-center")
    assert after_snapshot.status_code == 200
    assert len(after_snapshot.json()["health_history"]) == 2
    assert after_snapshot.json()["health_history"][-1]["previous_entry_sha256"] == after_snapshot.json()["health_history"][-2]["entry_sha256"]

    history = client.get("/api/matters/FICTIONAL-42/command-center/health-history")
    assert history.status_code == 200
    assert history.json()["count"] == 2
    assert history.json()["review_required"] is True


def test_command_center_health_history_tampering_fails_closed(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root, _records())
    assert client.get("/api/matters/FICTIONAL-42/command-center").status_code == 200
    history_path = case_root / "21_MATTER_COMMAND_CENTER" / "health_history.jsonl"
    history_path.write_text(history_path.read_text(encoding="utf-8").replace("attention_required", "quiet"), encoding="utf-8")
    tampered = client.get("/api/matters/FICTIONAL-42/command-center/health-history")
    assert tampered.status_code == 409
    assert tampered.json()["detail"] == "command_center_health_history_tampered"


def test_command_center_health_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    for marker in (
        "Review blockers and exact corrective actions",
        "Matter health history",
        "data-command-center-inspect-record",
        "/command-center/records/${encodeURIComponent(recordId)}/source",
    ):
        assert marker in src_ui

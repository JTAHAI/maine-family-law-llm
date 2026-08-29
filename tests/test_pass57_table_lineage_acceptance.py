from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api


def test_table_lineage_is_active_matter_gated_and_source_bound(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "active_case_root", lambda: tmp_path)
    client = TestClient(api.app)

    response = client.post(
        "/api/evidence/table-lineage-review",
        json={
            "source_hash": "a" * 64,
            "cells": [
                {
                    "cell_id": "p1-r1-c1",
                    "value": "Fictional amount",
                    "page_number": 1,
                    "coordinates": {"x": 72, "y": 144, "width": 60, "height": 12},
                    "ocr_text": "Fictional amount",
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_hash"] == "a" * 64
    assert payload["review_required"] is True
    assert payload["cells"][0]["coordinates"]["x"] == 72
    assert payload["cells"][0]["review_required"] is True
    assert "overwrite" in payload["notice"].lower()

    missing_page = client.post(
        "/api/evidence/table-lineage-review",
        json={"source_hash": "a" * 64, "cells": [{"value": "fictional", "page_number": 0}]},
    )
    assert missing_page.status_code == 400
    assert missing_page.json()["detail"] == "table_lineage_page_required"

    monkeypatch.setattr(api, "active_case_root", lambda: None)
    unavailable = client.post(
        "/api/evidence/table-lineage-review",
        json={"source_hash": "a" * 64, "cells": []},
    )
    assert unavailable.status_code == 404


def test_table_lineage_is_in_both_production_assets():
    root = Path(__file__).resolve().parents[1]
    source = root / "src" / "maine_family_law_llm" / "ui" / "workbench.js"
    frozen = root / "maine_family_law_llm" / "ui" / "workbench.js"

    assert source.read_bytes() == frozen.read_bytes()
    content = source.read_text(encoding="utf-8")
    assert "/api/evidence/table-lineage-review" in content
    assert "table-lineage-run" in content
    assert "Review required" in content

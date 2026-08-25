from pathlib import Path

from app.api.main import app as canonical_app


ROOT = Path(__file__).resolve().parents[1]


def test_pass28_canonical_api_exposes_review_required_pinpoint_route() -> None:
    operation = canonical_app.openapi()["paths"]["/api/authority/pinpoints/resolve"]["post"]

    assert operation["summary"].startswith("Resolve an exact admitted pinpoint")


def test_pass28_frozen_runtime_and_shipped_ui_share_the_pinpoint_path() -> None:
    frozen_api = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()

    assert '@app.post("/api/authority/pinpoints/resolve")' in frozen_api
    assert b"/api/authority/pinpoints/resolve" in source_ui
    assert b"Review required." in source_ui
    assert source_ui == mirrored_ui

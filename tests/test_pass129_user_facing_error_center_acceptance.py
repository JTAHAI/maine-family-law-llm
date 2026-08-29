from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_UI = ROOT / "src" / "maine_family_law_llm" / "ui"
MIRROR_UI = ROOT / "maine_family_law_llm" / "ui"


def test_pass129_safe_error_center_is_reachable_and_uses_only_safe_failure_fields() -> None:
    html = (SOURCE_UI / "workbench.html").read_text(encoding="utf-8")
    script = (SOURCE_UI / "workbench.js").read_text(encoding="utf-8")
    css = (SOURCE_UI / "workbench.css").read_text(encoding="utf-8")

    for marker in ('id="error-center-overlay"', 'id="error-center-status"', 'id="error-center-list"', 'data-v8-action="errors"'):
        assert marker in html
    for marker in (
        "const safeErrorEvents = [];",
        "const maxSafeErrorEvents = 25;",
        "function recordSafeError(error, title)",
        "function renderErrorCenter()",
        "function openErrorCenter(owner = null)",
        "recordSafeError(error, title);",
        "button.dataset.v8Action === 'errors'",
    ):
        assert marker in script
    assert "hasSafeEnvelope ? String(error?.message" in script
    assert ".error-center-card" in css and ".error-center-list" in css


def test_pass129_error_center_assets_remain_mirrored() -> None:
    for name in ("workbench.css", "workbench.html", "workbench_components.js", "workbench.js"):
        assert (SOURCE_UI / name).read_bytes() == (MIRROR_UI / name).read_bytes()

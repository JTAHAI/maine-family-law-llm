from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_v3_constitutional_identity_and_shortcuts_are_locked() -> None:
    contract_path = REPO_ROOT / "configs" / "maine_v3_ui_interaction_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    identity = contract["constitutional_identity"]
    assert identity["always_visible"] == [
        "WE THE PEOPLE",
        "… establish JUSTICE …",
    ]
    assert "Justice does not belong" in identity["popover_text"]
    assert {"hover", "focus", "tap", "escape"} <= (
        set(identity["triggers"]) | set(identity["close_actions"])
    )

    palette = contract["command_palette"]
    assert palette["shortcut"] == "Ctrl+K"
    assert palette["visible_hint_required"] is True
    assert palette["touch_button_required"] is True
    assert "open_justice_lens" in palette["initial_commands"]

    justice = contract["justice_easter_egg"]
    assert justice["shortcut"] == "Ctrl+J"
    assert justice["initial_focus_phrase"] == "establish Justice"
    assert justice["asset_policy"] == "local_public_domain_only"
    assert justice["visible_palette_entry"] is True


def test_v3_plan_protects_children_families_and_accessibility() -> None:
    plan = (
        REPO_ROOT / "docs" / "v3" / "V3_IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")

    required_phrases = (
        "Child Impact Lens",
        "Next three steps",
        "Maine-law support",
        "Private-record support",
        "Ctrl+K",
        "Ctrl+J",
        "WE THE PEOPLE",
        "establish JUSTICE",
        "No deadline, source status, safety warning, privacy control",
    )
    for phrase in required_phrases:
        assert phrase in plan

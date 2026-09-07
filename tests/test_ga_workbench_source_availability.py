"""Execute the shipped startup-state function; never mock an API as E2E proof."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src/maine_family_law_llm/ui"


def test_startup_actions_do_not_promise_missing_authority():
    script = (UI / "workbench.js").read_text(encoding="utf-8")
    function = (
        "function renderNextSafeAction()"
        + script.split("function renderNextSafeAction()", 1)[1].split(
            "function runNextSafeAction", 1
        )[0]
    )
    harness = (
        """
const nextSafeActionCard = {}, lastPayload = null;
const nextSafeActionHeading = {}, nextSafeActionDetail = {}, nextSafeActionStatus = {};
const nextSafeActionPrimary = {}, nextSafeActionAlternativeOne = {};
const nextSafeActionAlternativeTwo = {};
const activeMatterContext = () => ({active:false});
const configureNextSafeAction = (button, value) => Object.assign(button, value);
let authorityTrustPayload = null;
"""
        + function
        + """
const results = [];
for (const state of [null, {active:false},
  {active:true,source_count:0}, {active:true,source_count:4}]) {
  authorityTrustPayload = state; renderNextSafeAction();
  results.push({heading:nextSafeActionHeading.textContent,
    detail:nextSafeActionDetail.textContent, action:nextSafeActionPrimary.action});
}
console.log(JSON.stringify(results));
"""
    )
    result = subprocess.run(
        ["node", "-e", harness], capture_output=True, text=True, timeout=20, check=True
    )
    states = json.loads(result.stdout)
    assert all(row["action"] == "review_authority" for row in states[:3])
    assert all("available now" not in row["detail"] for row in states[:3])
    assert states[3]["action"] == "focus_question"
    assert "available now" in states[3]["detail"]


def test_view_menu_has_checked_state_and_keyboard_recovery_in_both_copies():
    for filename in ("workbench.js", "workbench.html", "workbench.css"):
        assert (UI / filename).read_bytes() == (
            ROOT / "maine_family_law_llm/ui" / filename
        ).read_bytes()
    script = (UI / "workbench.js").read_text(encoding="utf-8")
    menu = (
        (UI / "workbench.html")
        .read_text(encoding="utf-8")
        .split('id="v8-view-menu"', 1)[1]
        .split("</details>", 1)[0]
    )
    assert 'aria-checked="true" data-v8-view="chat" role="menuitemradio"' in menu
    assert "aria-pressed" not in menu
    assert "button.setAttribute('aria-checked', selected ? 'true' : 'false')" in script
    assert "['ArrowDown', 'ArrowUp', 'Home', 'End']" in script
    assert "if (returnFocus) v8ViewMenu.querySelector('summary')?.focus()" in script

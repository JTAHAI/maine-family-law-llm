from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_journey_eval_cases_match_schema_required_fields() -> None:
    schema = json.loads(
        (ROOT / "eval_data" / "schemas" / "maine_user_journey_eval.schema.json").read_text(
            encoding="utf-8"
        )
    )
    cases = json.loads(
        (ROOT / "eval_data" / "user_journeys" / "maine_user_journey_eval_cases.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(schema["required_fields"])
    allowed_audiences = set(schema["allowed_audiences"])
    assert len(cases) >= 15
    assert {case["journey_id"] for case in cases} >= {
        "self_represented_custody_contact",
        "uploaded_prompt_injection",
        "unsupported_filing_ready",
        "fake_citation_check",
        "emergency_safety",
    }
    for row in cases:
        assert required.issubset(row)
        assert row["audience"] in allowed_audiences


def test_user_journey_schema_names_expected_metrics() -> None:
    schema = json.loads(
        (ROOT / "eval_data" / "schemas" / "maine_user_journey_eval.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert "prompt_injection_resistance" in schema["metrics"]
    assert "filing_ready_blocked_when_required" in schema["metrics"]
    assert "overall_pass" in schema["metrics"]

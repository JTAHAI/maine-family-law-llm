from __future__ import annotations

from pathlib import Path

from legal.matter.calendar_review import CalendarReviewStore


def test_calendar_candidates_are_source_bound_review_required_and_local(tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = CalendarReviewStore(case, encryption_key="synthetic-test-passphrase")
    store.add_events(
        {
            "events": [
                {
                    "event_id": "service_001",
                    "kind": "completed_service_candidate",
                    "date_time": "2026-01-02T23:30:00",
                    "time_zone": "America/New_York",
                    "proof_status": "disputed",
                    "disputed": True,
                    "source_ref": {"record_id": "proof_001", "page": 1},
                }
            ]
        }
    )
    store.add_rules(
        {
            "rules": [
                {
                    "rule_id": "rule_001",
                    "citation": "Synthetic rule",
                    "freshness": "stale",
                    "triggering_event": "completed_service_candidate",
                    "unit": "days",
                    "count": 7,
                    "inclusion_rule": "unknown",
                    "weekend_holiday_handling": "unknown",
                    "source_ref": {"record_id": "rule_source_001", "page": 2},
                }
            ]
        }
    )
    candidate = store.calculate(
        {"rule_id": "rule_001", "trigger_event_id": "service_001", "holidays": ["2026-01-19"]}
    )
    assert candidate["candidate_result"] == "2026-01-09"
    assert candidate["uncertainty"] == "stale_or_unknown_authority"
    assert candidate["reviewer_confirmed"] is False
    assert len(candidate["hash"]) == 64
    assert store.inventory()["calendar_account_write"] is False

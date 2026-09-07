from types import SimpleNamespace

import pytest

from scripts.verify_evidence_review_in_app import _quality_disclosure


def _candidate():
    return SimpleNamespace(
        model_id="mfl-evidence-review-research-r0011",
        capability="evidence_review",
        release_fingerprint="a" * 64,
    )


def _manifest(**changes):
    result = {
        "scope": "fictional_evidence_handling_research_only_not_substantive_legal_knowledge",
        "product_admission": "not_supplied; use only explicit offline research diagnostics",
        "production_admitted": False,
        "attorney_reviewed": False,
    }
    result.update(changes)
    return result


def _failed_quality(**changes):
    result = {
        "quality_gate_passed": False,
        "legal_use_approved": False,
        "runnable_research_only": True,
        "adapter_case_attempts": 99,
        "aggregate_semantic_passes": 5,
    }
    result.update(changes)
    return result


def test_bounded_fictional_profile_never_claims_admission_or_legal_use():
    result = _quality_disclosure(
        _failed_quality(),
        _manifest(),
        _candidate(),
        capability="evidence_review",
        bounded_fictional_research=True,
    )
    assert result["scope"] == "bounded_fictional_research_verifier_only"
    assert result["quality_gate_passed"] is False
    assert result["legal_use_approved"] is False
    assert result["client_matter_use"] is False
    assert result["raw_model_narrative_visible"] is False


@pytest.mark.parametrize(
    ("quality_changes", "manifest_changes", "capability"),
    [
        ({"quality_gate_passed": True}, {}, "evidence_review"),
        ({"legal_use_approved": True}, {}, "evidence_review"),
        ({}, {"production_admitted": True}, "evidence_review"),
        ({}, {}, "drafting"),
    ],
)
def test_bounded_fictional_profile_fails_closed_when_its_constraints_change(
    quality_changes, manifest_changes, capability
):
    with pytest.raises(ValueError, match="bounded_fictional_research_profile_required"):
        _quality_disclosure(
            _failed_quality(**quality_changes),
            _manifest(**manifest_changes),
            _candidate(),
            capability=capability,
            bounded_fictional_research=True,
        )

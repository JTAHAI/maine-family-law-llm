import json

import pytest

from scripts import audit_mfl_explanation_keywords as module


@pytest.mark.parametrize(
    "quote", ['"The claim has no adjudicated finding."', "“The claim has no adjudicated finding.”"]
)
def test_copied_record_does_not_substitute_for_an_explanation(quote):
    case = {"meaning_groups": [["claim"], ["finding"]]}
    result = module.explanation_check(case, f"Record: {quote} [1] Review required.")
    assert result["unquoted_meaning_keywords"] is False
    assert result["groups_satisfied"] == 0


def test_unquoted_keywords_are_only_a_lexical_check_not_truth():
    case = {"meaning_groups": [["claim"], ["finding"]]}
    result = module.explanation_check(case, "Every claim is a finding. Review required.")
    assert result["unquoted_meaning_keywords"] is True
    assert result["factual_or_legal_accuracy_proven"] is False


@pytest.mark.parametrize("answer", ['"claim finding', "“claim finding"])
def test_unfinished_quote_fails_closed(answer):
    assert not module.explanation_check({"meaning_groups": [["claim"]]}, answer)[
        "unquoted_meaning_keywords"
    ]


@pytest.mark.parametrize("groups", [None, "claim", [[]], [[""]], [[1]]])
def test_malformed_meaning_groups_fail_closed(groups):
    with pytest.raises(ValueError):
        module.explanation_check({"meaning_groups": groups}, "Review required.")


def test_empty_groups_cannot_be_counted_as_proof():
    assert not module.explanation_check({"meaning_groups": []}, "Review required.")[
        "unquoted_meaning_keywords"
    ]


@pytest.mark.parametrize("tamper", [None, "fixture", "case", "completion", "admission"])
def test_report_audit_preserves_baseline_and_rejects_unbound_evidence(
    tmp_path, monkeypatch, tamper
):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    fixture = tmp_path / "fictional.json"
    fixture.write_text(
        json.dumps(
            {
                "training_use_permitted": False,
                "cases": [{"id": "fictional-one", "meaning_groups": [["missing"]]}],
            }
        ),
        encoding="utf-8",
    )
    report = {
        "schema": "mfl.adapter-pilot-generation.v1",
        "completed": True,
        "inputs_unchanged": True,
        "production_admitted": False,
        "fatal_errors": [],
        "input_sha256": {str(fixture.resolve()): module.sha(fixture)},
        "requested": 1,
        "total": 1,
        "artifact_sha256": "a" * 64,
        "results": [
            {
                "fixture": fixture.name,
                "case_id": "fictional-one",
                "answer": '"An attachment is missing." [1] Review required.',
                "mechanical_pass": True,
                "checks": {"meaning_keywords": True},
            }
        ],
    }
    if tamper == "fixture":
        fixture.write_text("{}", encoding="utf-8")
    elif tamper == "case":
        report["results"][0]["case_id"] = "different"
    elif tamper == "completion":
        report["completed"] = False
    elif tamper == "admission":
        report["production_admitted"] = True
    report_path = tmp_path / "generation.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    before = report_path.read_bytes()
    output = tmp_path / "dist/diagnostic.json"
    if tamper:
        with pytest.raises(ValueError):
            module.audit(report_path, [fixture], output)
        assert not output.exists()
    else:
        result = module.audit(report_path, [fixture], output)
        assert result["original_mechanical_passed"] == 1
        assert result["combined_diagnostic_passed"] == 0
        assert result["quote_only_meaning_matches"] == 1
        assert result["production_admitted"] is False
    assert report_path.read_bytes() == before

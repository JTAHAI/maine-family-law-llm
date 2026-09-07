import copy

import pytest

from scripts.train_mfl_native_pilot import packet_digest, validate_pair, validate_training_budget


@pytest.mark.parametrize("device,limit", [("cpu", 64), ("cpu", 128), ("cuda", 64), ("cuda", 128), ("cuda", 512)])
def test_explicit_training_budgets(device, limit):
    validate_training_budget(limit, device)


@pytest.mark.parametrize("device,limit", [("cpu", 512), ("cuda", 1024), ("auto", 64), ("cpu", 0)])
def test_no_implicit_or_unbounded_training_budget(device, limit):
    with pytest.raises(ValueError, match="guarded CUDA"):
        validate_training_budget(limit, device)


def pair():
    packet = {"case_id": "train-fictional", "split": "train", "question": "Review the record.",
              "sources": ["A visit was proposed."], "quotes": ["A visit was proposed."],
              "forbidden_literals": ["QA-PRIVATE-OMIT"]}
    row = {"schema": "mainely-code.sft-example.v1", "example_id": packet["case_id"],
           "split": "train", "rights_class": "company_owned", "privacy_class": "no_client_data",
           "source_digest": packet_digest(packet), "task_family": "conditional",
           "response": 'Record: "A visit was proposed." [1] Completion is not established. Review required.'}
    return row, packet


def test_new_prompt_preserves_source_but_not_old_instruction():
    row, packet = pair()
    row["instruction"] = "OLD FRAME MUST NOT BE USED"
    result = validate_pair(row, packet, "evidence_review")
    assert result["messages"][0]["role"] == "system"
    assert "OLD FRAME" not in str(result["messages"])
    assert result["response"] == row["response"]


@pytest.mark.parametrize("field,value", [
    ("split", "test"), ("rights_class", "unknown"), ("privacy_class", "private"),
    ("source_digest", "0" * 64), ("example_id", "different"),
])
def test_forbid_holdout_private_unlicensed_or_unbound_rows(field, value):
    row, packet = pair()
    row[field] = value
    with pytest.raises(ValueError, match="binding mismatch"):
        validate_pair(row, packet, "drafting")


def test_changed_source_body_is_not_silently_trained():
    row, packet = pair()
    changed = copy.deepcopy(packet)
    changed["sources"] = ["The visit happened."]
    with pytest.raises(ValueError, match="binding mismatch"):
        validate_pair(row, changed, "evidence_review")


@pytest.mark.parametrize("response,match", [
    ('"A visit was proposed." [2] Review required.', "quotation"),
    ('"A visit was proposed." [1] Filing ready.', "review status"),
    ('"A visit was proposed." [1] QA-PRIVATE-OMIT Review required.', "forbidden literal"),
])
def test_wrong_reference_review_loss_and_private_target_block_training(response, match):
    row, packet = pair()
    row["response"] = response
    with pytest.raises(ValueError, match=match):
        validate_pair(row, packet, "evidence_review")

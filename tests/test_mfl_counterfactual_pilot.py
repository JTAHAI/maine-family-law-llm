import hashlib

from scripts.audit_mfl_generalization_pilot import validate_rows
from scripts.build_mfl_counterfactual_pilot import development_cases, training_case
from scripts.build_mfl_evidence_corrective_corpus import canonical


def test_every_counterfactual_pair_changes_evidence_not_the_question():
    for group in range(32):
        for family in range(8):
            absent = training_case(group * 16 + family)
            present = training_case(group * 16 + family + 8)
            assert absent[0] == present[0]
            assert absent[1] != present[1]
            assert absent[3] != present[3]
            assert absent[4] == present[4]


def test_counterfactual_targets_are_exact_private_safe_and_development_disjoint():
    rows, packets = [], []
    for i in range(512):
        question, sources, quotes, limit, forbidden = training_case(i)
        packet = {
            "case_id": str(i),
            "sources": sources,
            "quotes": quotes,
            "question": question,
            "forbidden_literals": forbidden,
            "split": "train",
        }
        bound = "; ".join(
            f'"{q}" [{next(n for n, s in enumerate(sources, 1) if q in s)}]' for q in quotes
        )
        packets.append(packet)
        rows.append(
            {
                "example_id": str(i),
                "split": "train",
                "task_family": str(i % 8),
                "source_digest": hashlib.sha256(canonical(packet)).hexdigest(),
                "privacy_class": "no_client_data",
                "rights_class": "company_owned",
                "instruction": '[{"role":"user","content":"fictional test"}]',
                "response": bound + limit + " Review required.",
            }
        )
    report = validate_rows(
        rows, packets, {"training_use_permitted": False, "cases": development_cases()}
    )
    assert report["rows"] == 512
    assert report["declared_development_overlap"] == 0


def test_confirmation_does_not_train_completion_or_fault_as_fact():
    assert "not proof that the event occurred" in training_case(9)[3]
    assert "does not determine fault" in training_case(12)[3]
    assert "not proof the event occurred" in training_case(14)[3]
    assert "neither its terms nor its validity" in training_case(13)[3]


def test_development_pairs_are_explicitly_diagnostic_and_balanced():
    cases = development_cases()
    assert len(cases) == 8
    for i in range(0, 8, 2):
        left, right = cases[i : i + 2]
        assert left["pair_id"] == right["pair_id"]
        assert left["question"] == right["question"]
        assert left["sources"][0] == right["sources"][0]
        assert left["sources"][1] != right["sources"][1]
        assert left["confirmation_present"] is False
        assert right["confirmation_present"] is True

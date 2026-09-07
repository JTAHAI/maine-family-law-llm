import re

import pytest

from scripts.build_mfl_diverse_counterfactual import training_case


def test_all_rows_keep_exact_source_binding_and_no_private_target():
    for index in range(512):
        question, sources, quotes, answer, forbidden = training_case(index)
        assert question and answer
        assert all(any(quote in source for source in sources) for quote in quotes)
        assert all(value not in answer and all(value not in quote for quote in quotes) for value in forbidden)


def test_clock_training_has_varied_correct_intervals_not_a_constant_answer():
    durations = set()
    for pair in range(32):
        _, sources, _, answer, _ = training_case(pair * 16 + 8 + 3)
        times = re.findall(r"(\d{2}):(\d{2}) UTC", " ".join(sources))
        assert len(times) == 2
        minutes = [int(h) * 60 + int(m) for h, m in times]
        interval = minutes[1] - minutes[0]
        assert f"{interval} minutes apart" in answer
        durations.add(interval)
    assert len(durations) == 32


def test_partial_authorization_never_counts_as_complete():
    for pair in range(1, 32, 2):
        absent = training_case(pair * 16 + 1)
        present = training_case(pair * 16 + 8 + 1)
        assert absent[0] == present[0]
        assert "Only one of the two" in absent[3]
        assert "satisfies" in present[3]
        assert absent[1] != present[1]


def test_attachment_targets_vary_actual_contents_and_keep_request_boundary():
    answers = {training_case(pair * 16 + 8 + 2)[3] for pair in range(32)}
    assert len(answers) == 32
    assert all("does not establish delivery" in answer for answer in answers)


@pytest.mark.parametrize("index", [-1, 512])
def test_no_unbounded_generation(index):
    with pytest.raises(ValueError):
        training_case(index)

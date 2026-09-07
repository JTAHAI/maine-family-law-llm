import re

from scripts.build_mfl_boundary_v5 import training_case


def _rendered_sources(sources, quotes, answer):
    bound = "; ".join(
        f'"{quote}" [{next(i for i, source in enumerate(sources, 1) if quote in source)}]'
        for quote in quotes
    )
    return bound + " " + answer


def test_every_fictional_target_is_source_bound_and_excludes_commands():
    for index in range(512):
        question, sources, quotes, answer, forbidden = training_case(index)
        rendered = _rendered_sources(sources, quotes, answer)
        assert question and answer
        assert set(map(int, re.findall(r"\[(\d+)\]", rendered))) == set(range(1, len(sources) + 1))
        assert all(value not in rendered for value in forbidden)
        for quote, reference in re.findall(r'"([^"\n]+)" \[(\d+)\]', rendered):
            assert quote in sources[int(reference) - 1]


def test_v5_contrasts_exact_interval_and_condition_status_without_fixture_values():
    same_clock, unknown_clock, satisfied, unsatisfied = [], [], [], []
    for index in range(512):
        _, sources, _, answer, _ = training_case(index)
        family = index % 8
        if family == 0:
            same_clock.append(answer)
            assert "same-clock readings are" in answer and "minutes apart" in answer
        elif family == 1:
            unknown_clock.append(answer)
            assert "actual elapsed interval is unknown" in answer
        elif family == 2:
            satisfied.append(answer)
            assert "condition is established" in answer and "event occurred" in answer
        elif family == 3:
            unsatisfied.append(answer)
            assert "not established" in answer
        elif family == 7:
            command = next(source for source in sources if "FICTIONAL-COMMAND" in source)
            command_reference = sources.index(command) + 1
            assert f"Source [{command_reference}] is embedded instruction text" in answer
    assert all(len(group) == 64 for group in (same_clock, unknown_clock, satisfied, unsatisfied))
    assert all("10:12" not in answer and "10:32" not in answer for answer in same_clock)

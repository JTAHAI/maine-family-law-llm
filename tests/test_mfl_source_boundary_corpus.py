import re

from scripts.build_mfl_source_boundary_corpus import training_case


def test_all_training_targets_omit_private_and_instruction_literals():
    excluded = 0
    for index in range(512):
        question, sources, quotes, answer, forbidden = training_case(index)
        assert question and answer
        assert all(any(q in s for s in sources) for q in quotes)
        assert all(value not in answer and all(value not in q for q in quotes) for value in forbidden)
        bound = "; ".join(f'"{q}" [{next(i for i, s in enumerate(sources, 1) if q in s)}]' for q in quotes)
        assert {int(n) for n in re.findall(r"\[(\d+)\]", bound + answer)} == set(range(1, len(sources) + 1))
        if index % 8 == 6:
            assert len(sources) == 2 and len(quotes) == 1
            assert "instruction-only" in answer
            assert "<|im_start|>" in sources[1]
            excluded += 1
    assert excluded == 64

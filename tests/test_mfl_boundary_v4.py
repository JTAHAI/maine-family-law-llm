import re
from collections import Counter

from scripts.build_mfl_boundary_v4 import training_case


def test_exact_source_attribution_and_exclusion_across_all_families():
    attacks = Counter()
    for index in range(512):
        question, sources, quotes, answer, forbidden = training_case(index)
        assert question and answer
        assert all(any(q in source for source in sources) for q in quotes)
        rendered = " ".join(f'{q} [{next(i for i, s in enumerate(sources, 1) if q in s)}]' for q in quotes) + answer
        assert set(map(int, re.findall(r"\[(\d+)\]", rendered))) == set(range(1, len(sources) + 1))
        assert all(value not in rendered for value in forbidden)
        if any("FICTIONAL-OVERRIDE" in s for s in sources):
            attacks[index % 8] += 1
    assert attacks == {**{family: 32 for family in range(7)}, 7: 16}
    assert any(not training_case(index)[1] for index in range(7, 512, 8))


def test_signature_and_written_approval_are_independent():
    combinations = set()
    for index in range(9, 512, 16):
        _, sources, _, answer, _ = training_case(index)
        requirement = next(s for s in sources if "requires" in s)
        approval = next(s for s in sources if "message approves" in s)
        requires_signature = "signed written" in requirement
        signed = "unsigned" not in approval
        combinations.add((requires_signature, signed))
        assert ("signature prerequisite is not established" in answer) == (requires_signature and not signed)
        assert "does not establish that the activity occurred" in answer
    assert len(combinations) == 4

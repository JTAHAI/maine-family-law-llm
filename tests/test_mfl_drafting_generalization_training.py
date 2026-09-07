from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_mfl_drafting_generalization_corpus import (
    _clean_case,
    _explicit_redaction,
    _general_no_sources,
)
from scripts.train_mfl_adapter_continuation import (
    CUDA_ALLOCATOR_CONFIG,
    DEFAULT_CUDA_EMPTY_CACHE_EVERY,
    exact_prompt,
    learning_rate,
    select_train_rows,
    write_json,
)


def test_exact_prompt_matches_literal_fast_interchange_wire_format() -> None:
    instruction = json.dumps([{"role": "user", "content": "Review this record."}])

    assert exact_prompt(instruction) == (
        "fi-fixed-role-v1:[USER]\\nReview this record."
    )
    assert "\n" not in exact_prompt(instruction)


def test_exact_prompt_rejects_assistant_or_extra_fields() -> None:
    with pytest.raises(ValueError, match="fixed-role"):
        exact_prompt(json.dumps([{"role": "assistant", "content": "unsafe"}]))
    with pytest.raises(ValueError, match="fixed-role"):
        exact_prompt(json.dumps([{"role": "user", "content": "x", "path": "C:/private"}]))


def test_general_no_source_target_does_not_quote_or_invent_a_reference() -> None:
    prompt, sources, response, quotes, forbidden = _general_no_sources(17, "RECORD-000017")

    assert not sources and not quotes and not forbidden
    assert "[1]" not in response and '"' not in response
    assert "No source was supplied" in response
    assert response.endswith("Review required.")
    assert "no record" in prompt or "not supplied" in prompt or "empty source" in prompt


def test_redaction_target_is_removed_but_safe_source_span_is_bound() -> None:
    _, sources, response, quotes, forbidden = _explicit_redaction(29, "RECORD-000029")

    assert len(sources) == len(quotes) == len(forbidden) == 1
    assert forbidden[0] in sources[0] and forbidden[0] not in response
    assert quotes[0] in sources[0]
    assert f'"{quotes[0]}" [1]' in response
    assert "redacted" in response.casefold()


def test_scaffolding_variation_keeps_source_identity_available() -> None:
    tag = "RECORD-000005"
    value = (
        f"Review {tag}.",
        [f"Fictional note {tag} records an event."],
        f'Working draft: "Fictional note {tag} records an event." [1] Review required.',
        [f"Fictional note {tag} records an event."],
        [],
    )

    prompt, sources, response, quotes, _ = _clean_case(value, 5, tag)

    assert tag not in prompt
    assert tag in sources[0] and tag in response and tag in quotes[0]


def test_continuation_learning_rate_warms_and_decays() -> None:
    peak = 6e-5
    rates = [learning_rate(step, 1_600, peak) for step in (0, 47, 48, 800, 1_599)]

    assert 0 < rates[0] < rates[1] <= peak
    assert rates[2] == pytest.approx(peak)
    assert rates[3] < rates[2]
    assert rates[-1] < rates[3]


def test_continuation_uses_bounded_consumer_gpu_allocator_policy() -> None:
    assert CUDA_ALLOCATOR_CONFIG == "expandable_segments:True"
    assert DEFAULT_CUDA_EMPTY_CACHE_EVERY == 64


def test_residual_continuation_cannot_repeat_or_spill_from_authorized_train_split() -> None:
    rows = [
        *[{"example_id": f"train-{index}", "split": "train"} for index in range(6)],
        {"example_id": "test-0", "split": "test"},
    ]

    all_train, residual = select_train_rows(rows, offset=3, limit=3)

    assert [row["example_id"] for row in all_train] == [f"train-{index}" for index in range(6)]
    assert [row["example_id"] for row in residual] == ["train-3", "train-4", "train-5"]
    with pytest.raises(ValueError, match="authorized train split"):
        select_train_rows(rows, offset=4, limit=3)


def test_progress_receipt_retries_transient_windows_replace_lock(tmp_path, monkeypatch) -> None:
    target = tmp_path / "progress.json"
    actual_replace = Path.replace
    attempts = 0

    def locked_once(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("temporary observer lock")
        return actual_replace(source, destination)

    monkeypatch.setattr(Path, "replace", locked_once)
    write_json(target, {"step": 1})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"step": 1}
    assert not list(tmp_path.glob("*.tmp"))

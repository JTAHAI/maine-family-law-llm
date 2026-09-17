"""Receipts cannot authorize tokenizer/configuration swaps for pinned weights."""

from dataclasses import replace

import pytest

from legal.fast_interchange.compact_cpu import LocalModelError, PinnedFile
from legal.fast_interchange.compact_ranker_pins import RANKER_PINS, verify_ranker_inventory
from legal.fast_interchange.compact_reranker import CompactPassageReranker


def files(root, weights):
    return tuple(
        PinnedFile(root / name, size, sha) for name, (size, sha) in RANKER_PINS[weights].items()
    )


@pytest.mark.parametrize("weights", RANKER_PINS)
def test_all_original_descriptor_pins_match(tmp_path, weights):
    assert verify_ranker_inventory(files(tmp_path, weights)) == weights


@pytest.mark.parametrize(
    "weights,name", [(weights, name) for weights, rows in RANKER_PINS.items() for name in rows]
)
@pytest.mark.parametrize("change", ["hash", "size", "folder"])
def test_every_file_is_pinned_not_only_weights(tmp_path, weights, name, change):
    rows = files(tmp_path, weights)
    changed = []
    for row in rows:
        if row.path.name == name:
            row = replace(
                row,
                **{
                    "hash": dict(sha256="0" * 64),
                    "size": dict(bytes=row.bytes + 1),
                    "folder": dict(path=tmp_path / "different" / name),
                }[change],
            )
        changed.append(row)
    with pytest.raises(LocalModelError) as caught:
        verify_ranker_inventory(tuple(changed))
    assert caught.value.code == (
        "fast_interchange_reranker_candidate_not_allowlisted"
        if name == "model.safetensors" and change == "hash"
        else "fast_interchange_compact_model_integrity_failed"
    )


@pytest.mark.parametrize("weights", RANKER_PINS)
def test_duplicates_missing_and_extra_files_are_rejected(tmp_path, weights):
    original = files(tmp_path, weights)
    for changed in (original[:-1], original + original[:1], original[:-1] + original[:1]):
        with pytest.raises(LocalModelError):
            verify_ranker_inventory(changed)


def test_forged_local_receipt_does_not_allow_model_load(tmp_path, monkeypatch):
    import sys

    weights = next(iter(RANKER_PINS))
    rows = tuple(
        replace(r, sha256="a" * 64) if r.path.name == "tokenizer.json" else r
        for r in files(tmp_path, weights)
    )
    # Exact changed-file hash in an attacker-edited receipt must not become trust.
    monkeypatch.setitem(sys.modules, "torch", None)
    engine = CompactPassageReranker(rows, research_only=True)
    try:
        with pytest.raises(LocalModelError) as caught:
            engine.warm()
        assert caught.value.code == "fast_interchange_compact_model_integrity_failed"
        assert engine.phase == "artifact_verification"
        assert engine._model is None
    finally:
        engine.close()

import copy
import hashlib
from threading import Event

import pytest

from legal.fast_interchange.compact_cpu import LocalModelError
from legal.fast_interchange.compact_span_process import (
    SPAN_BOOTSTRAP,
    IsolatedSpanReader,
    verify_spans,
)
from legal.fast_interchange.compact_span_reader import PINNED, CompactSpanReader, decode_span
from scripts.acquire_compact_model_candidates import CATALOG
from scripts.verify_compact_span_reader import CASES


def decoded():
    return decode_span(
        [0, 99, 3, 1], [0, 99, 1, 3], [(0, 0), (0, 1), (0, 3), (4, 7)], [None, 0, 1, 1], "red box"
    )


def packet():
    return dict(
        query="What color?",
        matter_id="fictional-qa",
        passages=[
            dict(
                text="red box",
                source_id="qa",
                matter_id="fictional-qa",
                lane="private_record",
            )
        ],
    )


def row():
    return dict(
        decoded(),
        source_id="qa",
        source_index=0,
        source_sha256=hashlib.sha256(b"red box").hexdigest(),
    )


def test_context_only_not_question_tokens():
    assert decoded()["text"] == "red box"
    assert decoded()["truth_verified"] is False


def test_abstention_never_means_absence():
    result = decode_span([20, 1], [20, 1], [(0, 0), (0, 3)], [None, 1], "red")
    assert result["status"] == "no_candidate"
    assert result["text"] is None and result["absence_verified"] is False


def test_answer_length_is_bounded_and_cannot_cross_context_boundary():
    start, end = [0.0] * 42, [0.0] * 42
    start[1], end[40] = 50.0, 50.0
    offsets = [(0, 0)] + [(i, i + 1) for i in range(40)] + [(0, 0)]
    result = decode_span(start, end, offsets, [None] + [1] * 40 + [None], "x" * 40)
    assert 0 < result["end"] - result["start"] <= 32


@pytest.mark.parametrize("length", [0, 513])
def test_invalid_context_length(length):
    with pytest.raises(LocalModelError):
        decode_span([0.0] * length, [0.0] * length, [(0, 0)] * length, [None] * length, "red")


def test_no_context_and_score_overflow_fail_closed():
    with pytest.raises(LocalModelError):
        decode_span([0, 1], [0, 1], [(0, 0), (0, 3)], [None, 0], "red")
    with pytest.raises(LocalModelError):
        decode_span([0, 1e308], [0, 1e308], [(0, 0), (0, 3)], [None, 1], "red")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True])
def test_invalid_logits(bad):
    with pytest.raises(LocalModelError):
        decode_span([0, bad], [0, 1], [(0, 0), (0, 3)], [None, 1], "red")


@pytest.mark.parametrize("offset", [(0, 4), (-1, 2), (2, 1), (True, 2)])
def test_invalid_offsets(offset):
    with pytest.raises(LocalModelError):
        decode_span([0, 1], [0, 1], [(0, 0), offset], [None, 1], "red")


@pytest.mark.parametrize(
    "key,value",
    [
        ("source_sha256", "0" * 64),
        ("source_index", True),
        ("source_id", "other"),
        ("text", "invented"),
        ("start", -1),
        ("end", 99),
        ("truth_verified", True),
        ("review_required", False),
        ("absence_verified", True),
        ("span_minus_null_score", float("nan")),
        ("status", "verified"),
    ],
)
def test_parent_rejects_changed_source_or_claim(key, value):
    result = row()
    result[key] = value
    with pytest.raises(LocalModelError):
        verify_spans([result], packet())


def test_parent_accepts_exact_span_only():
    assert verify_spans([row()], packet())[0]["text"] == "red box"


def test_fixed_qa_entrypoint_separate_from_scalar_ranker():
    assert "operation='extract'" in SPAN_BOOTSTRAP
    for engine in (CompactSpanReader, IsolatedSpanReader):
        with pytest.raises(LocalModelError):
            engine.rank(None)


def test_wrong_inventory_fails_before_import():
    engine = CompactSpanReader((), research_only=True)
    with pytest.raises(LocalModelError):
        engine.warm()
    assert engine._model is None


def test_license_and_budget_are_explicit():
    candidate = CATALOG["minilm-span-reader"]
    assert candidate["license"] == "cc-by-4.0"
    assert set(candidate["files"]) == set(PINNED)
    assert (
        sum(size for size, _ in PINNED.values()) + candidate["selected_runtime_bytes"]
        < 1_500_000_000
    )
    assert candidate["weights_sha256"] == PINNED["model.safetensors"][1]


def test_predeclared_balanced_fictional_fixture():
    assert len(CASES) == len({r[0] for r in CASES}) == 16
    assert sum(r[3] is None for r in CASES) == 8
    assert all(expected is None or expected in context for _, _, context, expected in CASES)


def test_cross_matter_rejected_before_worker(tmp_path):
    # Bypass construction only to test that source validation precedes all process work.
    worker = object.__new__(IsolatedSpanReader)
    data = copy.deepcopy(packet())
    data["passages"][0]["matter_id"] = "other"
    with pytest.raises(LocalModelError):
        worker.extract(**data)


def test_precancel_never_starts_worker(tmp_path):
    from legal.fast_interchange.compact_cpu import PinnedFile

    worker = IsolatedSpanReader(
        (PinnedFile(tmp_path / "model.safetensors", 1, "a" * 64),),
        scratch=tmp_path,
        research_only=True,
    )
    event = Event()
    event.set()
    with pytest.raises(LocalModelError):
        worker.extract(**packet(), cancellation=event)
    assert worker.worker_starts == 0


def test_source_changed_during_warm_stops_before_extract(tmp_path, monkeypatch):
    from legal.fast_interchange.compact_cpu import PinnedFile

    worker = IsolatedSpanReader(
        (PinnedFile(tmp_path / "model.safetensors", 1, "a" * 64),),
        scratch=tmp_path,
        research_only=True,
    )
    data = packet()

    def changed(_cancel):
        data["passages"][0]["text"] = "different text"

    monkeypatch.setattr(worker, "_ensure_warm", changed)
    with pytest.raises(LocalModelError):
        worker.extract(**data)
    assert worker.completed_requests == 0
    assert worker._process is None


def test_span_worker_never_accepts_production_admission(tmp_path):
    with pytest.raises(LocalModelError):
        IsolatedSpanReader((), scratch=tmp_path, research_only=False)
    with pytest.raises(LocalModelError):
        CompactSpanReader((), research_only=False)

"""Opt-in actual CPU transport regression, not a model-quality acceptance test."""

import hashlib
import json
import os
import time

import pytest

from legal.fast_interchange.compact_cpu import LocalModelError, pinned_inventory
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from legal.fast_interchange.compact_span_process import IsolatedSpanReader
from scripts.acquire_compact_model_candidates import OUTPUT

pytestmark = pytest.mark.skipif(
    os.environ.get("MFL_RUN_SPAN_TRANSPORT") != "1", reason="explicit real-model opt-in required"
)


@pytest.mark.parametrize(
    "candidate,worker_class",
    [
        ("minilm-span-reader", IsolatedSpanReader),
        ("legal-passage-reranker", IsolatedCompactRanker),
    ],
)
def test_actual_fixed_worker_protocol_and_shutdown(tmp_path, candidate, worker_class):
    worker = worker_class(
        pinned_inventory(OUTPUT / candidate, "acquisition.json"),
        scratch=tmp_path,
        research_only=True,
    )
    text = "The fictional folder rests on the green table."
    packet = dict(
        query="Where does the fictional folder rest?",
        matter_id="fictional-smoke",
        passages=[
            dict(source_id="folder", lane="private_record", matter_id="fictional-smoke", text=text)
        ],
    )
    report = dict(candidate=candidate, quality_acceptance=False, production_admitted=False)
    started = time.perf_counter()
    try:
        worker.warm()
        report["warm_seconds"] = time.perf_counter() - started
        operation = worker.extract if candidate == "minilm-span-reader" else worker.rank
        result = operation(**packet)
        assert len(result) == 1
        assert result[0]["review_required"] is True
        assert result[0]["truth_verified"] is False
        assert result[0]["source_sha256"] == hashlib.sha256(text.encode()).hexdigest()
        report["result"] = result
        if candidate == "minilm-span-reader":
            assert result[0]["status"] == "candidate_span"
            assert result[0]["text"] == text[result[0]["start"] : result[0]["end"]]
            packet["passages"][0]["text"] = "fictional " * 600
            with pytest.raises(LocalModelError) as caught:
                operation(**packet)
            assert caught.value.code == "fast_interchange_reranker_worker_failed"
            assert worker.last_failure["phase"] == "tokenize"
            assert worker._process is None
            report["oversized_source_failed_closed"] = True
    finally:
        worker.close()
        report.update(
            worker_stopped=worker._process is None,
            peak_resident_bytes=worker.peak_resident_bytes,
            completed_requests=worker.completed_requests,
        )
        (tmp_path / "transport-result.json").write_text(json.dumps(report, indent=2))
    assert worker._process is None

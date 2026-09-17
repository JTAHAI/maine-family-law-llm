"""Research-only span protocol with the existing owned Windows job lifecycle."""

import hashlib
import math

from .compact_cpu import fail
from .compact_ranker_process import WORKER_BOOTSTRAP, IsolatedCompactRanker
from .compact_reranker import rank_input

SPAN_RUNTIME_ABI = "compact_span_research_v1"

SPAN_BOOTSTRAP = WORKER_BOOTSTRAP.replace(
    "raise SystemExit(main())",
    "from legal.fast_interchange.compact_span_reader import CompactSpanReader;"
    "raise SystemExit(main(engine_type=CompactSpanReader,operation='extract'))",
)


def verify_spans(rows, packet):
    if not isinstance(rows, list) or len(rows) != len(packet["passages"]):
        fail("span_response_invalid")
    keys = {
        "source_id",
        "source_index",
        "source_sha256",
        "status",
        "start",
        "end",
        "text",
        "span_minus_null_score",
        "review_required",
        "truth_verified",
        "absence_verified",
    }
    for index, (row, passage) in enumerate(zip(rows, packet["passages"], strict=True)):
        if not isinstance(row, dict) or set(row) != keys:
            fail("span_response_invalid")
        score = row["span_minus_null_score"]
        if (
            type(row["source_index"]) is not int
            or row["source_index"] != index
            or row["source_id"] != passage["source_id"]
            or row["source_sha256"] != hashlib.sha256(passage["text"].encode()).hexdigest()
            or row["review_required"] is not True
            or row["truth_verified"] is not False
            or row["absence_verified"] is not False
            or type(score) not in (float, int)
            or not math.isfinite(score)
        ):
            fail("span_response_invalid")
        if row["status"] == "no_candidate" and score <= 0:
            if any(row[k] is not None for k in ("start", "end", "text")):
                fail("span_response_invalid")
        elif row["status"] == "candidate_span" and score > 0:
            if (
                type(row["start"]) is not int
                or type(row["end"]) is not int
                or not 0 <= row["start"] < row["end"] <= len(passage["text"])
                or row["text"] != passage["text"][row["start"] : row["end"]]
            ):
                fail("span_response_invalid")
        else:
            fail("span_response_invalid")
    return rows


class IsolatedSpanReader(IsolatedCompactRanker):
    def _bootstrap(self):
        return SPAN_BOOTSTRAP

    def rank(self, **kwargs):
        fail("span_reader_is_not_scalar_ranker")

    def extract(self, *, query, passages, matter_id, cancellation=None):
        packet = rank_input(query, passages, matter_id)
        if not self._operation.acquire(blocking=False):
            fail("worker_busy")
        self._cancel.clear()
        try:
            if cancellation is not None and cancellation.is_set():
                fail("generation_canceled")
            self._ensure_warm(cancellation)
            if packet != rank_input(query, passages, matter_id):
                fail("reranker_source_changed")
            rows = self._exchange("extract", packet, cancellation=cancellation)
            if cancellation is not None and cancellation.is_set():
                fail("generation_canceled")
            if packet != rank_input(query, passages, matter_id):
                fail("reranker_source_changed")
            verify_spans(rows, packet)
            self.completed_requests += 1
            return rows
        except BaseException:
            self._stop()
            raise
        finally:
            self._operation.release()

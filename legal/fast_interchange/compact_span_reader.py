"""Pinned extractive QA experiment. Exact text is not evidence of factual truth.

Research only: no production factory, admission, free-form generation or tools.
The fixed zero no-answer margin is exploratory, not a calibrated safety policy.
"""

from __future__ import annotations

import hashlib
import math
import time

import psutil

from legal.security.strict_json import strict_json_load_path

from .admission import canonical
from .compact_cpu import fail
from .compact_reranker import CompactPassageReranker, rank_input
from .snapshot import validate_safetensors

PINNED = {
    "README.md": (6138, "4be17750ace7cfef930939987619382f61f77252bdb4b57422c369e9d6b589eb"),
    "config.json": (477, "688d980e03e028843d378fb3bf9919dc4b677b24e2a6ef37c97815d5c056151b"),
    "tokenizer_config.json": (
        107,
        "c95bd2738add69376f7b8dea64d917128f949f174daa48910c5d8bf87bad36e2",
    ),
    "special_tokens_map.json": (
        112,
        "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
    ),
    "vocab.txt": (231508, "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"),
    "model.safetensors": (
        133466376,
        "240478c7251d5e55be35feb47177054b960259b9328af662ea3cee87ce9755a6",
    ),
}


def decode_span(start, end, offsets, sequence_ids, text):
    """Bounded context-only contiguous spans; CLS is the no-answer comparator."""
    n = len(start)
    if (
        not 1 <= n <= 512
        or len(end) != n
        or len(offsets) != n
        or len(sequence_ids) != n
        or sequence_ids[0] is not None
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in [*start, *end])
    ):
        fail("span_logits_invalid")
    valid = []
    previous = 0
    for i, (offset, lane) in enumerate(zip(offsets, sequence_ids, strict=True)):
        if lane != 1:
            continue
        if (
            len(offset) != 2
            or any(type(v) is not int for v in offset)
            or not 0 <= offset[0] < offset[1] <= len(text)
            or offset[0] < previous
        ):
            fail("span_offsets_invalid")
        previous = offset[1]
        valid.append(i)
    best = None
    for i in valid:
        for j in range(i, min(i + 32, n)):
            if sequence_ids[j] != 1:
                break
            score = start[i] + end[j]
            if best is None or score > best[0]:
                best = (score, offsets[i][0], offsets[j][1])
    if best is None:
        fail("span_context_missing")
    margin = best[0] - (start[0] + end[0])
    if not math.isfinite(margin):
        fail("span_score_invalid")
    accepted = margin > 0
    return {
        "status": "candidate_span" if accepted else "no_candidate",
        "start": best[1] if accepted else None,
        "end": best[2] if accepted else None,
        "text": text[best[1] : best[2]] if accepted else None,
        "span_minus_null_score": margin,
        "review_required": True,
        "truth_verified": False,
        "absence_verified": False,
    }


class CompactSpanReader(CompactPassageReranker):
    def warm(self):
        if self._model is not None:
            return
        try:
            self.phase = "artifact_verification"
            if (
                len(self.files) != len(PINNED)
                or {r.path.name: (r.bytes, r.sha256) for r in self.files} != PINNED
                or len({r.path.parent for r in self.files}) != 1
            ):
                fail("span_inventory_invalid")
            root = self.files[0].path.parent
            if {p.name for p in root.iterdir()} != set(PINNED) | {"acquisition.json"}:
                fail("span_inventory_invalid")
            for artifact in self.files:
                artifact.lock(self._locks)
                if artifact.path.suffix == ".json":
                    strict_json_load_path(artifact.path, max_bytes=10000, require_object=True)
            validate_safetensors(root / "model.safetensors", maximum_bytes=140_000_000)
            self.phase = "runtime_import"
            import torch
            from transformers import BertForQuestionAnswering, BertTokenizer

            self.phase = "model_load"
            self._tokenizer = BertTokenizer.from_pretrained(
                root,
                local_files_only=True,
                trust_remote_code=False,
            )
            self._model = (
                BertForQuestionAnswering.from_pretrained(
                    root,
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                    dtype=torch.float32,
                )
                .cpu()
                .eval()
            )
            self._torch = torch
            self.phase = "warm"
        except BaseException:
            self.close()
            raise

    def extract(self, *, query, passages, matter_id):
        packet = rank_input(query, passages, matter_id)
        self.warm()
        started, rows = time.monotonic(), []
        previous = self._torch.get_num_threads()
        self._torch.set_num_threads(2)
        try:
            with self._torch.inference_mode():
                for index, passage in enumerate(packet["passages"]):
                    if time.monotonic() - started > 60:
                        fail("generation_timeout")
                    if psutil.virtual_memory().available < 1024**3:
                        fail("insufficient_available_memory")
                    self.phase = "tokenize"
                    tokens = self._tokenizer(
                        query,
                        passage["text"],
                        truncation=False,
                        return_offsets_mapping=True,
                        return_tensors="pt",
                    )
                    n = tokens["input_ids"].shape[-1]
                    if n > 512:
                        fail("span_source_too_long")
                    if int(tokens["input_ids"][0, 0]) != self._tokenizer.cls_token_id:
                        fail("span_cls_missing")
                    offsets = tokens.pop("offset_mapping")[0].tolist()
                    sequence_ids = tokens.sequence_ids(0)
                    self.phase = "score"
                    output = self._model(**tokens)
                    if tuple(output.start_logits.shape) != (1, n) or tuple(
                        output.end_logits.shape
                    ) != (1, n):
                        fail("span_logits_invalid")
                    decoded = decode_span(
                        output.start_logits[0].tolist(),
                        output.end_logits[0].tolist(),
                        offsets,
                        sequence_ids,
                        passage["text"],
                    )
                    rows.append(
                        dict(
                            decoded,
                            source_id=passage["source_id"],
                            source_index=index,
                            source_sha256=hashlib.sha256(passage["text"].encode()).hexdigest(),
                        )
                    )
            if canonical(packet) != canonical(rank_input(query, passages, matter_id)):
                fail("reranker_source_changed")
            return rows
        finally:
            self._torch.set_num_threads(previous)

    def rank(self, **kwargs):
        fail("span_reader_is_not_scalar_ranker")

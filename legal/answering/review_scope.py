"""Bounded, process-local provenance for server-produced public-law answers.

An opaque handle binds an unmodified rendered answer to its producer's assertion
text. It is not a verification verdict. No caller-provided section label is
trusted, no private matter text is written to disk, and restart/expiry fails
closed. Only the public-authority answer producer issues these handles.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AnswerAssertions:
    text: str
    authority_build_id: str
    source_ids: tuple[str, ...]
    quotes: tuple[tuple[str, str], ...] = ()  # source ID, exact quoted text
    basis: str = "server_answer_body"


@dataclass(frozen=True)
class BoundAnswerReview:
    answer_sha256: str
    context_sha256: str
    assertions: AnswerAssertions
    expires_at: float


class AnswerReviewScopes:
    def __init__(
        self,
        *,
        ttl_seconds: float = 1800,
        max_entries: int = 64,
        max_bytes: int = 4_000_000,
        clock=time.monotonic,
    ):
        self._ttl = ttl_seconds
        self._limit = max_entries
        self._max_bytes = max_bytes
        self._clock = clock
        self._lock = threading.RLock()
        self._rows: OrderedDict[str, tuple[BoundAnswerReview, int]] = OrderedDict()

    def _purge(self):
        now = self._clock()
        for handle, (row, _) in list(self._rows.items()):
            if row.expires_at <= now:
                del self._rows[handle]

    def issue(self, *, answer: str, context: str, assertions: AnswerAssertions) -> str:
        if not assertions.authority_build_id or not assertions.source_ids:
            raise ValueError("answer_review_authority_binding_required")
        size = (
            len(assertions.text.encode("utf-8"))
            + sum(len(value.encode("utf-8")) for pair in assertions.quotes for value in pair)
            + 512
        )
        if size > self._max_bytes or len(answer) > 200_000:
            raise ValueError("answer_review_scope_too_large")
        with self._lock:
            self._purge()
            while self._rows and (
                len(self._rows) >= self._limit
                or sum(item[1] for item in self._rows.values()) + size > self._max_bytes
            ):
                self._rows.popitem(last=False)
            handle = secrets.token_urlsafe(32)
            self._rows[handle] = (
                BoundAnswerReview(
                    text_hash(answer), text_hash(context), assertions, self._clock() + self._ttl
                ),
                size,
            )
        return handle

    def resolve(self, handle: str, *, answer: str, context: str) -> BoundAnswerReview:
        with self._lock:
            self._purge()
            entry = self._rows.get(handle)
            if entry is None:
                raise ValueError("answer_review_scope_expired_or_unavailable")
            row = entry[0]
            if row.answer_sha256 != text_hash(answer) or row.context_sha256 != text_hash(context):
                raise ValueError("answer_review_scope_mismatch")
            return row

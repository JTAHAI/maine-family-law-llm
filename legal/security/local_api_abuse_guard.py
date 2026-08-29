"""Bounded, content-free abuse controls for the loopback desktop API."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass


SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_TOKENISH_SEGMENT = re.compile(r"^(?:[a-f0-9]{16,}|[0-9a-f-]{24,})$", re.I)


@dataclass(frozen=True)
class AbuseGuardDecision:
    allowed: bool
    code: str
    retry_after_seconds: int
    bucket: str


class LocalApiAbuseGuard:
    """Small in-memory rate guard with no prompts, IDs, or request bodies retained."""

    def __init__(
        self,
        *,
        window_seconds: int = 60,
        read_limit: int = 1_200,
        write_limit: int = 240,
        max_buckets: int = 512,
    ) -> None:
        self.window_seconds = max(1, int(window_seconds))
        self.read_limit = max(1, int(read_limit))
        self.write_limit = max(1, int(write_limit))
        self.max_buckets = max(8, int(max_buckets))
        self._lock = threading.RLock()
        self._events: dict[str, deque[float]] = {}

    @staticmethod
    def _route_class(path: str) -> str:
        segments = []
        for raw in str(path or "/").split("/"):
            if not raw:
                continue
            segment = "*" if _TOKENISH_SEGMENT.fullmatch(raw) else raw[:48]
            segments.append(segment)
            if len(segments) >= 5:
                break
        return "/" + "/".join(segments)

    @staticmethod
    def _client_class(client_host: str | None) -> str:
        value = str(client_host or "").strip().casefold()
        if value in {"127.0.0.1", "::1", "localhost"}:
            return "loopback"
        if value == "testclient":
            return "testclient"
        return "other"

    def check(self, *, method: str, path: str, client_host: str | None, now: float | None = None) -> AbuseGuardDecision:
        """Apply one bounded local rate policy without retaining sensitive route text."""
        current = float(now if now is not None else time.monotonic())
        method_name = str(method or "GET").upper()
        operation = "read" if method_name in SAFE_METHODS else "write"
        client = self._client_class(client_host)
        bucket = f"{client}:{operation}:{self._route_class(path)}"
        limit = self.read_limit if operation == "read" else self.write_limit
        with self._lock:
            stale_before = current - self.window_seconds
            for key, entries in list(self._events.items()):
                while entries and entries[0] <= stale_before:
                    entries.popleft()
                if not entries:
                    self._events.pop(key, None)
            if len(self._events) >= self.max_buckets and bucket not in self._events:
                oldest = min(self._events, key=lambda key: self._events[key][0] if self._events[key] else current)
                self._events.pop(oldest, None)
            entries = self._events.setdefault(bucket, deque())
            if len(entries) >= limit:
                retry_after = max(1, int(self.window_seconds - (current - entries[0])))
                return AbuseGuardDecision(False, "local_rate_limited", retry_after, operation)
            entries.append(current)
        return AbuseGuardDecision(True, "allowed", 0, operation)

    def status(self) -> dict[str, int | bool]:
        """Return policy counters only; bucket identities are intentionally omitted."""
        with self._lock:
            event_count = sum(len(entries) for entries in self._events.values())
            bucket_count = len(self._events)
        return {
            "enabled": True,
            "window_seconds": self.window_seconds,
            "read_limit": self.read_limit,
            "write_limit": self.write_limit,
            "active_bucket_count": bucket_count,
            "tracked_event_count": event_count,
            "retains_content": False,
        }


__all__ = ["AbuseGuardDecision", "LocalApiAbuseGuard", "SAFE_METHODS"]

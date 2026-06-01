from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from legal.connectors.base import RetrievedSource, SourceTarget


@dataclass(frozen=True)
class FetchAttempt:
    attempt_number: int
    status: str
    message: str
    elapsed_seconds: float
    status_code: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "status": self.status,
            "message": self.message,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "status_code": self.status_code,
        }


class OfficialSourceFetchError(RuntimeError):
    """Raised when an official-source fetch is blocked or exhausted."""

    def __init__(
        self,
        *,
        target: SourceTarget,
        code: str,
        message: str,
        attempts: list[FetchAttempt] | None = None,
    ) -> None:
        super().__init__(message)
        self.target = target
        self.code = code
        self.message = message
        self.attempts = attempts or []

    def as_failure_record(self) -> dict[str, Any]:
        return {
            "target_id": self.target.target_id,
            "source_class": self.target.source_class,
            "jurisdiction": self.target.jurisdiction,
            "url": self.target.url,
            "parser_name": self.target.parser_name,
            "failure_code": self.code,
            "message": self.message,
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


@dataclass
class RobotsCacheEntry:
    parser: urllib.robotparser.RobotFileParser
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    allowed_to_fetch_robots: bool = True


class OfficialSourceFetcher:
    """HTTP fetcher for official legal sources.

    The production fetcher applies a deliberate user agent, per-request delay,
    retry/backoff, optional robots.txt checks, and failure records that can be
    written into the external authority build evidence. Unit tests can still
    inject a static fetcher with the same ``fetch(target)`` shape.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        min_delay_seconds: float = 1.0,
        user_agent: str = "MaineFamilyLawLLM-AuthorityIngest/1.0 (+source verification)",
        max_retries: int = 2,
        retry_backoff_seconds: float = 1.5,
        respect_robots_txt: bool = True,
        strict_content_type: bool = False,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.min_delay_seconds = min_delay_seconds
        self.user_agent = user_agent
        self.max_retries = max(0, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.respect_robots_txt = respect_robots_txt
        self.strict_content_type = strict_content_type
        self._last_fetch_monotonic: float | None = None
        self._robots_cache: dict[str, RobotsCacheEntry] = {}

    def _rate_limit(self) -> None:
        if self._last_fetch_monotonic is None:
            return
        elapsed = time.monotonic() - self._last_fetch_monotonic
        remaining = self.min_delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(self, url: str, *, accept: str) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": accept or "*/*",
            },
        )

    def _robots_url_for(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

    def _robots_entry(self, url: str) -> RobotsCacheEntry:
        robots_url = self._robots_url_for(url)
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]
        parser = urllib.robotparser.RobotFileParser(robots_url)
        allowed_to_fetch_robots = True
        try:
            with urllib.request.urlopen(
                self._request(robots_url, accept="text/plain"), timeout=self.timeout_seconds
            ) as response:
                parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
        except Exception:
            # Absence or temporary failure of robots.txt is not treated as permission
            # to hammer a site; ingestion remains rate-limited and auditable.
            allowed_to_fetch_robots = False
            parser.parse([])
        entry = RobotsCacheEntry(parser=parser, allowed_to_fetch_robots=allowed_to_fetch_robots)
        self._robots_cache[robots_url] = entry
        return entry

    def _check_robots(self, target: SourceTarget) -> None:
        if not self.respect_robots_txt:
            return
        entry = self._robots_entry(target.url)
        if not entry.parser.can_fetch(self.user_agent, target.url):
            raise OfficialSourceFetchError(
                target=target,
                code="robots_disallow",
                message=f"robots.txt disallows fetching {target.url}",
            )


    @staticmethod
    def _content_type_matches(expected: str | None, actual: str | None, content: bytes) -> bool:
        """Return whether a response matches the target's expected content type.

        Official sites sometimes include charset parameters or serve PDFs as
        ``application/octet-stream``.  In strict mode, HTML must be HTML-like
        and PDF targets must either advertise a PDF-ish content type or begin
        with a PDF file signature.
        """
        expected_norm = (expected or "").split(";", 1)[0].strip().lower()
        actual_norm = (actual or "").split(";", 1)[0].strip().lower()
        if not expected_norm or expected_norm == "*/*":
            return True
        if expected_norm == actual_norm:
            return True
        if expected_norm == "application/pdf":
            return actual_norm in {"application/octet-stream", "binary/octet-stream"} or content.startswith(b"%PDF")
        if expected_norm == "text/html":
            prefix = content[:512].lstrip().lower()
            return actual_norm in {"application/xhtml+xml", "text/plain"} and (b"<html" in prefix or b"<!doctype html" in prefix)
        if expected_norm.startswith("text/") and actual_norm.startswith("text/"):
            return True
        return False

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        self._check_robots(target)
        attempts: list[FetchAttempt] = []
        last_message = "fetch not attempted"
        for attempt_number in range(1, self.max_retries + 2):
            self._rate_limit()
            started = time.monotonic()
            try:
                request = self._request(
                    target.url,
                    accept=target.expected_content_type or "*/*",
                )
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    content = response.read()
                    content_type = response.headers.get("Content-Type")
                    if self.strict_content_type and not self._content_type_matches(
                        target.expected_content_type, content_type, content
                    ):
                        elapsed = time.monotonic() - started
                        last_message = (
                            f"content type mismatch: expected {target.expected_content_type!r}, "
                            f"got {content_type!r}"
                        )
                        attempts.append(
                            FetchAttempt(
                                attempt_number=attempt_number,
                                status="content_type_mismatch",
                                message=last_message,
                                elapsed_seconds=elapsed,
                                status_code=getattr(response, "status", None),
                            )
                        )
                        break
                    elapsed = time.monotonic() - started
                    attempts.append(
                        FetchAttempt(
                            attempt_number=attempt_number,
                            status="success",
                            message="fetched",
                            elapsed_seconds=elapsed,
                            status_code=getattr(response, "status", None),
                        )
                    )
                    result = RetrievedSource(
                        target=target,
                        content=content,
                        retrieved_at=datetime.now(timezone.utc),
                        content_type=content_type,
                        status_code=getattr(response, "status", None),
                        final_url=response.geturl(),
                    )
                self._last_fetch_monotonic = time.monotonic()
                return result
            except urllib.error.HTTPError as exc:
                elapsed = time.monotonic() - started
                last_message = f"HTTP {exc.code}: {exc.reason}"
                attempts.append(
                    FetchAttempt(
                        attempt_number=attempt_number,
                        status="http_error",
                        message=last_message,
                        elapsed_seconds=elapsed,
                        status_code=exc.code,
                    )
                )
                if 400 <= exc.code < 500 and exc.code not in {408, 425, 429}:
                    break
            except Exception as exc:  # network/DNS/timeout/socket errors
                elapsed = time.monotonic() - started
                last_message = f"{type(exc).__name__}: {exc}"
                attempts.append(
                    FetchAttempt(
                        attempt_number=attempt_number,
                        status="network_error",
                        message=last_message,
                        elapsed_seconds=elapsed,
                    )
                )
            self._last_fetch_monotonic = time.monotonic()
            if attempt_number <= self.max_retries and self.retry_backoff_seconds:
                time.sleep(self.retry_backoff_seconds * attempt_number)
        raise OfficialSourceFetchError(
            target=target,
            code="fetch_failed",
            message=last_message,
            attempts=attempts,
        )

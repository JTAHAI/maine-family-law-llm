from __future__ import annotations

import http.client
import ipaddress
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from legal.connectors.base import RetrievedSource, SourceTarget

_COURT_HOSTS = frozenset({
    "courts.maine.gov", "www.courts.maine.gov", "mjbportal.courts.maine.gov",
})
_STATUTE_HOSTS = frozenset({"legislature.maine.gov"})
_AGENCY_HOSTS = frozenset({"maine.gov", "www.maine.gov"})
_FEDERAL_HOSTS = frozenset({"uscode.house.gov", "ecfr.gov", "www.ecfr.gov"})
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_ROBOTS_MAX_BYTES = 512 * 1024


class _FetchPolicyError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _allowed_hosts(target: SourceTarget) -> frozenset[str]:
    source_class = target.source_class.casefold().removeprefix("maine_")
    jurisdiction = target.jurisdiction.casefold()
    if jurisdiction in {"federal", "federal-adjacent"} and source_class.startswith("federal_"):
        return _FEDERAL_HOSTS
    if jurisdiction != "maine":
        return frozenset()
    if source_class.startswith("statute_"):
        return _STATUTE_HOSTS
    if source_class.startswith(("court_", "law_court_", "ecourts_")) or source_class in {
        "family_guidance", "family_standing_order",
    }:
        return _COURT_HOSTS
    if source_class in {"agency_reference", "child_support"}:
        return _COURT_HOSTS | _AGENCY_HOSTS
    return frozenset()


def _validate_destination(url: str, hosts: frozenset[str]) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        allowed = (
            not any(ord(char) <= 32 or ord(char) == 127 or char == "\\" for char in url)
            and parsed.scheme == "https"
            and parsed.hostname in hosts
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        allowed = False
    if not allowed:
        raise _FetchPolicyError("source_destination_refused")


def _connect_public_address(address, timeout, source_address=None):
    """Resolve once and connect to a checked IP while leaving HTTPS SNI intact."""
    deadline = time.monotonic() + timeout
    candidates = socket.getaddrinfo(*address, type=socket.SOCK_STREAM)
    if not candidates:
        raise OSError("official_source_dns_empty")
    for _, _, _, _, endpoint in candidates:
        ip = ipaddress.ip_address(endpoint[0])
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise OSError("official_source_dns_nonpublic")
    last_error = None
    for family, kind, proto, _, endpoint in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("official_source_connect_timeout")
        connection = socket.socket(family, kind, proto)
        try:
            connection.settimeout(remaining)
            if source_address is not None:
                connection.bind(source_address)
            connection.connect(endpoint)
            return connection
        except OSError as exc:
            connection.close()
            last_error = exc
    raise OSError("official_source_connect_failed") from last_error


class _OfficialHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_public_address


class _OfficialHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_OfficialHTTPSConnection, request, context=self._context)


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
        max_response_bytes: int = 25 * 1024 * 1024,
    ) -> None:
        self.timeout_seconds = min(120.0, max(0.1, float(timeout_seconds)))
        self.min_delay_seconds = min(30.0, max(0.0, float(min_delay_seconds)))
        self.user_agent = user_agent
        self.max_retries = min(5, max(0, int(max_retries)))
        self.retry_backoff_seconds = min(30.0, max(0.0, float(retry_backoff_seconds)))
        self.respect_robots_txt = respect_robots_txt
        self.strict_content_type = strict_content_type
        self.max_response_bytes = max(1, int(max_response_bytes))
        self._last_fetch_monotonic: float | None = None
        self._robots_cache: dict[tuple[str, frozenset[str]], RobotsCacheEntry] = {}
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _OfficialHTTPSHandler(), _OfficialRedirectHandler()
        )

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
                "Accept-Encoding": "identity",
            },
        )

    def _robots_url_for(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

    def _robots_entry(self, url: str, hosts: frozenset[str]) -> RobotsCacheEntry:
        robots_url = self._robots_url_for(url)
        cache_key = (robots_url, hosts)
        if cache_key in self._robots_cache:
            return self._robots_cache[cache_key]
        parser = urllib.robotparser.RobotFileParser(robots_url)
        allowed_to_fetch_robots = True
        try:
            response, _ = self._open_chain(robots_url, hosts, accept="text/plain")
            with response:
                body, _, truncated = self._read_response_body(response, cap=_ROBOTS_MAX_BYTES)
                if truncated:
                    raise _FetchPolicyError("robots_response_too_large")
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
        except urllib.error.HTTPError as exc:
            allowed_to_fetch_robots = exc.code in {404, 410}
            parser.allow_all = allowed_to_fetch_robots
        except (OSError, http.client.HTTPException, _FetchPolicyError):
            allowed_to_fetch_robots = False
        entry = RobotsCacheEntry(parser=parser, allowed_to_fetch_robots=allowed_to_fetch_robots)
        self._robots_cache[cache_key] = entry
        return entry

    def _open(self, request: urllib.request.Request):
        try:
            return self._opener.open(request, timeout=self.timeout_seconds)
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECT_STATUSES:
                return exc
            exc.close()
            raise

    def _open_chain(self, url: str, hosts: frozenset[str], *, accept: str):
        visited = {url}
        redirects = []
        for _ in range(_MAX_REDIRECTS + 1):
            _validate_destination(url, hosts)
            self._rate_limit()
            self._last_fetch_monotonic = time.monotonic()
            response = self._open(self._request(url, accept=accept))
            if response.status not in _REDIRECT_STATUSES:
                if response.status != 200 or response.headers.get("Content-Range") is not None:
                    response.close()
                    raise _FetchPolicyError("source_response_status_refused")
                return response, redirects
            with response:
                location = response.headers.get("Location")
                if not location:
                    raise _FetchPolicyError("source_redirect_location_missing")
                if any(ord(char) <= 32 or ord(char) == 127 or char == "\\" for char in location):
                    raise _FetchPolicyError("source_destination_refused")
                url = urllib.parse.urljoin(url, location)
                _validate_destination(url, hosts)
            if url in visited:
                raise _FetchPolicyError("source_redirect_loop")
            visited.add(url)
            redirects.append(url)
        raise _FetchPolicyError("source_redirect_limit")

    def _check_robots(self, target: SourceTarget, hosts: frozenset[str]) -> None:
        if not self.respect_robots_txt:
            return
        entry = self._robots_entry(target.url, hosts)
        if not entry.allowed_to_fetch_robots or not entry.parser.can_fetch(self.user_agent, target.url):
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
        and PDF targets require a PDF header in the response body.
        """
        expected_norm = (expected or "").split(";", 1)[0].strip().lower()
        actual_norm = (actual or "").split(";", 1)[0].strip().lower()
        if not expected_norm or expected_norm == "*/*":
            return True
        if expected_norm == "application/pdf":
            return content.startswith(b"%PDF-")
        if expected_norm == "text/html":
            prefix = content[:512].lstrip().lower()
            return actual_norm in {"text/html", "application/xhtml+xml", "text/plain"} and (
                b"<html" in prefix or b"<!doctype html" in prefix
            )
        if expected_norm == actual_norm:
            return True
        if expected_norm.startswith("text/") and actual_norm.startswith("text/"):
            return True
        return False

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        hosts = _allowed_hosts(target)
        try:
            _validate_destination(target.url, hosts)
        except _FetchPolicyError as exc:
            raise OfficialSourceFetchError(target=target, code=exc.code, message=exc.code) from None
        self._check_robots(target, hosts)
        attempts: list[FetchAttempt] = []
        last_message = "fetch not attempted"
        for attempt_number in range(1, self.max_retries + 2):
            started = time.monotonic()
            try:
                response, redirects = self._open_chain(
                    target.url, hosts,
                    accept=target.expected_content_type or "*/*",
                )
                with response:
                    content, byte_count, truncated = self._read_response_body(response)
                    content_type = response.headers.get("Content-Type")
                    mime_is_pdf = (target.expected_content_type or "").split(";", 1)[0].strip().lower() == "application/pdf"
                    if not truncated and (self.strict_content_type or mime_is_pdf) and not self._content_type_matches(
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
                    if truncated:
                        elapsed = time.monotonic() - started
                        last_message = f"response too large: exceeded {self.max_response_bytes} bytes"
                        attempts.append(
                            FetchAttempt(
                                attempt_number=attempt_number,
                                status="response_too_large",
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
                        fetch_metadata={
                            "attempt_count": len(attempts),
                            "attempts": [attempt.as_dict() for attempt in attempts],
                            "content_length": byte_count,
                            "max_response_bytes": self.max_response_bytes,
                            "redirected": response.geturl() != target.url,
                            "redirect_chain": redirects,
                            "robots_policy_result": "checked" if self.respect_robots_txt else "not_checked",
                        },
                    )
                self._last_fetch_monotonic = time.monotonic()
                return result
            except _FetchPolicyError as exc:
                attempts.append(FetchAttempt(attempt_number, exc.code, exc.code, time.monotonic() - started))
                last_message = exc.code
                break
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
            except (OSError, http.client.HTTPException) as exc:
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
                time.sleep(min(30.0, self.retry_backoff_seconds * attempt_number))
        raise OfficialSourceFetchError(
            target=target,
            code="fetch_failed",
            message=last_message,
            attempts=attempts,
        )

    def _read_response_body(self, response, *, cap: int | None = None) -> tuple[bytes, int, bool]:
        max_bytes = self.max_response_bytes if cap is None else cap
        encoding = response.headers.get("Content-Encoding", "identity")
        if encoding.strip().lower() != "identity":
            raise _FetchPolicyError("source_content_encoding_refused")
        get_all = getattr(response.headers, "get_all", None)
        lengths = get_all("Content-Length", []) if get_all else []
        if len(lengths) > 1:
            raise _FetchPolicyError("source_content_length_invalid")
        length = response.headers.get("Content-Length")
        if length is not None and response.headers.get("Transfer-Encoding") is not None:
            raise _FetchPolicyError("source_content_length_invalid")
        if length is not None:
            if not length.isascii() or not length.isdecimal() or len(length) > 20:
                raise _FetchPolicyError("source_content_length_invalid")
            length = int(length)
            if length > max_bytes:
                return b"", length, True
        remaining = max_bytes
        chunks: list[bytes] = []
        byte_count = 0
        deadline = time.monotonic() + self.timeout_seconds
        read = getattr(response, "read1", response.read)
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("official_source_body_timeout")
            chunk = read(min(1024 * 1024, remaining + 1))
            if not chunk:
                break
            byte_count += len(chunk)
            if byte_count > max_bytes:
                return b"".join(chunks), byte_count, True
            chunks.append(chunk)
            remaining = max_bytes - byte_count
        if length is not None and byte_count != length:
            raise _FetchPolicyError("source_content_length_mismatch")
        return b"".join(chunks), byte_count, False


class _OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        # urllib follows redirects by default, including an unbounded drain of
        # the redirect body. Expose each response to the bounded fetch loop.
        original_url = str(getattr(req, "full_url", getattr(req, "url", "")))
        raise urllib.error.HTTPError(original_url, code, msg, headers, fp)

    # Bypass HTTPRedirectHandler.http_error_302 even for unsupported schemes:
    # the source-aware loop owns URL parsing and never drains the redirect.
    def http_error_302(self, req, fp, code, msg, headers):
        return self.redirect_request(req, fp, code, msg, headers, None)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

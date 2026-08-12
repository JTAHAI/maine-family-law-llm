"""Loopback request policy for the local browser workbench.

The workbench is intentionally bound to loopback. This module adds an
application-layer check against Host-header abuse, DNS rebinding, cross-site
browser requests, non-loopback clients, and oversized request bodies.
"""

from __future__ import annotations

import ipaddress
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
DEFAULT_MAX_BODY_BYTES = 2 * 1024 * 1024
_LOCAL_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", "testserver"})
_TEST_CLIENTS = frozenset({"testclient"})


@dataclass(frozen=True)
class FirewallDecision:
    allowed: bool
    status_code: int
    code: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _host_without_port(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or any(ch in raw for ch in "\r\n\x00,"):
        return ""
    if raw.startswith("["):
        end = raw.find("]")
        if end < 0:
            return ""
        return raw[1:end].casefold()
    if raw.count(":") == 1:
        raw = raw.rsplit(":", 1)[0]
    return raw.rstrip(".").casefold()


def _is_loopback_host(value: str) -> bool:
    host = _host_without_port(value)
    if not host:
        return False
    if host in _LOCAL_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _origin_is_local(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    if raw == "null":
        return False
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    return _is_loopback_host(parsed.hostname or "")


def _origin_matches_request_host(origin: str, host_header: str) -> bool:
    """Require browser writes to come from this exact loopback origin.

    Treating every loopback origin as trusted permits a process on another
    localhost port to issue form POSTs to the workbench.  Loopback is a
    network boundary, not a browser same-origin boundary.
    """

    raw_origin = str(origin or "").strip()
    if not raw_origin:
        return True
    try:
        parsed_origin = urlsplit(raw_origin)
    except ValueError:
        return False
    if (
        parsed_origin.scheme != "http"
        or parsed_origin.username
        or parsed_origin.password
        or not parsed_origin.hostname
        or not _is_loopback_host(parsed_origin.hostname)
    ):
        return False
    try:
        origin_port = parsed_origin.port or 80
    except ValueError:
        return False

    raw_host = str(host_header or "").strip()
    if not raw_host or any(ch in raw_host for ch in "\r\n\x00,"):
        return False
    host_name = _host_without_port(raw_host)
    if not _is_loopback_host(host_name):
        return False
    try:
        if raw_host.startswith("["):
            closing = raw_host.find("]")
            suffix = raw_host[closing + 1 :]
            host_port = int(suffix[1:]) if suffix.startswith(":") else 80
        elif raw_host.count(":") == 1:
            host_port = int(raw_host.rsplit(":", 1)[1])
        else:
            host_port = 80
    except ValueError:
        return False
    return parsed_origin.hostname.rstrip(".").casefold() == host_name and origin_port == host_port


def evaluate_local_request(
    *,
    method: str,
    path: str,
    client_host: str | None,
    host_header: str,
    origin_header: str = "",
    sec_fetch_site: str = "",
    content_length: str = "",
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
) -> FirewallDecision:
    """Return a fail-closed decision for a local HTTP request."""

    if max_body_bytes < 0:
        raise ValueError("max_body_bytes must be non-negative")
    normalized_method = str(method or "GET").upper()
    client = str(client_host or "").strip().casefold()
    if client and client not in _TEST_CLIENTS and not _is_loopback_host(client):
        return FirewallDecision(
            False, 403, "non_loopback_client", "Only loopback clients are allowed."
        )
    if not _is_loopback_host(host_header):
        return FirewallDecision(
            False, 403, "invalid_host", "The Host header must identify loopback."
        )
    if origin_header and not _origin_matches_request_host(origin_header, host_header):
        return FirewallDecision(
            False,
            403,
            "cross_origin_blocked",
            "Cross-origin browser requests are blocked.",
        )
    fetch_site = str(sec_fetch_site or "").strip().casefold()
    if fetch_site == "cross-site" and (
        path.startswith("/api/") or normalized_method not in SAFE_METHODS
    ):
        return FirewallDecision(
            False,
            403,
            "cross_site_blocked",
            "Cross-site local-workbench requests are blocked.",
        )
    if content_length:
        try:
            declared = int(content_length)
        except (TypeError, ValueError):
            return FirewallDecision(
                False, 400, "invalid_content_length", "Invalid Content-Length header."
            )
        if declared < 0:
            return FirewallDecision(
                False, 400, "invalid_content_length", "Invalid Content-Length header."
            )
        if normalized_method not in SAFE_METHODS and declared > max_body_bytes:
            return FirewallDecision(
                False, 413, "request_too_large", "Request body exceeds the local limit."
            )
    return FirewallDecision(True, 200, "allowed", "Local request accepted.")


__all__ = [
    "DEFAULT_MAX_BODY_BYTES",
    "FirewallDecision",
    "SAFE_METHODS",
    "evaluate_local_request",
]

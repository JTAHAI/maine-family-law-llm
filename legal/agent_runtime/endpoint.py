"""Strict loopback endpoint validation for optional local model servers."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from urllib.parse import urlsplit, urlunsplit


@dataclass(frozen=True)
class LoopbackEndpoint:
    base_url: str
    host: str
    port: int
    scheme: str
    endpoint_class: str = "loopback_http"

    def url(self, path: str) -> str:
        clean_path = "/" + str(path or "").lstrip("/")
        return f"{self.base_url.rstrip('/')}{clean_path}"


class LoopbackEndpointPolicy:
    """Reject DNS names and all non-loopback destinations.

    Requiring a literal loopback IP avoids DNS-rebinding ambiguity.  HTTPS is
    accepted for local reverse proxies, but ordinary Ollama/LM Studio use HTTP.
    """

    def __init__(self, *, allowed_schemes: tuple[str, ...] = ("http", "https")):
        self.allowed_schemes = allowed_schemes

    def validate(self, value: str) -> LoopbackEndpoint:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("local_model_endpoint_required")
        parsed = urlsplit(raw)
        if parsed.scheme.lower() not in self.allowed_schemes:
            raise ValueError("local_model_endpoint_scheme_not_allowed")
        if parsed.username or parsed.password:
            raise ValueError("local_model_endpoint_userinfo_not_allowed")
        if parsed.query or parsed.fragment:
            raise ValueError("local_model_endpoint_query_or_fragment_not_allowed")
        if not parsed.hostname:
            raise ValueError("local_model_endpoint_host_required")
        try:
            host_ip = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise ValueError("local_model_endpoint_literal_loopback_ip_required") from exc
        if not host_ip.is_loopback:
            raise ValueError("local_model_endpoint_not_loopback")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("local_model_endpoint_invalid_port") from exc
        if port is None:
            port = 443 if parsed.scheme.lower() == "https" else 80
        if not (1 <= port <= 65535):
            raise ValueError("local_model_endpoint_invalid_port")
        path = parsed.path.rstrip("/")
        if ".." in [part for part in path.split("/") if part]:
            raise ValueError("local_model_endpoint_path_traversal")
        netloc_host = f"[{host_ip.compressed}]" if host_ip.version == 6 else host_ip.compressed
        netloc = f"{netloc_host}:{port}"
        base_url = urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))
        return LoopbackEndpoint(
            base_url=base_url,
            host=host_ip.compressed,
            port=port,
            scheme=parsed.scheme.lower(),
            endpoint_class="loopback_https" if parsed.scheme.lower() == "https" else "loopback_http",
        )

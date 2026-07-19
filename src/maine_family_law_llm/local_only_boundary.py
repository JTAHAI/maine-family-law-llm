"""Fail-closed network boundary for local evidence processing."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from typing import Iterator


class LocalOnlyNetworkBlocked(RuntimeError):
    """Raised when a local evidence pipeline attempts network access."""


@contextmanager
def local_only_network_boundary() -> Iterator[None]:
    """Block sockets and DNS for the duration of local evidence processing."""

    original_socket = socket.socket
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def blocked(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise LocalOnlyNetworkBlocked("local_evidence_pipeline_network_access_blocked")

    socket.socket = blocked  # type: ignore[assignment]
    socket.create_connection = blocked  # type: ignore[assignment]
    socket.getaddrinfo = blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create_connection  # type: ignore[assignment]
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]

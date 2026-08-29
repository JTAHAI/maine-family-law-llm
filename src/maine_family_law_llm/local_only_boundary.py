"""Fail-closed network boundary for local evidence processing."""

from __future__ import annotations

import asyncio
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager


class LocalOnlyNetworkBlocked(RuntimeError):
    """Raised when a local evidence pipeline attempts network access."""


_boundary_lock = threading.RLock()
_active_boundaries = 0
_originals: list[tuple[object, str, object, bool]] = []


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise LocalOnlyNetworkBlocked("local_evidence_pipeline_network_access_blocked")


def _restore_originals() -> None:
    for owner, name, original, was_defined in reversed(_originals):
        if was_defined:
            setattr(owner, name, original)
        else:
            delattr(owner, name)
    _originals.clear()


@contextmanager
def local_only_network_boundary() -> Iterator[None]:
    """Block Python outbound connections/DNS, preserving the local API listener.

    Socket construction must remain intact: asyncio constructs accepted sockets
    with it, even when a background OCR thread is running. Guard outbound methods
    instead. Reference counting keeps overlapping/nested jobs blocked until the
    final job exits. This is not an OS firewall or a native-subprocess sandbox.
    """
    global _active_boundaries
    with _boundary_lock:
        if _active_boundaries == 0:
            targets = [
                (socket, name)
                for name in (
                    "create_connection",
                    "getaddrinfo",
                    "gethostbyname",
                    "gethostbyname_ex",
                    "gethostbyaddr",
                )
            ] + [
                (socket.socket, name)
                for name in ("connect", "connect_ex", "sendto", "sendmsg")
                if hasattr(socket.socket, name)
            ]
            # Proactor TCP connects can bypass socket.connect on Windows.
            # Guard outbound asyncio entry points, not server accept/create_server.
            targets.extend(
                (asyncio.BaseEventLoop, name)
                for name in ("create_connection", "create_datagram_endpoint")
            )
            for loop_class in (
                asyncio.SelectorEventLoop,
                getattr(asyncio, "ProactorEventLoop", None),
            ):
                if loop_class is not None:
                    targets.append((loop_class, "sock_connect"))
            try:
                for owner, name in targets:
                    original = getattr(owner, name)
                    was_defined = name in vars(owner)
                    setattr(owner, name, _blocked)
                    _originals.append((owner, name, original, was_defined))
            except BaseException:
                _restore_originals()
                raise
        _active_boundaries += 1
    try:
        yield
    finally:
        with _boundary_lock:
            _active_boundaries -= 1
            if _active_boundaries == 0:
                _restore_originals()

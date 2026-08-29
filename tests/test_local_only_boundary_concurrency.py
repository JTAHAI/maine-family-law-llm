from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from maine_family_law_llm.local_only_boundary import (
    LocalOnlyNetworkBlocked,
    local_only_network_boundary,
)


@pytest.mark.parametrize(
    "name",
    ["create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"],
)
def test_boundary_blocks_connection_factories_and_dns(name):
    original = getattr(socket, name)
    with local_only_network_boundary():
        with pytest.raises(LocalOnlyNetworkBlocked):
            getattr(socket, name)("fictional.invalid")
    assert getattr(socket, name) is original


@pytest.mark.parametrize("method", ["connect", "connect_ex", "sendto", "sendmsg"])
def test_boundary_blocks_existing_socket_outbound_methods(method):
    if not hasattr(socket.socket, method):
        # Windows lacks sendmsg; its absence is not a missing security check.
        assert method == "sendmsg" and sys.platform == "win32"
        return
    constructor = socket.socket
    with socket.socket() as existing:
        original = getattr(socket.socket, method)
        with local_only_network_boundary():
            assert socket.socket is constructor
            with pytest.raises(LocalOnlyNetworkBlocked):
                getattr(existing, method)(b"fictional-data", ("192.0.2.1", 9))
        assert getattr(socket.socket, method) is original


def test_nested_boundaries_restore_after_exception():
    original = socket.create_connection
    socket_attributes = dict(vars(socket.socket))
    loop_attributes = dict(vars(asyncio.SelectorEventLoop))
    with pytest.raises(ValueError, match="fictional"):
        with local_only_network_boundary():
            with local_only_network_boundary():
                with pytest.raises(LocalOnlyNetworkBlocked):
                    socket.create_connection(("192.0.2.1", 9))
            with pytest.raises(LocalOnlyNetworkBlocked):
                socket.create_connection(("192.0.2.1", 9))
            raise ValueError("fictional")
    assert socket.create_connection is original
    assert dict(vars(socket.socket)) == socket_attributes
    assert dict(vars(asyncio.SelectorEventLoop)) == loop_attributes


def test_overlapping_threads_do_not_restore_network_early():
    entered = threading.Event()
    finish = threading.Event()
    original = socket.create_connection
    errors = []

    def second_job():
        try:
            with local_only_network_boundary():
                entered.set()
                if not finish.wait(10):
                    raise TimeoutError("test coordination timed out")
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=second_job, daemon=True)
    try:
        with local_only_network_boundary():
            worker.start()
            assert entered.wait(5)
        # The first scope has ended, but the second job still owns a boundary.
        with pytest.raises(LocalOnlyNetworkBlocked):
            socket.create_connection(("192.0.2.1", 9))
    finally:
        finish.set()
        worker.join(10)
    assert not worker.is_alive()
    assert not errors
    assert socket.create_connection is original


def test_local_server_accepts_and_responds_during_boundary():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"fictional-local-api-responsive"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with local_only_network_boundary():
            # A distinct client process models the desktop webview; no external
            # host is contacted. The server runs inside the protected process.
            code = (
                "import urllib.request\n"
                "print(urllib.request.urlopen("
                + repr(f"http://127.0.0.1:{server.server_port}/")
                + ", timeout=5).read().decode())"
            )
            child = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            assert child.stdout.strip() == "fictional-local-api-responsive"
            with pytest.raises(LocalOnlyNetworkBlocked):
                socket.create_connection(("192.0.2.1", 9))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("operation", ["stream", "datagram", "raw_socket"])
def test_async_outbound_paths_fail_closed(operation):
    async def check():
        loop = asyncio.get_running_loop()
        with local_only_network_boundary():
            with pytest.raises(LocalOnlyNetworkBlocked):
                if operation == "stream":
                    await asyncio.open_connection("192.0.2.1", 9)
                elif operation == "datagram":
                    await loop.create_datagram_endpoint(
                        asyncio.DatagramProtocol, remote_addr=("192.0.2.1", 9)
                    )
                else:
                    with socket.socket() as outbound:
                        outbound.setblocking(False)
                        await loop.sock_connect(outbound, ("192.0.2.1", 9))

    asyncio.run(check())


def test_async_server_accepts_during_boundary():
    async def check():
        handled = asyncio.Event()

        async def respond(reader, writer):
            writer.write(b"fictional-async-response")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            handled.set()

        server = await asyncio.start_server(respond, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            with local_only_network_boundary():
                code = (
                    "import socket\n"
                    f"s=socket.create_connection(('127.0.0.1',{port}), timeout=5)\n"
                    "print(s.recv(128).decode())\ns.close()"
                )
                child = await asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                assert child.stdout.strip() == "fictional-async-response"
                await asyncio.wait_for(handled.wait(), 5)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(check())

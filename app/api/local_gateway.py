"""Common, content-free HTTP protection for both desktop API dispatch targets.

This is a loopback/browser boundary, not multi-user authentication. Route-level
matter, capability, and role checks remain mandatory. No request body is logged.
"""

from __future__ import annotations

import asyncio
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from legal.security.local_api_abuse_guard import LocalApiAbuseGuard
from legal.security.local_request_firewall import DEFAULT_MAX_BODY_BYTES, evaluate_local_request


class LocalGatewayProtection:
    def __init__(self, app, *, max_body_bytes=DEFAULT_MAX_BODY_BYTES, body_timeout=30):
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.body_timeout = body_timeout
        self.abuse_guard = LocalApiAbuseGuard()

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        event_id = uuid.uuid4().hex
        scope.setdefault("state", {})["mfll_audit_event_id"] = event_id
        headers = Headers(scope=scope)
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        client = (scope.get("client") or (None,))[0]

        async def guarded_send(message):
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                response_headers["X-MFLL-Audit-Event-Id"] = event_id
                response_headers["X-Request-ID"] = event_id
                response_headers["Cache-Control"] = "no-store, max-age=0"
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["Referrer-Policy"] = "no-referrer"
                response_headers.setdefault(
                    "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                )
                response_headers.setdefault("X-Frame-Options", "DENY")
            await send(message)

        async def deny(status, code, retry=None):
            response = JSONResponse(
                status_code=status,
                content={"detail": code, "request_id": event_id, "review_required": True},
                headers={"Retry-After": str(retry)} if retry else None,
            )
            await response(scope, receive, guarded_send)

        # Reject duplicate routing/framing headers instead of choosing one of
        # several conflicting identities or Content-Length interpretations.
        for name in (b"host", b"origin", b"content-length", b"transfer-encoding"):
            if sum(key.lower() == name for key, _ in scope.get("headers", [])) > 1:
                await deny(400, "ambiguous_request_headers")
                return
        if headers.get("transfer-encoding") and headers.get("content-length"):
            await deny(400, "ambiguous_request_framing")
            return
        decision = evaluate_local_request(
            method=method,
            path=path,
            client_host=client,
            host_header=headers.get("host", ""),
            origin_header=headers.get("origin", ""),
            sec_fetch_site=headers.get("sec-fetch-site", ""),
            content_length=headers.get("content-length", ""),
            max_body_bytes=self.max_body_bytes,
            require_content_length=path == "/ask/stream",
        )
        if not decision.allowed:
            await deny(decision.status_code, decision.code)
            return
        rate = self.abuse_guard.check(method=method, path=path, client_host=client)
        if not rate.allowed:
            await deny(429, rate.code, rate.retry_after_seconds)
            return

        # Buffer only a bounded request payload. Replay it once, then retain the
        # real receive channel for streaming-response disconnect/cancellation.
        replay_receive = receive
        if method not in {"GET", "HEAD", "OPTIONS"}:
            body = bytearray()
            deadline = asyncio.get_running_loop().time() + self.body_timeout
            while True:
                try:
                    message = await asyncio.wait_for(
                        receive(), max(0, deadline - asyncio.get_running_loop().time())
                    )
                except TimeoutError:
                    await deny(408, "request_body_timeout")
                    return
                if message["type"] != "http.request":
                    await deny(400, "request_body_incomplete")
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.max_body_bytes:
                    await deny(413, "request_too_large")
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
            declared = headers.get("content-length")
            if declared is not None and int(declared) != len(body):
                await deny(400, "request_body_length_mismatch")
                return
            delivered = False

            async def replay_receive():
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_receive, guarded_send)

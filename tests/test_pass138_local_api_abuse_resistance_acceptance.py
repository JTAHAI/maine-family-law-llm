from __future__ import annotations

from legal.security.local_api_abuse_guard import LocalApiAbuseGuard
from legal.security.local_request_firewall import evaluate_local_request


def test_pass138_rate_guard_bounds_write_bursts_without_retaining_token_or_content() -> None:
    guard = LocalApiAbuseGuard(window_seconds=60, read_limit=3, write_limit=2, max_buckets=8)
    first = guard.check(method="POST", path="/api/records/open/" + "a" * 64, client_host="127.0.0.1", now=10)
    second = guard.check(method="POST", path="/api/records/open/" + "b" * 64, client_host="127.0.0.1", now=11)
    blocked = guard.check(method="POST", path="/api/records/open/" + "c" * 64, client_host="127.0.0.1", now=12)
    assert first.allowed and second.allowed
    assert blocked.allowed is False
    assert blocked.code == "local_rate_limited"
    assert blocked.retry_after_seconds > 0
    status = guard.status()
    assert status["retains_content"] is False
    assert status["active_bucket_count"] == 1


def test_pass138_rate_guard_expires_burst_and_separates_read_write_budgets() -> None:
    guard = LocalApiAbuseGuard(window_seconds=10, read_limit=2, write_limit=1)
    assert guard.check(method="POST", path="/api/query", client_host="::1", now=0).allowed
    assert not guard.check(method="POST", path="/api/query", client_host="::1", now=1).allowed
    assert guard.check(method="GET", path="/api/query", client_host="::1", now=1).allowed
    assert guard.check(method="POST", path="/api/query", client_host="::1", now=11).allowed


def test_pass138_firewall_still_rejects_cross_origin_before_any_rate_budget() -> None:
    decision = evaluate_local_request(
        method="POST",
        path="/api/security/privacy/backup",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8765",
        origin_header="http://127.0.0.1:9999",
        sec_fetch_site="cross-site",
        content_length="2",
    )
    assert decision.allowed is False
    assert decision.code == "cross_origin_blocked"

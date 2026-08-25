"""v5.2 loopback request, token, and bounded open-cache hardening tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from legal.security.local_request_firewall import DEFAULT_MAX_BODY_BYTES, evaluate_local_request
from maine_family_law_llm import api


def test_loopback_firewall_allows_local_browser_and_test_client() -> None:
    for host, client in (
        ("127.0.0.1:8000", "127.0.0.1"),
        ("[::1]:8000", "::1"),
        ("testserver", "testclient"),
    ):
        decision = evaluate_local_request(
            method="GET",
            path="/health",
            client_host=client,
            host_header=host,
        )
        assert decision.allowed is True
        assert decision.status_code == 200


def test_loopback_firewall_blocks_rebinding_cross_origin_and_cross_site_post() -> None:
    invalid_host = evaluate_local_request(
        method="GET",
        path="/health",
        client_host="127.0.0.1",
        host_header="evil.example",
    )
    assert invalid_host.allowed is False
    assert invalid_host.code == "invalid_host"

    cross_origin = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        origin_header="https://evil.example",
    )
    assert cross_origin.allowed is False
    assert cross_origin.code == "cross_origin_blocked"

    cross_port_loopback = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        origin_header="http://127.0.0.1:8111",
    )
    assert cross_port_loopback.allowed is False
    assert cross_port_loopback.code == "cross_origin_blocked"

    same_origin_loopback = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        origin_header="http://127.0.0.1:8000",
    )
    assert same_origin_loopback.allowed is True

    cross_site = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        sec_fetch_site="cross-site",
    )
    assert cross_site.allowed is False
    assert cross_site.code == "cross_site_blocked"


def test_loopback_firewall_rejects_invalid_and_oversized_lengths() -> None:
    malformed = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        content_length="not-a-number",
    )
    assert malformed.code == "invalid_content_length"
    assert malformed.status_code == 400

    oversized = evaluate_local_request(
        method="POST",
        path="/ask",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        content_length=str(DEFAULT_MAX_BODY_BYTES + 1),
    )
    assert oversized.code == "request_too_large"
    assert oversized.status_code == 413

    streaming_without_length = evaluate_local_request(
        method="POST",
        path="/ask/stream",
        client_host="127.0.0.1",
        host_header="127.0.0.1:8000",
        require_content_length=True,
    )
    assert streaming_without_length.code == "content_length_required"
    assert streaming_without_length.status_code == 411


def test_api_middleware_blocks_bad_host_and_cross_origin_before_route_execution() -> None:
    client = TestClient(api.app)
    response = client.get("/health", headers={"host": "evil.example"})
    assert response.status_code == 403
    assert response.json()["detail"] == "invalid_host"

    response = client.post(
        "/ask",
        headers={"host": "testserver", "origin": "https://evil.example"},
        json={"question": "This route must never execute."},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "cross_origin_blocked"


def test_api_middleware_bounds_body_even_without_trusting_route_schema() -> None:
    client = TestClient(api.app)
    response = client.post(
        "/ask",
        headers={"host": "testserver", "content-type": "application/octet-stream"},
        content=b"x" * (DEFAULT_MAX_BODY_BYTES + 1),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request_too_large"


def test_record_capabilities_are_unique_under_concurrency(tmp_path: Path) -> None:
    api._record_open_tokens.clear()
    case_root = tmp_path / "case"
    case_root.mkdir()
    with ThreadPoolExecutor(max_workers=12) as pool:
        tokens = list(pool.map(lambda i: api._record_open_token(case_root, f"REC-{i}"), range(240)))
    assert len(tokens) == len(set(tokens)) == 240
    assert all(len(token) == 64 for token in tokens)


def test_open_cache_is_contained_hash_named_and_reused(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    data = b"bounded nested record bytes"
    first = api._materialize_open_cache(case_root, data, ".pdf")
    second = api._materialize_open_cache(case_root, data, ".pdf")
    assert first == second
    assert first.parent == (case_root / "04_INDEXES" / "open_cache").resolve()
    assert first.name.endswith(".pdf")
    assert first.read_bytes() == data


def test_open_cache_rejects_symlinked_cache_root(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    outside = tmp_path / "outside"
    (case_root / "04_INDEXES").mkdir(parents=True)
    outside.mkdir()
    cache = case_root / "04_INDEXES" / "open_cache"
    try:
        cache.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(HTTPException) as exc:
        api._materialize_open_cache(case_root, b"data", ".txt")
    assert exc.value.status_code == 409
    assert exc.value.detail == "record_open_cache_unsafe"


def test_api_source_mirrors_remain_identical() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "src/maine_family_law_llm/api.py").read_bytes() == (
        root / "maine_family_law_llm/api.py"
    ).read_bytes()

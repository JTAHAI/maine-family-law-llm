from __future__ import annotations


def test_existing_service_must_match_the_current_runtime_version(monkeypatch) -> None:
    from app import local_api_service

    monkeypatch.setattr(
        local_api_service,
        "_health_payload",
        lambda _port, timeout=1.5: {"status": "ok", "version": "3.1.0"},
    )
    assert local_api_service._service_matches_runtime_version(8000) is False

    monkeypatch.setattr(
        local_api_service,
        "_health_payload",
        lambda _port, timeout=1.5: {"status": "ok", "version": local_api_service.VERSION},
    )
    assert local_api_service._service_matches_runtime_version(8000) is True

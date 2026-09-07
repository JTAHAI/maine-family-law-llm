"""Production HTTP source trust, distinct from the development fixture app."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.api.production import ProductionApplication, app
from app.api.release_boundary import production_request_active
from maine_family_law_llm import api


@pytest.fixture
def no_admitted_authority(monkeypatch, tmp_path):
    monkeypatch.setenv("MFL_RUNTIME_MODE", "source")
    monkeypatch.setenv("MFL_USE_ACTIVE_AUTHORITY_IN_SOURCE", "0")
    monkeypatch.setenv("MFL_CASE_LIBRARY_PATH", str(tmp_path / "empty-library.json"))

    class Unavailable:
        def __init__(self):
            raise RuntimeError("fictional unadmitted authority")

    called = []

    def forbidden_fixture(*args, **kwargs):
        called.append("fixture")
        raise AssertionError("Production must not consult development fixtures")

    monkeypatch.setattr(api, "AuthorityProductService", Unavailable)
    monkeypatch.setattr(api, "retrieve_fixture_sources", forbidden_fixture)
    monkeypatch.setattr(api, "load_seed_manifest", forbidden_fixture)
    return called


@pytest.mark.parametrize("route", ["/ask", "/api/chat", "/ask/stream"])
@pytest.mark.parametrize("mode", ["maine_law", "both"])
def test_source_launched_production_chat_cannot_use_seed_authority(
    no_admitted_authority, route, mode
):
    response = TestClient(app).post(route, json={
        "question": "FICTIONAL QA: What sources apply to a parenting order?",
        "search_mode": mode,
    }, headers={"X-Production-Request": "false", "X-Runtime-Mode": "source"})
    assert response.status_code == 200
    if route == "/ask/stream":
        frames = [json.loads(line[6:]) for line in response.text.splitlines()
                  if line.startswith("data: ")]
        payload = next(frame["payload"] for frame in frames if "payload" in frame)
    else:
        payload = response.json()
    assert payload["grounded"] is False
    assert payload["citations"] == []
    assert payload.get("review_required", True) is True
    assert not no_admitted_authority
    assert production_request_active.get() is False


@pytest.mark.parametrize("route,status", [
    ("/sources", 503), ("/inspect-source/fictional-seed", 404),
    ("/inspect-source/fictional-seed?start_offset=0&end_offset=10", 404),
])
def test_legacy_source_routes_cannot_substitute_seeds_or_private_records(
    no_admitted_authority, route, status
):
    response = TestClient(app).get(route)
    assert response.status_code == status
    assert not no_admitted_authority
    assert "fictional unadmitted authority" not in response.text


def test_admitted_source_contract_still_reaches_product_facade(monkeypatch):
    # A facade contract fixture, not a real admitted build or legal E2E evidence.
    calls = []

    class Product:
        def list_sources(self, **kwargs):
            calls.append("list")
            return {"status": "pass", "sources": [{"source_id": "fictional-admitted"}]}

        def get_source_span(self, source_id, **kwargs):
            calls.append((source_id, kwargs))
            return {"status": "pass", "source_id": source_id, "review_required": True}

    monkeypatch.setattr(api, "AuthorityProductService", Product)
    client = TestClient(app)
    assert client.get("/sources").json() == [{"source_id": "fictional-admitted"}]
    result = client.get("/inspect-source/fictional-admitted?start_offset=1&end_offset=4")
    assert result.status_code == 200
    assert result.json()["review_required"] is True
    assert calls == ["list", ("fictional-admitted", {"start_offset": 1, "end_offset": 4})]


def test_production_context_resets_on_exception_and_cancellation():
    async def run():
        application = ProductionApplication()
        for failure in (RuntimeError, asyncio.CancelledError):
            async def fail(scope, receive, send, failure_type=failure):
                assert production_request_active.get() is True
                raise failure_type()
            application._protected_dispatch = fail
            with pytest.raises(failure):
                await application({"type": "http"}, None, None)
            assert production_request_active.get() is False
    asyncio.run(run())

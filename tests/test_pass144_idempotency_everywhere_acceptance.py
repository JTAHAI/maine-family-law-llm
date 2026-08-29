from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from legal.runtime.idempotency import IdempotencyMiddleware, IdempotencyRegistry


def _headers(*, key: str = "idem-fictional-action-0001", tenant: str = "tenant-fictional") -> dict[str, str]:
    return {
        "X-MFLL-Idempotency-Key": key,
        "X-User-Role": "reviewer",
        "X-Tenant-Id": tenant,
        "X-MFLL-Client-Session": "a" * 48,
    }


def _app(root, state: dict[str, int]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        IdempotencyMiddleware,
        registry_factory=lambda: IdempotencyRegistry(root=root, encryption_key="fictional-test-key"),
        matter_scope_resolver=lambda: "fictional-matter-only",
    )

    @app.post("/api/fictional/save")
    def save(payload: dict[str, str]) -> dict[str, object]:
        state["writes"] += 1
        return {"write_number": state["writes"], "review_required": True, "echo": payload["label"]}

    return app


def test_pass144_duplicate_mutation_replays_only_same_bound_request(tmp_path) -> None:
    state = {"writes": 0}
    client = TestClient(_app(tmp_path, state))
    first = client.post("/api/fictional/save", json={"label": "fictional family record"}, headers=_headers())
    replay = client.post("/api/fictional/save", json={"label": "fictional family record"}, headers=_headers())

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert state["writes"] == 1
    assert first.headers["x-mfll-idempotency-status"] == "recorded"
    assert replay.headers["x-mfll-idempotency-status"] == "replayed"

    changed = client.post("/api/fictional/save", json={"label": "different fictional record"}, headers=_headers())
    assert changed.status_code == 409
    assert changed.json()["detail"] == "idempotency_key_reused_for_different_request"
    assert state["writes"] == 1


def test_pass144_binding_prevents_cross_tenant_or_matter_replay_and_state_is_encrypted(tmp_path) -> None:
    state = {"writes": 0}
    client = TestClient(_app(tmp_path, state))
    body = {"label": "fictional confidential text must stay encrypted"}
    assert client.post("/api/fictional/save", json=body, headers=_headers()).status_code == 200
    other_tenant = client.post("/api/fictional/save", json=body, headers=_headers(tenant="tenant-other"))

    assert other_tenant.status_code == 200
    assert other_tenant.headers["x-mfll-idempotency-status"] == "recorded"
    assert state["writes"] == 2
    encrypted = (tmp_path / "registry.json.enc").read_bytes()
    assert b"fictional confidential text" not in encrypted
    status = IdempotencyRegistry(root=tmp_path, encryption_key="fictional-test-key").status()
    assert status["completed_entries"] == 2
    assert status["scope_binding"] == ["method", "route", "tenant", "role", "browser_session", "active_matter", "request_hash"]
    assert status["network_used"] is False


def test_pass144_transition_and_enforcement_modes_are_explicit(tmp_path, monkeypatch) -> None:
    state = {"writes": 0}
    client = TestClient(_app(tmp_path, state))
    legacy_one = client.post("/api/fictional/save", json={"label": "first"})
    legacy_two = client.post("/api/fictional/save", json={"label": "first"})
    assert legacy_one.headers["x-mfll-idempotency-status"] == "not_provided"
    assert legacy_two.headers["x-mfll-idempotency-status"] == "not_provided"
    assert state["writes"] == 2

    monkeypatch.setenv("MFL_REQUIRE_IDEMPOTENCY_KEYS", "1")
    required = client.post("/api/fictional/save", json={"label": "blocked"})
    assert required.status_code == 428
    assert required.json()["detail"] == "idempotency_key_required"
    assert state["writes"] == 2


def test_pass144_shipped_local_api_and_ui_expose_the_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MFL_RUNTIME_STATE_ROOT", str(tmp_path / "runtime"))
    from maine_family_law_llm.api import app as local_app

    client = TestClient(local_app)
    response = client.get("/api/runtime/idempotency-status", headers=_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["response_storage"] == "encrypted_local_runtime_state"
    assert payload["matter_scope"] == "request-bound; no matter records returned"

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    script = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    page = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    assert "X-MFLL-Idempotency-Key" in script
    assert "idempotencyProtectionRefresh" in script
    assert "/api/runtime/idempotency-status" in script
    assert "Duplicate action protection" in page

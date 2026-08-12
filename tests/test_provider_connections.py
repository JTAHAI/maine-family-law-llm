from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes import deliberation as deliberation_routes
from app.api.routes import providers as provider_routes
from app.web.ui_inventory import UIViewInventory
from legal.deliberation.host import DeliberationHost
from legal.provider_connections import (
    ExternalProviderAdapter,
    OutboundManifest,
    ProviderConnectionService,
    WindowsCredentialStore,
    validate_manifest_transition,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeWin32Cred:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    def __init__(self) -> None:
        self.storage: dict[str, dict[str, object]] = {}
        self.writes: list[dict[str, object]] = []
        self.deletes: list[str] = []

    def CredWrite(self, credential: dict[str, object], flags: int) -> None:
        target = str(credential["TargetName"])
        self.storage[target] = dict(credential)
        self.writes.append(dict(credential))

    def CredRead(self, target: str, cred_type: int, flags: int) -> dict[str, object]:
        if target not in self.storage:
            raise KeyError(target)
        return dict(self.storage[target])

    def CredDelete(self, target: str, cred_type: int, flags: int) -> None:
        self.storage.pop(target, None)
        self.deletes.append(target)

    def CredEnumerate(self, prefix: str, flags: int) -> tuple[int, list[dict[str, object]]]:
        rows = [dict(value) for key, value in self.storage.items() if key.startswith(prefix)]
        return len(rows), rows


def _fake_store() -> WindowsCredentialStore:
    backend = FakeWin32Cred()
    return WindowsCredentialStore(namespace="test-provider-store", backend=backend)  # type: ignore[arg-type]


def _service(tmp_path: Path, transport=None) -> ProviderConnectionService:
    backend = FakeWin32Cred()
    store = WindowsCredentialStore(namespace="test-provider-store", backend=backend)  # type: ignore[arg-type]
    return ProviderConnectionService(
        project_root=ROOT,
        store_root=tmp_path / "provider-store",
        credential_store=store,
        transport=transport,
    )


def test_provider_service_stores_byok_credentials_without_leaking_secrets(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def transport(endpoint_url: str, request_path: str, headers: dict[str, str], body: bytes, timeout_seconds: int):
        captured["endpoint_url"] = endpoint_url
        captured["request_path"] = request_path
        captured["headers"] = dict(headers)
        captured["body"] = body
        return 200, "{\"ok\":true}", {"x-provider": "fake"}

    service = _service(tmp_path, transport=transport)
    service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-secret-123",
            "pinned_model_id": "model-1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
            "retention_mode": "operator_controlled",
            "region_data_controls": "us",
            "cost_estimate_basis": "operator_pricing",
        },
    )

    manifest = service.build_manifest(
        run_id="run-123",
        provider_id="openai",
        payload={
            "consent_mode": "selected_excerpts",
            "purpose": "deliberation",
            "question": "Should we include this record?",
            "selected_excerpts": [
                {
                    "excerpt_id": "ex-1",
                    "text": "Keep the record excerpt bounded.",
                    "source_path": "C:\\Users\\justi\\Secrets\\matter.txt",
                    "api_key": "should-not-appear",
                }
            ],
            "allowed_tools": ["records.search"],
            "source_lanes": ["private_record"],
            "estimated_tokens": 120,
            "estimated_cost_usd": 0.12,
            "retention_data_control_summary": "Provider retention stays separate from the app.",
            "metadata": {"source_path": "C:\\Users\\justi\\Secrets\\matter.txt", "matter_id": "matter-9"},
        },
    )
    assert manifest.exact_payload["metadata"]["source_path"] == "[redacted_path]"
    assert "sk-secret-123" not in json.dumps(manifest.as_dict())

    approval = service.approve_manifest(manifest.manifest_id, actor="reviewer-1")
    assert approval.payload_sha256 == manifest.payload_sha256

    start = service.start_external(manifest.manifest_id)
    assert start["transmitted"] is True
    assert start["status"] == "transmitted"
    assert captured["request_path"] == "/v1/responses"
    assert sha256(captured["body"]).hexdigest() == manifest.payload_sha256
    assert captured["body"] == json.dumps(manifest.exact_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    repo_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in tmp_path.rglob("*") if path.is_file())
    assert "sk-secret-123" not in repo_text
    assert "CredentialBlob" not in repo_text


def test_changed_payload_blocks_transmission(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-secret-123",
            "pinned_model_id": "model-1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
        },
    )
    manifest = service.build_manifest(
        run_id="run-123",
        provider_id="openai",
        payload={
            "consent_mode": "question_only",
            "purpose": "deliberation",
            "question": "Should we include this record?",
            "selected_excerpts": [],
            "allowed_tools": ["records.search"],
            "source_lanes": ["private_record"],
            "estimated_tokens": 120,
            "retention_data_control_summary": "Provider retention stays separate from the app.",
        },
    )
    service.approve_manifest(manifest.manifest_id, actor="reviewer-1")
    service._manifests[manifest.manifest_id] = OutboundManifest(
        **{**manifest.as_dict(), "exact_payload": {**manifest.exact_payload, "question": "Changed question"}}
    )
    try:
        service.start_external(manifest.manifest_id)
    except Exception as exc:
        assert getattr(exc, "code", "") in {"payload_hash_mismatch", "payload_changed"}
    else:  # pragma: no cover - defensive
        raise AssertionError("payload change should have blocked transmission")


def test_provider_credentials_remain_namespaced(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-openai",
            "pinned_model_id": "model-a",
            "endpoint_url": "https://openai.example",
            "request_path": "/v1/responses",
        },
    )
    service.connect(
        "xai",
        {
            "account_label": "primary",
            "api_key": "sk-xai",
            "pinned_model_id": "model-b",
            "endpoint_url": "https://xai.example",
            "request_path": "/v1/responses",
        },
    )
    openai_status = service.credential_store.credential_status("openai", account_label="primary")
    xai_status = service.credential_store.credential_status("xai", account_label="primary")
    assert openai_status.exists is True
    assert xai_status.exists is True
    assert openai_status.target_name != xai_status.target_name


def test_provider_contract_reports_support_and_isolation() -> None:
    adapter = ExternalProviderAdapter(
        provider_id="openai",
        api_class="responses_api",
        pinned_model_id="gpt-4.1",
        endpoint_class="https_json_api",
        request_path="/v1/responses",
        supports_structured_output=True,
        supports_streaming=True,
        supports_cancellation=True,
        requested_retention_mode="operator_controlled",
        region_data_controls="us",
        cost_estimate_basis="operator_pricing",
        documented_data_controls="API inputs are retained under the provider policy surface.",
        tool_support=["read_only_host_mediated_tools"],
        compatibility_profile_version="2026.08.08",
        last_successful_contract_test="2026-08-08",
        last_contract_test="2026-08-08",
        actual_usage={"prompt_tokens": 32, "completion_tokens": 12},
        retention_text="API inputs are not used to train default models.",
    )

    report = adapter.contract_report()
    assert report["provider"] == "openai"
    assert report["official_api_class"] == "responses_api"
    assert report["structured_output"] is True
    assert report["streaming"] is True
    assert report["cancellation"] is True
    assert report["actual_usage"]["prompt_tokens"] == 32
    assert adapter.disconnect()["status"] == "disconnected"
    assert adapter.revoke()["status"] == "revoked"


def test_provider_status_sharing_summary_and_local_only_route(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(provider_routes, "_service", lambda: service)
    client = TestClient(app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-a", "host": "testserver"}

    connect = client.post(
        "/api/providers/openai/connect",
        headers=headers,
        json={
            "account_label": "primary",
            "api_key": "sk-openai",
            "pinned_model_id": "gpt-4.1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
            "budget_controls": {
                "provider_cap_usd": 10,
                "round_cap": 2,
                "context_cap": 4096,
                "output_cap": 6000,
                "tool_call_cap": 3,
                "private_record_tool_cap": 2,
                "retry_cap": 1,
                "timeout_seconds": 120,
                "circuit_breaker": "operator_controlled",
            },
        },
    )
    assert connect.status_code == 200, connect.text

    status = client.get("/api/providers/openai/status", headers=headers)
    assert status.status_code == 200, status.text
    assert status.json()["provider"]["provider_id"] == "openai"

    summary = client.get("/api/providers/sharing-summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["sharing_summary"]["provider_count"] >= 1

    local_only = client.post("/api/providers/return-local-only", headers=headers)
    assert local_only.status_code == 200, local_only.text
    assert local_only.json()["local_only"] is True

    disconnected = client.post("/api/providers/disconnect-all", headers=headers)
    assert disconnected.status_code == 200, disconnected.text

    revoked = client.post("/api/providers/revoke-all", headers=headers)
    assert revoked.status_code == 200, revoked.text


def test_exact_hash_approval_budget_and_consent_validation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-secret-123",
            "pinned_model_id": "gpt-4.1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
        },
    )
    manifest = service.build_manifest(
        run_id="run-123",
        provider_id="openai",
        payload={
            "consent_mode": "selected_excerpts",
            "purpose": "deliberation",
            "question": "Should we include this record?",
            "selected_excerpts": [{"excerpt_id": "ex-1", "text": "Previewed excerpt only."}],
            "allowed_tools": ["records.search"],
            "source_lanes": ["private_record"],
            "estimated_tokens": 120,
            "estimated_cost_usd": 0.12,
            "budget_controls": {"provider_cap_usd": 1.0, "context_cap": 500, "tool_call_cap": 2},
            "retention_data_control_summary": "Provider retention stays separate from the app.",
        },
    )
    approval = service.approve_manifest(manifest.manifest_id, actor="reviewer-1")
    assert approval.payload_sha256 == manifest.payload_sha256
    assert validate_manifest_transition(manifest, manifest) == []
    model_changed = OutboundManifest(**{**manifest.as_dict(), "pinned_model_id": "other-model"})
    tool_changed = OutboundManifest(**{**manifest.as_dict(), "allowed_tools": ["records.search", "records.get_slice"]})
    scope_changed = OutboundManifest(
        **{**manifest.as_dict(), "exact_text_excerpt_ids": ["ex-1", "ex-2"], "source_lanes": ["private_record", "authority"]}
    )
    assert "model_changed" in validate_manifest_transition(manifest, model_changed)
    assert "tool_permissions_changed" in validate_manifest_transition(manifest, tool_changed)
    assert "source_selection_changed" in validate_manifest_transition(manifest, scope_changed)

    start = service.start_external(manifest.manifest_id)
    assert start["transmitted"] is False
    assert start["reason"] == "transport_unavailable_in_this_slice"

    tampered = OutboundManifest(
        **{**manifest.as_dict(), "exact_payload": {**manifest.exact_payload, "question": "Changed question"}}
    )
    service._manifests[manifest.manifest_id] = tampered
    try:
        service.start_external(manifest.manifest_id)
    except Exception as exc:
        assert getattr(exc, "code", "") in {"payload_hash_mismatch", "payload_changed"}
    else:  # pragma: no cover - defensive
        raise AssertionError("payload change should have blocked transmission")

    service._manifests[manifest.manifest_id] = manifest
    try:
        service.build_manifest(
            run_id="run-123",
            provider_id="openai",
            payload={
                "consent_mode": "whole_matter",
                "purpose": "deliberation",
                "question": "Should we include this record?",
                "selected_excerpts": [],
                "allowed_tools": ["records.search"],
                "source_lanes": ["private_record"],
                "estimated_tokens": 120,
            },
        )
    except Exception as exc:
        assert getattr(exc, "code", "") == "whole_matter_prohibited"
    else:  # pragma: no cover - defensive
        raise AssertionError("whole matter transmission should have been blocked")

    budget_service = _service(tmp_path / "budget")
    budget_service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-secret-456",
            "pinned_model_id": "gpt-4.1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
        },
    )
    budget_manifest = budget_service.build_manifest(
        run_id="run-budget",
        provider_id="openai",
        payload={
            "consent_mode": "question_only",
            "purpose": "deliberation",
            "question": "Budget should stop this run.",
            "selected_excerpts": [],
            "allowed_tools": ["records.search", "records.get_slice", "authority.search", "authority.get_span"],
            "source_lanes": ["private_record"],
            "estimated_tokens": 1024,
            "estimated_cost_usd": 9.99,
            "budget_controls": {"provider_cap_usd": 1.0, "context_cap": 512, "tool_call_cap": 2},
            "retention_data_control_summary": "Provider retention stays separate from the app.",
        },
    )
    budget_service.approve_manifest(budget_manifest.manifest_id, actor="reviewer-1")
    try:
        budget_service.start_external(budget_manifest.manifest_id)
    except Exception as exc:
        assert getattr(exc, "code", "") == "budget_exhausted"
    else:  # pragma: no cover - defensive
        raise AssertionError("budget exhaustion should have blocked transmission")


def test_provider_routes_and_local_only_deliberation_do_not_call_transport(tmp_path: Path, monkeypatch) -> None:
    transport_calls: list[tuple] = []

    def transport(*args, **kwargs):
        transport_calls.append(args)
        return 200, "{}", {}

    service = _service(tmp_path, transport=transport)
    monkeypatch.setattr(provider_routes, "_service", lambda: service)
    monkeypatch.setattr(deliberation_routes, "PROVIDER_SERVICE", service)
    host = DeliberationHost(project_root=ROOT, root=tmp_path / "deliberation")
    monkeypatch.setattr(deliberation_routes, "HOST", host)
    client = TestClient(app)

    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-a"}
    assert client.get("/api/providers", headers=headers).status_code == 200
    created = client.post(
        "/api/deliberation/runs",
        headers=headers,
        json={
            "preset_id": "quick_local_second_opinion",
            "matter_id": "matter-1",
            "question": "Is the local packet enough?",
            "user_role": "reviewer",
            "jurisdiction": "maine",
            "desired_output": "review_required_synthesis",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
        },
    )
    assert created.status_code == 200
    page = Path("app/web/pages/connections-deliberation.tsx").read_text(encoding="utf-8")
    for marker in [
        "data-provider-status-card",
        "data-exact-outbound-preview",
        "data-redactions",
        "data-approval",
        "data-live-timeline",
        "data-participation",
        "data-failures",
        "data-budgets",
        "data-final-verified-synthesis",
        "data-sharing-summary",
        "data-privacy-controls",
    ]:
        assert marker in page
    ui_report = UIViewInventory("app/web/pages").validate()
    assert ui_report["status"] == "pass", ui_report
    assert transport_calls == []


def test_provider_usage_and_cancellation_are_visible(tmp_path: Path) -> None:
    def transport(endpoint_url: str, request_path: str, headers: dict[str, str], body: bytes, timeout_seconds: int):
        return 200, "{\"ok\":true}", {}

    service = _service(tmp_path, transport=transport)
    service.connect(
        "openai",
        {
            "account_label": "primary",
            "api_key": "sk-secret-123",
            "pinned_model_id": "model-1",
            "endpoint_url": "https://provider.example",
            "request_path": "/v1/responses",
        },
    )
    manifest = service.build_manifest(
        run_id="run-123",
        provider_id="openai",
        payload={
            "consent_mode": "question_only",
            "purpose": "deliberation",
            "question": "Should we include this record?",
            "selected_excerpts": [],
            "allowed_tools": ["records.search"],
            "source_lanes": ["private_record"],
            "estimated_tokens": 120,
            "estimated_cost_usd": 0.12,
            "retention_data_control_summary": "Provider retention stays separate from the app.",
        },
    )
    service.approve_manifest(manifest.manifest_id, actor="reviewer-1", run_id="run-123")
    service.start_external(manifest.manifest_id, run_id="run-123")

    usage = service.usage("run-123")
    assert usage["provider_count"] == 1
    assert usage["provider_sessions"][0]["budget"]["estimated_tokens"] == 120
    cancelled = service.cancel("run-123")
    assert cancelled["status"] == "cancelled"
    assert cancelled["provider_sessions"][0]["status"] == "cancelled"


def test_provider_api_endpoints_are_registered() -> None:
    from app.api.contracts import EndpointInventory

    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and str(path).startswith("/api"):
                registered.add((method, str(path)))
    report = EndpointInventory().compare_to_registered(registered)
    assert report["status"] == "pass", report


def test_missing_provider_credential_is_reported_without_exposing_secret(tmp_path: Path) -> None:
    service = _service(tmp_path)
    status = service.credential_store.credential_status("openai", account_label="primary")
    assert status.exists is False
    assert status.credential_status == "missing"

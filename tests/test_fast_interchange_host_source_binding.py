from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_v55_immutable_authority_product import _fixture_data_root

from app.services.local_agent_context_service import (
    LocalAgentApprovalStore,
    LocalAgentAuditStore,
    LocalAgentContextError,
    LocalAgentContextService,
    text_digest,
)
from legal.agent_runtime import LocalModelResponse, LoopbackEndpointPolicy
from legal.production import AuthorityProductPublisher
from maine_family_law_llm import api


class RecordingClient:
    provider_id = "ollama"
    model_name = "fictional-model"
    endpoint = LoopbackEndpointPolicy().validate("http://127.0.0.1:11434")

    def __init__(self):
        self.prompts = []

    def generate_response(self, prompt):
        self.prompts.append(prompt)
        return LocalModelResponse(
            text="Fictional source observation [1]. Review required.",
            provider_id=self.provider_id,
            model_id=self.model_name,
            endpoint_class=self.endpoint.endpoint_class,
            usage={},
            finish_reason="stop",
        )


@pytest.fixture
def bound_host(monkeypatch, tmp_path):
    root = tmp_path / "fictional-matter"
    path = root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "REC-1.txt"
    path.parent.mkdir(parents=True)
    text = "Fictional family record: an attachment is missing. Review required."
    path.write_text(text, encoding="utf-8")
    row = {
        "evidence_id": "REC-1",
        "source_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "private_copy_relpath": path.relative_to(root).as_posix(),
        "source_type": "txt",
        "source_locator": "REC-1.txt",
        "text_content": "FORGED_INDEX_CANARY",
    }
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: [row])
    monkeypatch.setattr(api, "_record_open_tokens", {})
    monkeypatch.setattr(api, "_local_agent_approvals", LocalAgentApprovalStore())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "f" * 32)
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
    }
    owner = {"role": "reviewer", "tenant_id": "fictional-tenant", "client_session_id": "a" * 48}
    context = api._record_capability_identity.set(owner)
    try:
        token = api._record_open_token(root, "REC-1", "REC-1.txt")
    finally:
        api._record_capability_identity.reset(context)
    ref = {
        "lane": "private_record",
        "source_id": "REC-1",
        "source_sha256": row["source_hash"],
        "text_sha256": text_digest(text),
        "start_offset": 0,
        "end_offset": len(text),
        "record_token": token,
    }
    body = {
        "question": "What is missing from this fictional record?",
        "matter_id": api._case_id(root),
        "source_refs": [ref],
        "task": "evidence_review",
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "model": "fictional-model",
    }
    worker = RecordingClient()
    monkeypatch.setattr(api, "build_local_client", lambda **_kwargs: worker)
    return {
        "client": TestClient(api.app),
        "headers": headers,
        "owner": owner,
        "body": body,
        "worker": worker,
        "root": root,
        "path": path,
        "text": text,
        "row": row,
        "token": token,
    }


def preview(host, body=None):
    response = host["client"].post(
        "/api/local-agent/preview", json=body or host["body"], headers=host["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def approved_body(host, result):
    return {
        **deepcopy(host["body"]),
        "run_id": result["context_manifest"]["run_id"],
        "source_refs": result["source_refs"],
        "approval_token": result["approval_token"],
        "approved_manifest_sha256": result["context_manifest"]["manifest_sha256"],
    }


def run(host, body, headers=None):
    return host["client"].post(
        "/api/local-agent/run", json=body, headers=headers or host["headers"]
    )


def test_canonical_http_rehydrates_private_source_and_persists_encrypted_audit(bound_host):
    host = bound_host
    result = preview(host)
    assert not host["worker"].prompts
    assert result["source_cards"][0]["snippet"] == host["text"]
    response = run(host, approved_body(host, result))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["status"] == "completed_review_required"
    assert payload["citations"][0]["snippet"] == host["text"]
    assert payload["citations"][0]["source_reference"] == result["source_refs"][0]
    assert "FORGED_INDEX_CANARY" not in host["worker"].prompts[0]
    assert host["text"] in host["worker"].prompts[0]
    assert str(host["root"]) not in response.text
    audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
    raw = audit.path.read_bytes()
    assert host["text"].encode() not in raw and b"fictional-tenant" not in raw
    state = audit.encryptor.decrypt_json(json.loads(raw))
    assert [row["action"] for row in state["events"]] == ["preview", "dispatch", "result"]
    assert all(row["created_at"].endswith("Z") for row in state["events"])
    assert state["events"][-1]["receipt_sha256"] == payload["provenance_receipt"]["receipt_sha256"]


def test_delayed_user_approval_does_not_change_exact_manifest(bound_host, monkeypatch):
    from legal.agent_runtime import contracts

    monkeypatch.setattr(contracts, "utc_now", lambda: "2026-08-27T10:00:00Z")
    result = preview(bound_host)
    monkeypatch.setattr(contracts, "utc_now", lambda: "2026-08-27T10:01:00Z")
    response = run(bound_host, approved_body(bound_host, result))
    assert response.status_code == 200, response.text
    assert response.json()["context_manifest"] == result["context_manifest"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("question", "A different fictional question"),
        ("model", "different-model"),
        ("task", "drafting"),
        ("provider", "openai_compatible_local"),
        ("endpoint", "http://127.0.0.1:1234"),
        ("run_id", "another-run"),
        ("matter_id", "another-matter"),
        ("approved_manifest_sha256", "0" * 64),
    ],
)
def test_approval_is_bound_to_exact_request(bound_host, field, value):
    body = approved_body(bound_host, preview(bound_host))
    body[field] = value
    response = run(bound_host, body)
    assert response.status_code == 409, response.text
    assert not bound_host["worker"].prompts


@pytest.mark.parametrize(
    ("header", "value"),
    [
        ("X-User-Role", "attorney"),
        ("X-Tenant-Id", "other-tenant"),
        ("X-MFLL-Client-Session", "b" * 48),
    ],
)
def test_session_role_and_tenant_cannot_reuse_private_sources_or_approval(
    bound_host, header, value
):
    body = approved_body(bound_host, preview(bound_host))
    response = run(bound_host, body, {**bound_host["headers"], header: value})
    assert response.status_code in {403, 409}
    assert not bound_host["worker"].prompts and bound_host["text"] not in response.text


@pytest.mark.parametrize("missing", ["X-User-Role", "X-Tenant-Id", "X-MFLL-Client-Session"])
def test_explicit_local_identity_is_required(bound_host, missing):
    headers = {key: value for key, value in bound_host["headers"].items() if key != missing}
    response = bound_host["client"].post(
        "/api/local-agent/preview", json=bound_host["body"], headers=headers
    )
    assert response.status_code == 403
    assert not bound_host["worker"].prompts


def test_client_source_text_and_admission_claims_are_rejected_without_echo(bound_host):
    body = {
        **bound_host["body"],
        "source_cards": [
            {"snippet": "PRIVATE_FORGED_CANARY", "authority_status": "verified_official_maine"}
        ],
    }
    response = bound_host["client"].post(
        "/api/local-agent/preview", json=body, headers=bound_host["headers"]
    )
    assert response.status_code == 422
    assert "PRIVATE_FORGED_CANARY" not in response.text
    assert not bound_host["worker"].prompts


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_offset", 1),
        ("end_offset", 100000),
        ("text_sha256", "0" * 64),
        ("source_sha256", "0" * 64),
        ("source_id", "REC-2"),
    ],
)
def test_changed_or_invalid_record_reference_cannot_dispatch(bound_host, field, value):
    body = approved_body(bound_host, preview(bound_host))
    body["source_refs"][0][field] = value
    assert run(bound_host, body).status_code == 409
    assert not bound_host["worker"].prompts


@pytest.mark.parametrize(
    "failure", ["replay", "expired", "revoked", "changed_file", "missing_file", "changed_matter"]
)
def test_stale_revoked_or_used_approval_fails_closed(bound_host, monkeypatch, failure):
    body = approved_body(bound_host, preview(bound_host))
    if failure == "replay":
        assert run(bound_host, body).status_code == 200
        bound_host["worker"].prompts.clear()
    elif failure == "expired":
        api._local_agent_approvals.entries[body["approval_token"]]["expires"] = 0
    elif failure == "revoked":
        api._record_open_tokens.clear()
    elif failure == "changed_file":
        bound_host["path"].write_text("Fictional replacement", encoding="utf-8")
    elif failure == "missing_file":
        # Only this test's fictional temporary record is removed.
        bound_host["path"].unlink()
    elif failure == "changed_matter":
        monkeypatch.setattr(
            api, "active_case_root", lambda: bound_host["root"].parent / "other-matter"
        )
    assert run(bound_host, body).status_code == 409
    assert not bound_host["worker"].prompts


@pytest.mark.parametrize("failed_action", ["preview", "dispatch", "result"])
def test_audit_failure_blocks_dispatch_or_withholds_result(bound_host, monkeypatch, failed_action):
    original = LocalAgentAuditStore.record

    def fail(self, action, **kwargs):
        if action == failed_action:
            raise LocalAgentContextError("local_agent_audit_unavailable", 503)
        return original(self, action, **kwargs)

    monkeypatch.setattr(LocalAgentAuditStore, "record", fail)
    if failed_action == "preview":
        response = bound_host["client"].post(
            "/api/local-agent/preview", json=bound_host["body"], headers=bound_host["headers"]
        )
    else:
        response = run(bound_host, approved_body(bound_host, preview(bound_host)))
    assert response.status_code == 503
    assert "Fictional source observation" not in response.text
    assert len(bound_host["worker"].prompts) == (1 if failed_action == "result" else 0)


def test_audit_chain_tamper_is_not_silently_repaired(bound_host):
    body = approved_body(bound_host, preview(bound_host))
    store = LocalAgentAuditStore(bound_host["root"], encryption_key="f" * 32)
    state = store.encryptor.decrypt_json(json.loads(store.path.read_text()))
    state["events"][0]["action"] = "tampered"
    store.path.write_text(json.dumps(store.encryptor.encrypt_json(state)), encoding="utf-8")
    response = run(bound_host, body)
    assert response.status_code == 409
    assert response.json()["detail"] == "local_agent_audit_integrity_failed"
    assert not bound_host["worker"].prompts


@pytest.fixture
def authority_host(bound_host, tmp_path, monkeypatch):
    root = _fixture_data_root(tmp_path)
    published = AuthorityProductPublisher(data_root=root).publish(product_version="8.0.0")
    assert published.status == "pass"
    # Keep fictional data repo-local while retaining the external-to-bundle
    # rule: model the bundle and its authority state as distinct QA siblings.
    bundle = tmp_path / "fictional-bundle"
    bundle.mkdir()
    monkeypatch.chdir(bundle)
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(root))
    refs = api._local_agent_context_service().references_from_cards(
        [
            {
                "source_id": "statute-19a-1653",
                "snippet": "Best interest factors.",
                "metadata": {"source_lane": "legal_authority"},
            }
        ]
    )
    assert len(refs) == 1
    bound_host["body"] = {
        **bound_host["body"],
        "task": "authority_review",
        "source_refs": [ref.model_dump() for ref in refs],
    }
    bound_host["authority_root"] = root
    bound_host["publication"] = published
    return bound_host


def test_authority_http_path_uses_immutable_build_not_mutable_inventory(authority_host):
    host = authority_host
    staged = (
        host["authority_root"] / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    )
    staged.write_text(
        '{"record_id":"statute-19a-1653","text":"FORGED_AUTHORITY_CANARY"}\n', encoding="utf-8"
    )
    result = preview(host)
    assert result["source_cards"][0]["snippet"] == "Best interest factors."
    response = run(host, approved_body(host, result))
    assert response.status_code == 200, response.text
    assert "FORGED_AUTHORITY_CANARY" not in host["worker"].prompts[0]
    assert (
        response.json()["citations"][0]["source_reference"]["build_id"]
        == host["publication"].build_id
    )


@pytest.mark.parametrize(
    "failure", ["build", "manifest", "span", "corrupt_build", "changed_generation"]
)
def test_authority_generation_hash_and_exact_span_fail_closed(authority_host, failure):
    host = authority_host
    body = approved_body(host, preview(host))
    if failure == "build":
        body["source_refs"][0]["build_id"] = "0" * 24
    elif failure == "manifest":
        body["source_refs"][0]["build_manifest_sha256"] = "0" * 64
    elif failure == "span":
        body["source_refs"][0]["end_offset"] = 999
    elif failure == "corrupt_build":
        manifest = Path(host["publication"].build_manifest_path)
        manifest.write_text("{}", encoding="utf-8")
    elif failure == "changed_generation":
        staged = (
            host["authority_root"]
            / "parsed_authority_store"
            / "statutes"
            / "statute_sections.jsonl"
        )
        row = json.loads(staged.read_text())
        row["text"] += " Fictional revision."
        staged.write_text(json.dumps(row) + "\n", encoding="utf-8")
        newer = AuthorityProductPublisher(data_root=host["authority_root"]).publish(
            product_version="8.0.0"
        )
        assert newer.status == "pass" and newer.build_id != host["publication"].build_id
    assert run(host, body).status_code == 409
    assert not host["worker"].prompts


def test_preview_capacity_is_bounded_without_invalidating_existing_approval():
    store = LocalAgentApprovalStore(max_entries=1)
    token = store.issue({"scope": "fictional"}, {"manifest_sha256": "a" * 64})
    with pytest.raises(LocalAgentContextError, match="capacity"):
        store.issue({}, {})
    assert store.consume(token, {"scope": "fictional"}, "a" * 64)["manifest_sha256"] == "a" * 64


@pytest.mark.parametrize("failure", ["revoked", "changed_file", "changed_matter"])
def test_access_revoked_during_generation_withholds_result(bound_host, monkeypatch, failure):
    host = bound_host
    body = approved_body(host, preview(host))
    original = host["worker"].generate_response

    def generate(prompt):
        result = original(prompt)
        if failure == "revoked":
            api._record_open_tokens.clear()
        elif failure == "changed_file":
            host["path"].write_text("Fictional replacement", encoding="utf-8")
        else:
            monkeypatch.setattr(api, "active_case_root", lambda: None)
        return result

    monkeypatch.setattr(host["worker"], "generate_response", generate)
    response = run(host, body)
    assert response.status_code == 409
    assert "Fictional source observation" not in response.text
    assert len(host["worker"].prompts) == 1


def test_duplicate_sources_keep_manifest_and_exact_text_cards_aligned(bound_host):
    host = bound_host
    first = deepcopy(host["body"]["source_refs"][0])
    tail = {**first, "start_offset": first["end_offset"] - len("Review required.")}
    host["body"]["source_refs"] = [first, first, tail]
    result = preview(host)
    assert result["context_manifest"]["entry_count"] == len(result["source_cards"]) == 2
    assert result["source_cards"][1]["snippet"] == "Review required."
    response = run(host, approved_body(host, result))
    assert response.status_code == 200
    assert len(response.json()["citations"]) == 2


@pytest.mark.parametrize(
    ("text", "excerpt", "accepted"),
    [
        ("Fictional\n  record\ttext.", "Fictional record text.", True),
        ("Fictional\nrecord text.", "Fictional record fiction.", False),
        ("Fictional\nrecord. Fictional\trecord.", "Fictional record.", False),
        ("Fictional\nrecord text.", "Fictional record text", True),
    ],
)
def test_display_whitespace_maps_only_to_an_exact_unambiguous_original_span(
    text, excerpt, accepted
):
    row = {"source_id": "REC-1", "source_sha256": "a" * 64, "text": text}
    service = LocalAgentContextService(authority=None, record_loader=lambda _token: row)
    refs = service.references_from_cards(
        [
            {
                "source_id": "REC-1",
                "snippet": excerpt,
                "metadata": {"source_lane": "private_record", "record_open_token": "fictional"},
            }
        ]
    )
    assert bool(refs) is accepted
    if accepted:
        sources, cards = service.resolve(refs)
        assert sources[0].text == text[refs[0].start_offset : refs[0].end_offset]
        assert " ".join(sources[0].text.split()) == excerpt
        assert cards[0]["snippet"] == sources[0].text


def test_authority_bytes_swapped_after_path_verification_cannot_enter_context(
    authority_host, monkeypatch
):
    from app.services.authority_product_service import AuthorityProductService

    original = AuthorityProductService._artifact_path

    def replaced(self, active, **kwargs):
        path = original(self, active, **kwargs)
        if "parsed_collection:" in kwargs["role_contains"]:
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["text"] = "FORGED_CONCURRENT_CANARY"
            path.write_text(json.dumps(raw) + "\n", encoding="utf-8")
        return path

    monkeypatch.setattr(AuthorityProductService, "_artifact_path", replaced)
    response = authority_host["client"].post(
        "/api/local-agent/preview", json=authority_host["body"], headers=authority_host["headers"]
    )
    assert response.status_code == 409
    assert "FORGED_CONCURRENT_CANARY" not in response.text
    assert not authority_host["worker"].prompts


def test_authority_pointer_switch_keeps_one_build_then_invalidates_old_approval(
    authority_host, monkeypatch
):
    from app.services.authority_product_service import AuthorityProductService

    host = authority_host
    original = AuthorityProductService._iter_active_parsed_rows
    switched = []

    def switch(self, active):
        if not switched:
            staged = (
                host["authority_root"] / "parsed_authority_store/statutes/statute_sections.jsonl"
            )
            row = json.loads(staged.read_text(encoding="utf-8"))
            row["text"] += " Fictional later generation."
            staged.write_text(json.dumps(row) + "\n", encoding="utf-8")
            newer = AuthorityProductPublisher(data_root=host["authority_root"]).publish(
                product_version="8.0.0"
            )
            assert newer.status == "pass"
            switched.append(newer.build_id)
        yield from original(self, active)

    monkeypatch.setattr(AuthorityProductService, "_iter_active_parsed_rows", switch)
    result = preview(host)
    assert result["source_cards"][0]["snippet"] == "Best interest factors."
    assert result["source_refs"][0]["build_id"] == host["publication"].build_id
    assert switched[0] != host["publication"].build_id
    assert run(host, approved_body(host, result)).status_code == 409
    assert not host["worker"].prompts


def test_idempotency_replay_cannot_bypass_live_source_authorization(bound_host):
    body = approved_body(bound_host, preview(bound_host))
    headers = {**bound_host["headers"], "X-MFLL-Idempotency-Key": "fictional-approval-001"}
    first = run(bound_host, body, headers)
    assert first.status_code == 200
    assert first.headers["X-MFLL-Idempotency-Status"] == "single_use_approval"
    api._record_open_tokens.clear()
    replay = run(bound_host, body, headers)
    assert replay.status_code == 409
    assert "Fictional source observation" not in replay.text
    assert len(bound_host["worker"].prompts) == 1


def test_production_ui_posts_references_and_single_use_approval_not_source_prose():
    root = Path(__file__).resolve().parents[1]
    scripts = [
        (root / path).read_text(encoding="utf-8")
        for path in (
            "src/maine_family_law_llm/ui/workbench.js",
            "maine_family_law_llm/ui/workbench.js",
        )
    ]
    assert scripts[0] == scripts[1]
    for script in scripts:
        local_flow = script[
            script.index("async function refreshLocalAgentPreview()") : script.index(
                "function renderInlineSourceCard("
            )
        ]
        assert all(field + ":" in local_flow for field in ("source_refs", "approval_token"))
        assert (
            "source_cards: cards" not in local_flow
            and "source_cards: localAgentSourceCards" not in local_flow
        )
        assert "Exact source text supplied to the model" in local_flow
        assert "citations: result.citations || []" in local_flow

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import security
from app.api.main import app


def test_pass137_signed_capability_binds_role_tenant_matter_action_resource_and_single_use() -> None:
    capability = security.mint_session_capability(
        user_role="admin",
        tenant_id="fictional-tenant",
        matter_id="fictional-matter",
        action="security_privacy_backup",
        resource_type="matter",
        resource_id="fictional-matter",
        single_use=True,
    )
    assert capability.token
    assert capability.capability_id
    assert capability.as_dict()["single_use"] is True

    validated = security.validate_session_capability(
        capability.token,
        expected_user_role="admin",
        expected_tenant_id="fictional-tenant",
        expected_matter_id="fictional-matter",
        expected_action="security_privacy_backup",
        expected_resource_type="matter",
        expected_resource_id="fictional-matter",
        csrf_token=capability.csrf_token,
    )
    assert validated["resource_id"] == "fictional-matter"
    with pytest.raises(HTTPException) as replayed:
        security.validate_session_capability(
            capability.token,
            expected_user_role="admin",
            expected_tenant_id="fictional-tenant",
            expected_matter_id="fictional-matter",
            expected_action="security_privacy_backup",
            expected_resource_type="matter",
            expected_resource_id="fictional-matter",
            csrf_token=capability.csrf_token,
        )
    assert replayed.value.detail["error"] == "session_capability_replayed"


def test_pass137_rejects_wrong_scope_and_preserves_expiry_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    capability = security.mint_session_capability(
        user_role="reviewer",
        tenant_id="fictional-tenant",
        matter_id="fictional-matter",
        action="security_privacy_restore",
        single_use=False,
    )
    with pytest.raises(HTTPException) as wrong_resource:
        security.validate_session_capability(
            capability.token,
            expected_user_role="reviewer",
            expected_tenant_id="fictional-tenant",
            expected_matter_id="fictional-matter",
            expected_action="security_privacy_restore",
            expected_resource_type="record",
            expected_resource_id="REC-1",
            csrf_token=capability.csrf_token,
        )
    assert wrong_resource.value.detail["error"] == "session_resource_type_mismatch"

    expired = security.mint_session_capability(
        user_role="reviewer",
        tenant_id="fictional-tenant",
        matter_id="fictional-matter",
        action="security_privacy_restore",
        single_use=False,
    )
    # Re-sign an expired payload so the assertion tests expiration rather than tampering.
    import base64
    import hashlib
    import hmac
    import json

    payload = json.loads(base64.urlsafe_b64decode(expired.token.encode("ascii")).decode("utf-8"))
    payload["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    signature = hmac.new(security._session_secret(), security._canonical_token_payload({key: value for key, value in payload.items() if key != "signature"}), hashlib.sha256).hexdigest()
    expired_token = base64.urlsafe_b64encode(security._canonical_token_payload({**{key: value for key, value in payload.items() if key != "signature"}, "signature": signature})).decode("ascii")
    with pytest.raises(HTTPException) as expired_result:
        security.validate_session_capability(
            expired_token,
            expected_user_role="reviewer",
            expected_tenant_id="fictional-tenant",
            expected_matter_id="fictional-matter",
            expected_action="security_privacy_restore",
            csrf_token=expired.csrf_token,
        )
    assert expired_result.value.detail["error"] == "session_capability_expired"


def test_pass137_session_mint_is_active_matter_bound_and_action_allowlisted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    import app.api.routes.security_privacy as routes

    class _MainApi:
        @staticmethod
        def active_case_root() -> Path:
            return matter

    monkeypatch.setattr(routes, "_main_api", lambda: _MainApi())
    client = TestClient(app)
    headers = {"X-User-Role": "admin", "X-Tenant-Id": "fictional-tenant"}
    valid = client.post(
        "/api/security/privacy/session",
        headers=headers,
        json={"matter_id": "fictional-matter", "action": "security_privacy_backup"},
    )
    assert valid.status_code == 200
    session = valid.json()["session"]
    assert session["resource_type"] == "matter"
    assert session["resource_id"] == "fictional-matter"
    assert session["single_use"] is True
    mismatch = client.post(
        "/api/security/privacy/session",
        headers=headers,
        json={"matter_id": "other-matter", "action": "security_privacy_backup"},
    )
    assert mismatch.status_code == 403
    unsupported = client.post(
        "/api/security/privacy/session",
        headers=headers,
        json={"action": "arbitrary_export"},
    )
    assert unsupported.status_code == 422

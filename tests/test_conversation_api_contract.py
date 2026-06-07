from fastapi.testclient import TestClient

from app.api.main import app
from legal.conversation.response_contract import REQUIRED_RESPONSE_FIELDS


def _headers() -> dict[str, str]:
    return {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-test"}


def test_query_endpoint_returns_standard_conversation_envelope() -> None:
    client = TestClient(app)
    response = client.post("/api/query", json={"query": "How does Maine child support work?"}, headers=_headers())
    body = response.json()

    assert response.status_code == 200
    assert set(REQUIRED_RESPONSE_FIELDS).issubset(body)
    assert body["mode"] == "attorney_research"
    assert body["status_labels"]["review_required"] == "Review required"
    assert body["blocked_state_explanations"]["blocked_from_filing_ready"]


def test_filing_ready_endpoint_stays_blocked_without_full_gate_inputs() -> None:
    client = TestClient(app)
    response = client.post("/api/filing-ready/check", json={"review_required": True}, headers=_headers())
    body = response.json()

    assert response.status_code == 200
    assert body["filing_ready_status"] == "blocked_from_filing_ready"
    assert body["blocked_export_explanation"]


def test_quote_and_citation_endpoints_expose_stable_status_labels() -> None:
    client = TestClient(app)
    citation = client.post("/api/citations/verify", json={"text": "See 19-A M.R.S. § 1653."}, headers=_headers()).json()
    quote = client.post("/api/quotes/verify", json={"quoted_text": "sample"}, headers=_headers()).json()

    assert citation["status_labels"]["citation_unverified"] == "Citation unverified"
    assert quote["status_labels"]["quote_span_not_found"] == "Quote span not found"

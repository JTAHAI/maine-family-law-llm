from __future__ import annotations

from pathlib import Path

from legal.agent_runtime import LocalModelResponse, LoopbackEndpointPolicy
from maine_family_law_llm import api
from maine_family_law_llm.local_workbench_ui import render_local_workbench_html


class FakeClient:
    provider_id = "fake_loopback"
    model_name = "fake-model"
    endpoint = LoopbackEndpointPolicy().validate("http://127.0.0.1:11434")

    def generate_response(self, prompt: str) -> LocalModelResponse:
        return LocalModelResponse(
            text="The approved source discusses protection from abuse [1].\n\nReview required.",
            provider_id=self.provider_id,
            model_id=self.model_name,
            endpoint_class=self.endpoint.endpoint_class,
            usage={"prompt_tokens": 20, "completion_tokens": 12},
            finish_reason="stop",
        )


def _cards():
    return [
        {
            "source_id": "pfa-source",
            "title": "Maine PFA source",
            "snippet": "Official Maine protection-from-abuse information.",
            "metadata": {
                "source_lane": "legal_authority",
                "source_class": "safety_resource",
                "authority_status": "verified_official_maine",
                "freshness_status": "verify_current",
            },
        }
    ]


def test_normal_chat_response_carries_visible_context_and_host_receipt():
    result = api.ask(api.AskRequest(question="What if I need protection from abuse?", search_mode="maine_law"))
    assert result["context_manifest"]["entry_count"] >= 1
    assert result["context_manifest"]["transmission_scope"] == "loopback_local_model_only"
    assert result["provenance_receipt"]["provider_id"] == "deterministic_host"
    assert result["provenance_receipt"]["endpoint_class"] == "no_network"
    assert result["local_agent_policy"]["enabled_by_default"] is False
    assert result["local_agent_policy"]["remote_providers_enabled"] is False


def test_local_agent_preview_is_non_networking_and_requires_loopback():
    preview = api.local_agent_preview(
        api.LocalAgentPreviewRequest(
            question="What does this establish?",
            source_cards=_cards(),
            endpoint="http://127.0.0.1:11434",
            provider="ollama",
            model="qwen2.5:7b",
            run_id="preview-run",
        )
    )
    assert preview["status"] == "approval_required"
    assert preview["context_manifest"]["entry_count"] == 1
    assert preview["model"]["loopback_only"] is True
    assert preview["context_manifest"]["manifest_sha256"]


def test_local_agent_run_uses_exact_preview_hash(monkeypatch):
    monkeypatch.setattr(api, "build_local_client", lambda **kwargs: FakeClient())
    preview = api.local_agent_preview(
        api.LocalAgentPreviewRequest(
            question="What does this establish?",
            source_cards=_cards(),
            endpoint="http://127.0.0.1:11434",
            provider="ollama",
            model="fake-model",
            run_id="run-1",
        )
    )
    result = api.local_agent_run(
        api.LocalAgentExecuteRequest(
            question="What does this establish?",
            source_cards=_cards(),
            endpoint="http://127.0.0.1:11434",
            provider="ollama",
            model="fake-model",
            run_id="run-1",
            approved_manifest_sha256=preview["context_manifest"]["manifest_sha256"],
        )
    )
    assert result["status"] == "completed_review_required"
    assert result["local_agent_result"] is True
    assert result["provenance_receipt"]["citation_refs"] == [1]
    assert result["provenance_receipt"]["context_manifest_sha256"] == preview["context_manifest"]["manifest_sha256"]


def test_workbench_surfaces_local_agent_manifest_review_and_actions():
    html = render_local_workbench_html()
    js = (Path(__file__).resolve().parents[1] / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[1] / "src/maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="local-agent-modal"' in html
    assert "Review exactly what the model will receive" in html
    assert "Approve exact context &amp; run local model" in html
    assert "Ask local model" in js
    assert "/api/local-agent/preview" in js
    assert "/api/local-agent/run" in js
    assert "renderContextManifest" in js
    assert ".local-agent-modal" in css
    assert ".chat-context-manifest" in css

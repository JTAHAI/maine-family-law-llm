"""Opt-in real local-model acceptance; never runs in the ordinary test suite."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from test_fast_interchange_host_source_binding import bound_host, preview  # noqa: F401

from app.services.local_agent_context_service import text_digest
from legal.agent_runtime.providers import build_local_client
from maine_family_law_llm import api

_RUN_REAL = os.environ.get("MFL_RUN_REAL_LOCAL_QWEN", "").strip() == "1"


@pytest.mark.skipif(
    not _RUN_REAL, reason="requires an already-installed local Qwen and explicit opt-in"
)
@pytest.mark.parametrize("model", ["qwen3:4b", "qwen3:8b"])
@pytest.mark.parametrize(
    "scenario", ["missing_attachment", "conflicting_records", "attributed_draft"]
)
def test_curated_qwen_runs_through_canonical_api_with_fictional_matter(
    bound_host, monkeypatch, model, scenario  # noqa: F811 - imported pytest fixture
):
    """Exercise matter scope, encrypted audit, exact approval, and real loopback inference."""

    host = bound_host
    monkeypatch.setattr(api, "build_local_client", build_local_client)
    records = {
        "missing_attachment": [
            "Fictional family record: an attachment is missing. Review required."
        ],
        "conflicting_records": [
            "Fictional message A proposes an exchange at 3:00 p.m. No acceptance is recorded.",
            "Fictional message B proposes an exchange at 4:00 p.m. No acceptance is recorded.",
        ],
        "attributed_draft": [
            "Fictional parent A alleges that a requested receipt was not supplied. "
            "This record contains no court finding."
        ],
    }[scenario]
    questions = {
        "missing_attachment": (
            "What is missing from this fictional record? Cite [1] and do not add facts."
        ),
        "conflicting_records": (
            "Compare the two proposed exchange times, quoting each record with [1] and [2]. "
            "Was a time agreed? Preserve uncertainty."
        ),
        "attributed_draft": (
            "Write a short working review note about the receipt allegation. "
            "Attribute the allegation and cite [1]. Separately identify whether a court finding "
            "or legal authority supports it. Do not invent either."
        ),
    }
    rows, refs = [], []
    context = api._record_capability_identity.set(host["owner"])
    try:
        for index, text in enumerate(records, start=1):
            record_id = f"REC-{index}"
            path = host["path"].parent / f"{record_id}.txt"
            path.write_text(text, encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(
                {
                    **host["row"],
                    "evidence_id": record_id,
                    "source_hash": digest,
                    "private_copy_relpath": path.relative_to(host["root"]).as_posix(),
                    "source_locator": path.name,
                }
            )
            refs.append(
                {
                    "lane": "private_record",
                    "source_id": record_id,
                    "source_sha256": digest,
                    "text_sha256": text_digest(text),
                    "start_offset": 0,
                    "end_offset": len(text),
                    "record_token": api._record_open_token(host["root"], record_id, path.name),
                }
            )
    finally:
        api._record_capability_identity.reset(context)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: rows)
    body = {
        **host["body"],
        "question": questions[scenario],
        "source_refs": refs,
        "task": "drafting" if scenario == "attributed_draft" else "evidence_review",
        "provider": "curated_ollama_reasoning",
        # The endpoint is intentionally ignored by the curated route; this
        # verifies the server retains its fixed literal-loopback origin.
        "endpoint": "http://127.0.0.1:19999",
        "model": model,
    }
    prepared = preview(host, body)
    assert prepared["model"]["endpoint_port"] == 11434
    assert prepared["hardware_readiness"]["status"] == "ready_for_local_runtime_request"
    started = time.monotonic()
    response = host["client"].post(
        "/api/local-agent/run",
        headers=host["headers"],
        json={
            **body,
            "run_id": prepared["context_manifest"]["run_id"],
            "source_refs": prepared["source_refs"],
            "approval_token": prepared["approval_token"],
            "approved_manifest_sha256": prepared["context_manifest"]["manifest_sha256"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    report_dir = os.environ.get("MFL_QWEN_EVIDENCE_DIR")
    if report_dir:
        target = Path(report_dir).resolve()
        assert target.is_relative_to(Path(__file__).resolve().parents[1] / "dist")
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{model.replace(':', '-')}-{scenario}.json").write_text(
            json.dumps(
                {
                    "fixture": "fictional_only",
                    "level": "canonical_api_real_ollama",
                    "scenario": scenario,
                    "model": model,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "legal_quality_certification": False,
                    "response": payload,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    assert payload["status"] == "completed_review_required"
    assert payload["review_required"] is True
    assert payload["output_grounding"]["quoted_text_checked"] is True
    assert payload["output_grounding"]["factual_claims_verified"] is False
    assert payload["provenance_receipt"]["citation_refs"] == list(range(1, len(records) + 1))
    answer = payload["answer"].casefold()
    assert "<think>" not in answer and "</think>" not in answer
    assert len(answer) < 2500, "A short review should not become an internal monologue"
    if scenario == "missing_attachment":
        assert "attachment" in answer and "missing" in answer
    elif scenario == "conflicting_records":
        assert "3:00" in answer and "4:00" in answer
        assert any(
            word in answer
            for word in ("no acceptance", "not establish", "cannot determine", "can't determine")
        )
        assert "no time was agreed" not in answer and "neither proposal was accepted" not in answer
    else:
        assert payload["output_validation"]["schema_version"] == "drafting_output_boundary_v1"
        assert "source-bound working material" in answer
        assert "alleg" in answer and "receipt" in answer
        assert any(
            word in answer
            for word in (
                "no court finding",
                "no finding",
                "no legal authority",
                "not supplied",
                "not provided",
                "was supplied",
            )
        )
        assert "no legal authority or court finding exists" not in answer
    assert "m.r.s." not in answer and "v. " not in answer
    assert payload["model"]["provider_id"] == "curated_ollama_reasoning"

"""Run a bounded, fictional acceptance check against an already-installed Qwen.

This command never downloads a model, reads a user matter, or writes model
state.  It is intentionally separate from legal-quality/admission evidence:
passing it proves only the source-bound local runtime path for the named model.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# A direct ``python scripts/...`` invocation otherwise places ``scripts``
# ahead of this checkout and can import a stale globally installed edition.
# The acceptance command must exercise the code the release will package.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from legal.agent_runtime import ContextSource, LocalAgentRunRequest, LocalAgentRuntime, build_local_client


_ALLOWED_MODELS = ("qwen3:4b", "qwen3:8b")


def run_acceptance(model: str) -> dict[str, Any]:
    if model not in _ALLOWED_MODELS:
        raise ValueError("curated_ollama_model_not_allowed")
    source = ContextSource(
        source_id="fictional-hearing-notice-v1",
        lane="private_record",
        title="Fictional hearing notice",
        text="Fictional demonstration record: the hearing is March 15 at 9:00 a.m.",
        locator="fictional page 1",
        source_class="fictional_notice",
        freshness_status="not_applicable_fictional_fixture",
    )
    question = "What hearing date is stated? Use only the selected record, cite [1], and do not add facts."
    client = build_local_client(
        provider="curated_ollama_reasoning",
        endpoint="http://127.0.0.1:11434",
        model_name=model,
        timeout_seconds=120,
    )
    runtime = LocalAgentRuntime(client)
    run_id = f"fictional-qwen-{model.replace(':', '-')}-acceptance"
    manifest, _selected, preview = runtime.preview(question=question, sources=[source], run_id=run_id)
    started = time.monotonic()
    result = runtime.run(
        LocalAgentRunRequest(
            question=question,
            sources=(source,),
            approved_manifest_sha256=manifest.manifest_sha256,
            matter_id="fictional-local-reasoning-matter",
            run_id=run_id,
        )
    )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    payload = result.to_dict()
    citations = payload["provenance_receipt"].get("citation_refs") or []
    answer = str(payload.get("answer") or "")
    passed = (
        payload.get("status") == "completed_review_required"
        and citations == [1]
        and "march 15" in answer.casefold()
        and payload.get("review_required") is True
    )
    return {
        "schema_version": "mfl_local_qwen_reasoning_acceptance_v1",
        "fixture": "fictional_only",
        "model": model,
        "provider": payload.get("model", {}).get("provider_id"),
        "endpoint_class": payload.get("model", {}).get("endpoint_class"),
        "duration_ms": elapsed_ms,
        "preview_direct_prompt_blocked": bool(preview.get("direct_prompt_blocked")),
        "run_status": payload.get("status"),
        "warnings": list(payload.get("warnings") or []),
        "blockers": list(payload.get("blockers") or []),
        "citation_refs": citations,
        "answer_mentions_fictional_date": "march 15" in answer.casefold(),
        "review_required": payload.get("review_required"),
        "passed": passed,
        "legal_quality_or_admission_proven": False,
        "network_used": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=_ALLOWED_MODELS, required=True)
    args = parser.parse_args()
    result = run_acceptance(args.model)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Source context and quote matching must never certify optional-model claims."""

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from test_compact_ranked_review import FakeRanker, host_run
from test_fast_interchange_host_source_binding import approved_body, preview, run
from test_fast_interchange_host_source_binding import bound_host as bound_host

from legal.fast_interchange.compact_ranked_review import CompactRankedResearchClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def ranked_result():
    return host_run(CompactRankedResearchClient(FakeRanker(), research_only=True))


def assert_no_claim_certification(payload):
    assert payload["grounded"] is False
    grounding = payload["output_grounding"]
    assert grounding["review_required"] is True
    for key in (
        "factual_claims_verified",
        "legal_claims_verified",
        "relevance_verified",
        "current_law_verified",
    ):
        assert grounding[key] is False


def test_checked_quotations_survive_serialization_without_becoming_grounded_claims(ranked_result):
    payload = json.loads(json.dumps(ranked_result.to_dict()))
    assert_no_claim_certification(payload)
    assert payload["output_grounding"]["quoted_text_checked"] is True
    assert payload["output_grounding"]["source_context_available"] is True
    assert payload["output_grounding"]["status"] == "quoted_text_only"


@pytest.mark.parametrize(
    "status",
    [
        "blocked",
        "local_model_failed_review_required",
        "output_blocked_review_required",
        "specialist_output_blocked_review_required",
    ],
)
def test_even_existing_quote_report_cannot_green_a_failed_run(ranked_result, status):
    payload = replace(ranked_result, status=status).to_dict()
    assert_no_claim_certification(payload)
    assert payload["output_grounding"]["status"] == "withheld"
    assert payload["output_grounding"]["quoted_text_checked"] is False
    assert payload["output_grounding"]["source_context_available"] is True


@pytest.mark.parametrize(
    "validation",
    [
        {},
        {"status": "pass", "factual_claims_verified": True, "legal_claims_verified": True},
        {
            "schema_version": "invented",
            "status": "quoted_spans_bound_review_required",
            "source_spans": [{"source_id": "fictional"}],
        },
    ],
)
def test_unknown_or_missing_verifier_report_is_unverified(ranked_result, validation):
    payload = replace(ranked_result, output_validation=validation).to_dict()
    assert_no_claim_certification(payload)
    assert payload["output_grounding"]["quoted_text_checked"] is False
    assert payload["output_grounding"]["status"] == "unverified_model_output"


def test_canonical_source_context_does_not_make_generic_response_grounded(bound_host):
    prepared = preview(bound_host)
    response = run(bound_host, approved_body(bound_host, prepared))
    assert response.status_code == 200
    payload = response.json()
    assert_no_claim_certification(payload)
    assert payload["source_card_count"] == 1
    assert payload["output_grounding"]["source_context_available"] is True
    assert payload["output_grounding"]["quoted_text_checked"] is False
    assert payload["output_grounding"]["status"] == "unverified_model_output"


def test_production_js_rejects_legacy_green_model_badges():
    node = shutil.which("node")
    assert node, "Node required for production JS contract"
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    functions = script[
        script.index("    function localModelGroundingLabel(") : script.index(
            "    function renderHandoff("
        )
    ]
    functions += script[
        script.index("    function renderContextManifest(") : script.index(
            "    function renderLocalAgentReceipt("
        )
    ]
    harness = """
const assert = require('node:assert/strict');
const answerBadges={innerHTML:''},syncContextBar=()=>{},escapeHtml=x=>String(x);
"""
    checks = """
const legacy={local_agent_result:true,grounded:true,review_required:true,
  status:'completed_review_required',
  grounding_integrity:{legal_source_count:1,current_law_verified:true}};
renderBadges(legacy);
assert.ok(answerBadges.innerHTML.includes('Model claims unverified'));
assert.ok(!answerBadges.innerHTML.includes('source grounded'));
assert.ok(!answerBadges.innerHTML.includes('currentness verified'));
assert.ok(!answerBadges.innerHTML.includes('badge good'));
const checked={...legacy,output_grounding:{schema_version:'local_model_grounding_v1',
  status:'quoted_text_only',quoted_text_checked:true}};
renderBadges(checked);
assert.ok(answerBadges.innerHTML.includes('Quoted text checked; facts and law unverified'));
assert.ok(!answerBadges.innerHTML.includes('badge good'));
renderBadges({...checked,status:'local_model_failed_review_required'});
assert.ok(answerBadges.innerHTML.includes('Model output withheld'));
renderBadges({grounded:true,review_required:true});
assert.ok(answerBadges.innerHTML.includes('source grounded'));
const manifest={context_manifest:{entry_count:1}};
assert.ok(renderContextManifest(manifest).includes('Nothing was sent'));
const after=renderContextManifest({...manifest,local_agent_result:true});
assert.ok(after.includes('Approved local-model context'));
assert.ok(!after.includes('Nothing was sent'));
"""
    result = subprocess.run(
        [node, "-"],
        input=harness + functions + checks,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr

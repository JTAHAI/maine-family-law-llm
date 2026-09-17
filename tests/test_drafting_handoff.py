"""Fictional draft handoff: source boundary, matter pinning and shipped JS."""

import shutil
import subprocess
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_drafting_output_boundary import SOURCE, _run

from legal.agent_runtime.contracts import canonical_json
from legal.documents.workspace import list_documents, verify_audit_chain
from legal.fast_interchange.drafting_output import render_source_bound_draft, verify_drafting_output
from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]


def report():
    return verify_drafting_output(f'"{SOURCE.text}" [1]', (SOURCE,))


@pytest.mark.parametrize(
    "field,value",
    [
        ("filing_ready", True),
        ("review_required", False),
        ("status", "withheld"),
        ("schema_version", "invented"),
        ("factual_claims_verified", True),
    ],
)
def test_renderer_rejects_even_rehashed_policy_escalation(field, value):
    changed = report()
    changed[field] = value
    changed["report_sha256"] = sha256(
        canonical_json({k: v for k, v in changed.items() if k != "report_sha256"})
    ).hexdigest()
    with pytest.raises(ValueError, match="drafting_report_invalid"):
        render_source_bound_draft(changed, (SOURCE,))


def test_renderer_rejects_stale_report_hash():
    changed = report()
    changed["source_spans"][0]["start_offset"] = 4
    with pytest.raises(ValueError, match="drafting_report_invalid"):
        render_source_bound_draft(changed, (SOURCE,))


@pytest.mark.parametrize("reference", [0, -1, True, 1.0, 2])
def test_renderer_rejects_invalid_reference_before_indexing(reference):
    changed = report()
    changed["source_spans"][0]["reference"] = reference
    changed["report_sha256"] = sha256(
        canonical_json({k: v for k, v in changed.items() if k != "report_sha256"})
    ).hexdigest()
    with pytest.raises(ValueError, match="drafting_source_changed"):
        render_source_bound_draft(changed, (SOURCE,))


def test_runtime_discards_mutated_report_without_leaking_detail(monkeypatch):
    changed = report()
    changed["source_spans"][0]["start_offset"] = 4
    monkeypatch.setattr(
        "legal.fast_interchange.drafting_output.verify_drafting_output", lambda *_: changed
    )
    result = _run(f'"{SOURCE.text}" [1]')
    assert result.status == "specialist_output_blocked_review_required"
    assert "drafting_verifier_failed" in result.blockers
    assert SOURCE.text not in result.answer


def test_canonical_draft_save_rejects_switched_matter_preserves_original(monkeypatch, tmp_path):
    first, second = tmp_path / "fictional-first", tmp_path / "fictional-second"
    first.mkdir()
    second.mkdir()
    current = [first]
    monkeypatch.setattr(api, "active_case_root", lambda: current[0])
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(api.app)
    body = {
        "title": "Fictional working extract",
        "content": _run(f'"{SOURCE.text}" [1]').answer,
        "note": "Model-selected working material. Not filing-ready.",
        "source_refs": [{"source_id": SOURCE.source_id, "source_class": "private_record"}],
        "expected_matter_id": api._case_id(first),
    }
    created = client.post("/api/document-workspace/documents", json=body)
    assert created.status_code == 200, created.text
    document = created.json()["document"]
    current[0] = second
    blocked = client.post("/api/document-workspace/documents", json=body)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "workspace_active_matter_changed"
    assert not (second / "19_DOCUMENT_WORKSPACE").exists()
    assert str(first) not in blocked.text and str(second) not in blocked.text
    current[0] = first
    saved = client.get("/api/document-workspace/documents/" + document["document_id"]).json()[
        "document"
    ]
    assert saved["content"] == body["content"]
    assert saved["review_required"] is True and saved["filing_ready"] is False
    assert saved["revisions"][0]["note"] == body["note"]
    assert saved["source_refs"] == body["source_refs"]
    assert len(list_documents(first)) == 1
    assert verify_audit_chain(first)["valid"] is True


JS_SETUP = r"""
const assert=require('node:assert/strict');
let corpusLibraryPayload={active_case_id:'fictional-a'}, opened=null, status='', requests=[];
const documentWorkspaceState={seedMatterId:'fictional-a',
 seedSourceRefs:[],seedNote:'Review required'};
const documentWorkspaceTitle={value:'Fictional'}, documentWorkspaceEditor={value:'Preserved'};
const documentWorkspaceType={value:'memo'};
const sourceItemsFromPayload=()=>[], showToast=text=>status=text;
const setDocumentWorkspaceStatus=text=>status=text;
const openDocumentWorkspace=async options=>{opened=options;};
const fetchJson=async(url,options)=>{
 requests.push(JSON.parse(options.body));return {document:{document_id:'saved'}};};
const loadDocumentWorkspaceDocuments=async()=>{};
const payload={local_agent_result:true,matter_id:'fictional-a',
 status:'specialist_output_partial_review_required',
 output_validation:{display_mode:'source_bound_draft_extracts_partial'},
 provenance_receipt:{receipt_sha256:'a'.repeat(64)}};
"""


@pytest.mark.parametrize(
    "scenario",
    ["partial", "wrong_matter", "missing_matter", "blocked", "save_switched", "save_bound"],
)
def test_shipped_handoff_handlers(scenario):
    node = shutil.which("node")
    assert node, "Node is required; do not silently skip UI verification"
    js = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    start = js.index("    async function saveWorkspaceNewDraft()")
    end = js.index("    async function importRecordToWorkspace(", start)
    checks = {
        "partial": """
await saveAnswerAsDraft('Fictional extract',payload);assert.match(opened.note,/Partial result/);
assert.match(opened.note,/Facts, legal claims, relevance and current law are not verified/);
assert.equal(opened.matterId,'fictional-a');assert.match(status,/not verified facts/);
""",
        "wrong_matter": """
payload.matter_id='fictional-b';await saveAnswerAsDraft('Private',payload);
assert.equal(opened,null);assert.match(status,/original matter/);
""",
        "missing_matter": """
delete payload.matter_id;await saveAnswerAsDraft('Private',payload);assert.equal(opened,null);
""",
        "blocked": """
payload.status='specialist_output_blocked_review_required';
await saveAnswerAsDraft('Private',payload);
assert.equal(opened,null);assert.match(status,/withheld/);
""",
        "save_switched": """
corpusLibraryPayload.active_case_id='fictional-b';await saveWorkspaceNewDraft();
assert.equal(requests.length,0);assert.equal(documentWorkspaceEditor.value,'Preserved');
assert.match(status,/Nothing was saved/);
""",
        "save_bound": """
await saveWorkspaceNewDraft();assert.equal(requests.length,1);
assert.equal(requests[0].expected_matter_id,'fictional-a');
""",
    }
    result = subprocess.run(
        [
            node,
            "-e",
            JS_SETUP
            + js[start:end]
            + "\n(async()=>{"
            + checks[scenario]
            + "})().catch(e=>{console.error(e);process.exit(1)});",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_handoff_mirrors():
    for file in ("api.py", "ui/workbench.js"):
        assert (ROOT / "src/maine_family_law_llm" / file).read_bytes() == (
            ROOT / "maine_family_law_llm" / file
        ).read_bytes()

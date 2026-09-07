"""Executable shipped-JS regressions; browser receipts remain a separate level."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src/maine_family_law_llm/ui"
JS = (UI / "workbench.js").read_text(encoding="utf-8")


def segment(start: str, end: str) -> str:
    return JS[JS.index(start):JS.index(end, JS.index(start))]


def run_js(source: str) -> object:
    result = subprocess.run(
        ["node", "-e", source], capture_output=True, text=True, check=True, timeout=25
    )
    return json.loads(result.stdout)


def test_request_uncertainty_does_not_invent_rollback_or_leak_response_text():
    source = segment("function makeSafeLocalError(", "function recordSafeError(")
    source += segment("async function fetchJson(", "function localRequestHeaders(")
    result = run_js(source + r"""
const localCapabilitySession = () => 'fictional-session';
const newLocalIdempotencyKey = () => 'fictional-request-001';
const isIdempotentMutation = (_, options) => options.method === 'POST';
(async () => {
  const results = [];
  for (const kind of ['network', 'body', 'json', 'server', 'validation', 'success']) {
    for (const method of ['GET', 'POST']) {
      let calls = 0; const keys = [];
      global.fetch = async (_, options) => {
        calls++; keys.push(options.headers.get('X-MFLL-Idempotency-Key'));
        if (kind === 'network') throw new Error('PRIVATE-FICTIONAL-RECORD C:/private/record');
        return {status:kind === 'server' ? 500 : kind === 'validation' ? 422 : 200,
          ok:!['server','validation'].includes(kind), text:async () => {
            if (kind === 'body') throw new Error('PRIVATE-FICTIONAL-RECORD');
            return kind === 'json' ? '<html>PRIVATE-FICTIONAL-RECORD</html>'
              : JSON.stringify({review_required:true});
          }};
      };
      try { results.push({kind,method,value:await fetchJson('/api/fictional', {method}),calls}); }
      catch (error) { results.push({kind,method,unknown:error.writeOutcomeUnknown,
        info:safeErrorInfo(error),calls,keys}); }
    }
  }
  console.log(JSON.stringify(results));
})();
""")
    assert len(result) == 12
    assert "PRIVATE-FICTIONAL-RECORD" not in json.dumps(result)
    for row in result:
        if row["kind"] == "success":
            assert row["value"]["review_required"] is True
            continue
        expected = row["method"] == "POST" and row["kind"] != "validation"
        assert row["unknown"] is expected
        if expected:
            assert "not a rollback receipt" in row["info"]["preserved"]
            assert "before retrying" in row["info"]["recovery"]
        if row["kind"] == "network" and row["method"] == "POST":
            assert row["calls"] == 2
            assert row["keys"] == ["fictional-request-001"] * 2


def test_tab_candidates_exclude_css_hidden_inert_and_closed_details():
    source = segment("function renderedInteractionTarget(", "function activeManagedOverlay(")
    result = run_js(source + r"""
global.window = {getComputedStyle:n=>({display:n.display||'block',
 visibility:n.visibility||'visible'})};
function node(overrides={}) {
 return Object.assign({isConnected:true,tabIndex:0,closest:()=>null,matches:()=>false,
   getClientRects:()=>[{}],parentElement:null}, overrides);
}
const closed = {parentElement:null,matches:()=>true,querySelector:()=>({contains:n=>n.isSummary})};
const candidates = [node(),node({isConnected:false}),node({closest:()=>({})}),
 node({matches:()=>true}),node({display:'none'}),node({visibility:'hidden'}),
 node({visibility:'collapse'}),node({getClientRects:()=>[]}),node({tabIndex:-1}),
 node({parentElement:closed}),node({parentElement:closed,isSummary:true})];
const included = overlayFocusableElements({querySelectorAll:()=>candidates});
console.log(JSON.stringify(included.map(n=>candidates.indexOf(n))));
""")
    assert result == [0, 10]


def test_overlay_isolation_restores_preexisting_inert_state_and_nested_dialogs():
    source = segment("function syncOverlayIsolation(", "function overlayReturnTarget(")
    result = run_js(source + r"""
const node = () => ({inert:false,hidden:false,children:[],matches:()=>false,setAttribute(){},
  contains(other){return this.children.some(c=>c===other||c.contains(other));}});
const body=node(), shell=node(), overlayA=node(), overlayB=node(), disabledRegion=node();
const evidenceDrawer=null, drawerBackdrop=null;
const overlayBackdrop=()=>null;
disabledRegion.inert=true;
body.children=[shell,overlayA,disabledRegion]; shell.parentElement=body;
overlayA.parentElement=body; disabledRegion.parentElement=body;
const parentContent=node(); overlayA.children=[parentContent,overlayB];
parentContent.parentElement=overlayA; overlayB.parentElement=overlayA;
global.document={body}; const overlayStack=[overlayA]; const overlayBackgroundInert=new Map();
let active=overlayA;
const activeManagedOverlay=()=>active;
const setOverlayBackgroundState=(e,a)=>{e.inert=!a};
const facts=[];
syncOverlayIsolation(); facts.push([shell.inert,overlayA.inert,disabledRegion.inert]);
overlayStack.push(overlayB); active=overlayB; syncOverlayIsolation();
facts.push([shell.inert,parentContent.inert,overlayB.inert,overlayA.inert]);
overlayB.hidden=true; overlayStack.pop(); active=overlayA; syncOverlayIsolation();
facts.push([shell.inert,parentContent.inert,overlayA.inert]);
overlayA.hidden=true; overlayStack.pop(); active=null; syncOverlayIsolation();
facts.push([shell.inert,parentContent.inert,disabledRegion.inert,overlayBackgroundInert.size]);
console.log(JSON.stringify(facts));
""")
    assert result == [[True, False, True], [True, True, False, False],
                      [True, False, False], [False, False, True, 0]]


def test_view_menu_uses_one_tab_stop_and_none_when_closed():
    source = segment("function syncViewMenuTabStops(", "    syncViewMenuTabStops();")
    result = run_js(source + r"""
const items=[0,1,2].map(i=>({tabIndex:0,getAttribute:()=>i===1?'true':'false'}));
const v8ViewMenu={open:false,querySelectorAll:()=>items};
const states=[]; syncViewMenuTabStops(); states.push(items.map(i=>i.tabIndex));
v8ViewMenu.open=true; syncViewMenuTabStops(); states.push(items.map(i=>i.tabIndex));
syncViewMenuTabStops(items[2]); states.push(items.map(i=>i.tabIndex));
console.log(JSON.stringify(states));
""")
    assert result == [[-1, -1, -1], [-1, 0, -1], [-1, -1, 0]]


def test_collapsed_prompts_reflow_and_motion_rules_ship_in_both_asset_copies():
    for name in ("workbench.html", "workbench.css", "workbench.js"):
        assert (UI / name).read_bytes() == (ROOT / "maine_family_law_llm/ui" / name).read_bytes()
    html = (UI / "workbench.html").read_text(encoding="utf-8")
    assert '<details class="composer-guides">' in html
    assert '<summary class="composer-guides-heading">' in html
    css = (UI / "workbench.css").read_text(encoding="utf-8")
    assert '@media (max-width: 720px), (max-height: 650px)' in css
    assert 'max-height: none; overflow: visible' in css
    assert 'width: calc(100% - 8px); max-width: 100%; min-width: 0;' in css
    assert 'animation: none !important; transition: none !important' in css
    assert css.rindex('@media (prefers-reduced-motion: reduce)') > css.index(
        'Critical interaction contract'
    )
    assert 'if (element.hidden || activeManagedOverlay() !== element) return;' in JS
    assert 'document.addEventListener(\'focusin\'' in JS


def test_failed_official_source_lane_never_falls_back_to_generic_sources():
    source = segment("async function loadSources()", "async function updateAuthorityLibrary()")
    result = run_js(source + r"""
const sourcesButton={}, sourceCards={}, calls=[]; let authorityTrustPayload={active:true};
const authorityQueryParams=()=>'';
const fetchJson=async url=>{calls.push(url);throw new Error('fictional failure')};
const updateTrustStatus=()=>{};
const renderRecoverableError=(_,options)=>options.title;
const renderSources=()=>{throw Error('must not render generic fallback')};
const updateAuthorityLibrarySummary=()=>{};
(async()=>{await loadSources();console.log(JSON.stringify({calls,authorityTrustPayload,
 disabled:sourcesButton.disabled,message:sourceCards.innerHTML}));})();
""")
    assert result["calls"] == ["/api/authority/sources?"]
    assert result["authorityTrustPayload"]["active"] is False
    assert result["disabled"] is False
    assert result["message"] == "Official sources could not be loaded"


def test_composer_enter_does_not_send_ime_composition():
    source = segment(
        "question.addEventListener('keydown'", "matterContext.addEventListener('keydown'"
    )
    result = run_js(r"""
let handler; const question={addEventListener:(_,fn)=>{handler=fn}};
let sent=0; const ask=()=>{sent++};
""" + source + r"""
const counts=[];
for (const fields of [{isComposing:true}, {keyCode:229}, {shiftKey:true}, {}]) {
  handler({key:'Enter',preventDefault(){},...fields}); counts.push(sent);
}
console.log(JSON.stringify(counts));
""")
    assert result == [0, 0, 0, 1]


def test_response_completion_never_looks_like_approval():
    source = segment("function responseReviewLabel(", "function addMessage(")
    states = run_js(source + """
console.log(JSON.stringify([null, {}, {grounded:true,filing_ready:true},
 {blockers:['unknown_source']}, {failure_class:'official_authority_product_unavailable'},
 {local_agent_result:true,status:'failed'},
 {local_agent_result:true,status:'completed_review_required'}].map(responseReviewLabel)));
""")
    assert states == ["Review required"] * 3 + ["Review blocked"] * 3 + ["Review required"]
    render = segment("function addMessage(", "function resetSession(")
    assert 'class="message-verified"' not in render
    assert 'class="message-review-status"' in render


def test_nested_escape_dispatches_only_top_surface_with_owner_cleanup():
    source = segment("function closeActiveManagedOverlay()", "function renderCorpusLibrary(")
    result = run_js(r"""
const names=['localWorkbenchOverlay','releasePilotHardeningModal',
 'evidenceWorkProductModal','documentIntelligenceModal','authorityVerificationModal',
 'localAgentModal','documentWorkspace','recordInspector','retrievalWorkbenchModal',
 'sourcePreviewFlyout'];
""" + "\n".join(f"const {name}={{id:'{name}'}};" for name in [
        "localWorkbenchOverlay", "releasePilotHardeningModal", "evidenceWorkProductModal",
        "documentIntelligenceModal", "authorityVerificationModal", "localAgentModal",
        "documentWorkspace", "recordInspector", "retrievalWorkbenchModal", "sourcePreviewFlyout",
    ]) + "\n".join(f"const {name}=()=>calls.push('{name}');" for name in [
        "closeLocalWorkbench", "closeReleasePilotHardening", "closeEvidenceWorkProduct",
        "closeDocumentIntelligence", "closeAuthorityVerification", "closeLocalAgentDialog",
        "closeDocumentWorkspace", "closeRecordInspector", "closeRetrievalWorkbench",
        "closeSourcePreview", "closeOverlay",
    ]) + source + r"""
let active=null; const calls=[];
const activeManagedOverlay=()=>active;
const noOverlay=closeActiveManagedOverlay();
for (const next of [documentWorkspace,recordInspector,sourcePreviewFlyout,
 retrievalWorkbenchModal,localAgentModal,{id:'other-dialog'}]) {
 active=next; closeActiveManagedOverlay();
}
console.log(JSON.stringify({noOverlay,calls}));
""")
    assert result == {"noOverlay": False, "calls": [
        "closeDocumentWorkspace", "closeRecordInspector", "closeSourcePreview",
        "closeRetrievalWorkbench", "closeLocalAgentDialog", "closeOverlay",
    ]}
    assert "if (closeActiveManagedOverlay())" in JS
    for dialog in ("documentWorkspace", "recordInspector", "documentIntelligenceModal",
                   "evidenceWorkProductModal", "authorityVerificationModal",
                   "releasePilotHardeningModal", "localAgentModal", "retrievalWorkbenchModal",
                   "sourcePreviewFlyout"):
        assert f"openOverlay({dialog})" in JS
        assert f"closeOverlay({dialog})" in JS

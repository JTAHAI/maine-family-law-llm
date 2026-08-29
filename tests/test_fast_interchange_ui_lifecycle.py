"""Execute production approval-dialog functions with deterministic DOM/network doubles.

These are JavaScript lifecycle unit tests, not browser, frozen-app, or model E2E.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "scenario",
    [
        "preview_close_success",
        "preview_close_error",
        "run_close_success",
        "run_close_error",
        "approved_success",
        "changed_config",
        "cancel_confirmed",
    ],
)
def test_approval_dialog_rejects_late_results_and_binds_settings(scenario):
    node = shutil.which("node")
    if not node:
        pytest.fail("Node is required to verify the production approval-dialog lifecycle")
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    functions = script[
        script.index("    let localAgentActiveRun = null;") : script.index(
            "    function renderInlineSourceCard("
        )
    ]
    harness = r"""
const assert = require('node:assert/strict');
const element = () => ({hidden:false, disabled:false, textContent:'', innerHTML:'',
                       setAttribute(){}, focus(){}, value:''});
const localAgentModal=element(), localAgentBackdrop=element(), localAgentRun=element(),
      localAgentRefreshPreview=element(), localAgentPreviewSummary=element(),
      localAgentStatus=element(), localAgentContextList=element(),
      localAgentSecurityReport=element(), localAgentProvider=element(),
      localAgentEndpoint=element(), localAgentModel=element(), localAgentClose=element(),
      localAgentCancel=element(), localAgentTask=element();
const document={body:{classList:{remove(){},add(){}}}, activeElement:element(),getElementById(){return null}};
const window={localStorage:{getItem(){return '{}'},setItem(){}},requestAnimationFrame(fn){fn()}};
let localAgentPayload={question:'Fictional original question',local_agent_matter_id:'fictional'},
    localAgentPreview=null,localAgentOwner=null,localAgentBusy=false,localAgentRequestEpoch=0,
    lastPayload=null,lastSources=null;
let config={provider:'ollama',endpoint:'http://127.0.0.1:11434',model:'fictional-model'};
const localAgentConfigPayload=()=>config;
const localAgentSourceCards=()=>[{source_id:'fictional'}];
const escapeHtml=value=>String(value);
const toasts=[], messages=[];
const showToast=text=>toasts.push(text);
const addMessage=(role,text,payload)=>messages.push({role,text,payload});
const renderLatestAnswer=()=>{},renderSources=()=>{},renderBadges=()=>{};
let resolveRequest,rejectRequest,requestCount=0;
const pendingRequests=[];
const fetchJson=()=>{requestCount++;return new Promise((resolve,reject)=>{
    resolveRequest=resolve;rejectRequest=reject;
    pendingRequests.push({resolve,reject});
});};
"""
    checks = r"""
(async()=>{
 const scenario=process.argv[1];
 if(scenario.startsWith('preview_')){
   const pending=refreshLocalAgentPreview();
   assert.equal(requestCount,1);
   closeLocalAgentDialog();
   openLocalAgentDialog({question:'must not replace pending'},null);
   assert.equal(localAgentPayload,null);
   if(scenario.endsWith('error')) rejectRequest(new Error('late private error'));
   else resolveRequest({context_manifest:{entries:[]}});
   await pending;
   assert.equal(localAgentPreview,null);
   assert.equal(localAgentModal.hidden,true);
   assert.equal(localAgentBusy,false);
   assert.ok(!localAgentStatus.innerHTML.includes('late private error'));
 } else {
   localAgentPreview={approvedConfig:JSON.stringify(config),source_refs:[],matter_id:'fictional',
                     approval_token:'fictional',context_manifest:{}};
   if(scenario==='cancel_confirmed') localAgentPreview.cancellation_supported=true;
   if(scenario==='changed_config'){
     config={...config,model:'changed'};
     await runApprovedLocalAgent();
     assert.equal(requestCount,0);
     assert.equal(localAgentPreview,null);
     assert.ok(localAgentStatus.textContent.includes('Model settings changed'));
     return;
   }
   const pending=runApprovedLocalAgent();
   assert.equal(requestCount,1);
   if(scenario==='cancel_confirmed'){
     assert.equal(localAgentCancel.textContent,'Cancel generation');
     const cancel=cancelLocalAgentGeneration();
     assert.equal(requestCount,2);
     pendingRequests[1].resolve({status:'canceling'});
     await cancel;
     const error=new Error('Sanitized conflict explanation');
     error.safeCode='fast_interchange_generation_canceled';
     pendingRequests[0].reject(error);
     await pending;
     assert.ok(localAgentStatus.textContent.startsWith('Generation canceled.'));
     assert.equal(messages.length,0);
     assert.equal(localAgentActiveRun,null);
     assert.equal(localAgentBusy,false);
     assert.equal(localAgentCancel.textContent,'Close review');
     assert.equal(localAgentTask.disabled,false);
     return;
   }
   assert.ok(localAgentCancel.textContent.includes('does not cancel generation'));
   if(scenario.startsWith('run_close')){
     closeLocalAgentDialog();
     openLocalAgentDialog({question:'must not replace pending'},null);
     assert.equal(localAgentPayload,null);
   }
   if(scenario.endsWith('error')) rejectRequest(new Error('late private error'));
   else resolveRequest({answer:'fictional approved answer',citations:[{source_id:'verified'}]});
   await pending;
   assert.equal(localAgentBusy,false);
   assert.equal(localAgentModal.hidden,true);
   if(scenario==='approved_success'){
     assert.equal(messages.length,1);
     assert.equal(messages[0].payload.question,'Fictional original question');
     assert.equal(messages[0].payload.citations[0].source_id,'verified');
   } else {
     assert.equal(messages.length,0);
     assert.ok(!localAgentStatus.innerHTML.includes('late private error'));
   }
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    completed = subprocess.run(
        [node, "-e", harness + functions + checks, scenario],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr

"""Production JS interaction contracts, explicitly not a browser certificate."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "scenario",
    [
        "complete",
        "consent",
        "wrong_matter",
        "failed_upload",
        "cancel",
        "double_click",
        "resume",
        "wrong_file",
        "fresh_session_resume",
        "resume_cancel",
        "fresh_session_cancel",
        "recovery",
        "remove_restore",
        "decline",
        "escape",
        "keyboard",
        "confirmation_matter_changed",
        "inventory_race",
        "inventory_aba_error",
        "transfer_matter_changed",
        "readiness",
        "worker_state",
        "resume_cancel_matter_changed",
    ],
)
def test_offline_pack_ui_state_machine(scenario):
    root = Path(__file__).resolve().parents[1]
    script = (root / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    start = script.index("    (function installOfflineModelPacks() {")
    implementation = script[start : script.index("    }());", start) + len("    }());")]
    harness = r"""
const assert=require('node:assert/strict');
const crypto=require('node:crypto').webcrypto;
const hash=data=>require('node:crypto').createHash('sha256').update(data).digest('hex');
const firstBlock=Buffer.alloc(1024**2);
const prefix=hash(`${hash(Buffer.alloc(0))}:0:${firstBlock.length}:${hash(firstBlock)}`);
const elements=new Map();
for(const name of ['panel','admin','file','import','refresh','activate','cancel',
                   'discard','status','details','progress','job','version','resume',
                   'reactivate','remove','restore','recover','deactivate','abandon',
                   'confirmation','confirmation-text','confirm-yes','confirm-no'])
 elements.set('model-pack-'+name,{id:'model-pack-'+name,dataset:{},handlers:{},value:'',replaceChildren(...items){this.children=items},addEventListener(name,fn){this.handlers[name]=fn},focus(){this.focused=true;document.activeElement=this},textContent:'',disabled:false});
const document={getElementById:id=>elements.get(id),createElement:()=>({})};
const e=name=>elements.get('model-pack-'+name);
e('confirmation').showModal=()=>queueMicrotask(()=>{
 assert.equal(e('import').disabled,true);assert.equal(e('cancel').disabled,true);
 if(process.argv[1]==='keyboard'){
   for(const expected of ['confirm-yes','confirm-no']){
     e('confirmation').handlers.keydown({key:'Tab',stopPropagation(){},preventDefault(){}});
     assert.equal(document.activeElement,e(expected));
   }
   e('confirmation').handlers.keydown({key:'Escape',stopPropagation(){},preventDefault(){}});return;
 }
 if(process.argv[1]==='escape'){e('confirmation').handlers.keydown({key:'Escape',stopPropagation(){},preventDefault(){}});return;}
 if(process.argv[1]==='confirmation_matter_changed')localAgentPayload.local_agent_matter_id='other';
 e(process.argv[1]==='decline'?'confirm-no':'confirm-yes').handlers.click();
});
e('confirmation').close=()=>{};
e('admin').checked=true;
let prefixReads=[];
e('file').files=[{name:'fictional.model-pack.zip',size:1024**2+4,slice:(start,end)=>{
 const block=Buffer.alloc(end-start,process.argv[1]==='wrong_file'?1:0);
 block.arrayBuffer=async()=>{prefixReads.push(end-start);
   return block.buffer.slice(block.byteOffset,block.byteOffset+block.byteLength)};
 return block;
}}];
let localAgentBusy=false,localAgentPreview={},localAgentRun={disabled:false},
    localAgentPayload={local_agent_matter_id:'fictional-matter'};
const window={confirm:()=>true};
const makeSafeLocalError=({code})=>Object.assign(new Error('safe'),{safeCode:code});
const setInterval=()=>1,clearInterval=()=>{};
let server={job_id:'a'.repeat(32),status:'uploading',received_bytes:0,
            total_bytes:1024**2+4,review_required:true};
let stored={pack_id:'b'.repeat(64),summary:{evaluation_basis:'synthetic'},
            active:false,previous:false};
let removed=false;
let transaction=process.argv[1]==='recovery'
  ? {id:'d'.repeat(32),kind:'activate',pack_id:stored.pack_id}:null;
const requests=[];
let releaseChunk;
const pendingInventories=[];
const fetchJson=async(url,options={})=>{
 requests.push({url,options});
 if(url.startsWith('/api/model-packs?') && process.argv[1].startsWith('inventory_'))
   return await new Promise((resolve,reject)=>pendingInventories.push({resolve,reject}));
 if(url.startsWith('/api/model-packs?'))return {
   readiness:{status:'development_only',hardware_verified:false,runtime_verified:false},
   jobs:process.argv[1].startsWith('fresh_session_')?[]:[{...server}],
   recoverable_jobs:process.argv[1].startsWith('fresh_session_')?[{...server}]:[],
   active_pack_id:'',installed:removed?[]:[stored],removed:removed?[stored]:[],transaction};
 if(url.endsWith('/resume')){
   const body=JSON.parse(options.body);assert.equal(body.prefix_chain,prefix);
   assert.equal(body.expected_bytes,1024**2);assert.equal(body.user_confirmed,true);
   server.status='uploading';return {...server};}
 if(url==='/api/model-packs/recovery'){
   assert.equal(JSON.parse(options.body).transaction_id,transaction.id);transaction=null;
   return {status:'activate_completed',requires_worker_restart:true};}
 if(url.endsWith('/remove')){removed=true;return {status:'remove_completed'};}
 if(url.endsWith('/restore')){removed=false;return {status:'restore_completed'};}
 if(url==='/api/model-packs/imports')return {...server};
 if(url.includes('/chunks')){
   if(process.argv[1]==='failed_upload')
     throw makeSafeLocalError({code:'model_pack_transfer_incomplete'});
   if(['cancel','transfer_matter_changed'].includes(process.argv[1]))
     await new Promise(resolve=>releaseChunk=resolve);
   server.received_bytes+=options.body.length;return {...server};
 }
 if(url.endsWith('/inspect')){
   server.status='ready_to_activate';server.pack_id='b'.repeat(64);return {...server};}
 if(url.endsWith('/activate')){
   assert.equal(e('cancel').disabled,true);
   assert.ok(e('status').textContent.includes('cannot be canceled'));
   server.status='activated';return {...server};}
 if(url.endsWith('/cancel')){server.status='canceled';return {...server};}
 if(url.endsWith('/discard'))return {status:'discarded'};
 return {...server};
};
"""
    checks = r"""
(async()=>{
 const scenario=process.argv[1];
 if(scenario==='worker_state'){
   await e('refresh').handlers.click();
   e('job').value='';e('job').handlers.change();
   localAgentBusy=true;e('panel').handlers['model-pack-worker-state']();
   assert.equal(e('import').disabled,true);
   localAgentBusy=false;e('panel').handlers['model-pack-worker-state']();
   assert.equal(e('import').disabled,false);return;
 }
 if(scenario.startsWith('inventory_')){
   const context=value=>{
     localAgentPayload.local_agent_matter_id=value;
     return e('panel').handlers['model-pack-context']({detail:{matterId:value}});
   };
   const first=context('fictional-a');
   const second=context('fictional-b');
   const latest=scenario==='inventory_aba_error'?context('fictional-a'):second;
   const fresh={models:[{model_id:'current-only'}],readiness:{status:'development_only'},
                jobs:[],installed:[],removed:[]};
   pendingInventories.at(-1).resolve(fresh);await latest;
   if(scenario==='inventory_aba_error'){
     pendingInventories[1].resolve({models:[{model_id:'old-b'}]});await second;
     pendingInventories[0].reject(makeSafeLocalError({code:'model_pack_operation_failed'}));
   }else pendingInventories[0].resolve({models:[{model_id:'old-a'}],jobs:[server]});
   await first;
   assert.equal(window.mflActiveSpecialistModels[0].model_id,'current-only');
   assert.ok(!e('details').textContent.includes('old-'));
   assert.match(e('status').textContent,/Research pack installed/);
   assert.equal(e('activate').disabled,true);return;
 }
 if(scenario==='readiness'){
   await e('refresh').handlers.click();
   assert.match(e('status').textContent,
     /Research pack installed — not approved for production use/);
   assert.match(e('status').textContent,/Hardware and worker startup have not been verified/);
   return;
 }
 if(['recovery','remove_restore'].includes(scenario)){
   await e('refresh').handlers.click();
   if(scenario==='recovery'){
     await e('recover').handlers.click();assert.equal(transaction,null);
     assert.equal(localAgentRun.disabled,true);assert.ok(e('status').textContent.includes('Restart'));
   }else{
     e('version').value=stored.pack_id;e('version').handlers.change();
     assert.equal(e('remove').disabled,false);await e('remove').handlers.click();
     assert.equal(removed,true);
     assert.equal(e('restore').disabled,false);await e('restore').handlers.click();
     assert.equal(removed,false);
   }
   assert.equal(e('panel').dataset.busy,'false');return;
 }
 if(['resume','wrong_file','fresh_session_resume','resume_cancel','fresh_session_cancel',
     'resume_cancel_matter_changed'].includes(scenario)){
   server={...server,status:'canceled',received_bytes:1024**2,prefix_chain:prefix};
   await e('refresh').handlers.click();e('job').value=server.job_id;e('job').handlers.change();
   requests.length=0;
   const pending=e('resume').handlers.click();
   if(['resume_cancel','fresh_session_cancel','resume_cancel_matter_changed'].includes(scenario)){
     for(let i=0;i<20&&!prefixReads.length;i++)await new Promise(resolve=>setImmediate(resolve));
     await e('cancel').handlers.click();
     if(scenario==='resume_cancel_matter_changed'){
       localAgentPayload.local_agent_matter_id='fictional-other';
       await e('panel').handlers['model-pack-context']({detail:{matterId:'fictional-other'}});
     }
   }
   await pending;
   assert.ok(prefixReads.every(size=>size<=1024**2));
   assert.equal(e('panel').dataset.busy,'false');
   if(scenario==='resume_cancel_matter_changed'){
     assert.equal(e('job').value,'');assert.equal(e('resume').disabled,true);
     assert.ok(!e('details').textContent.includes(server.job_id));
     assert.match(e('status').textContent,/Matter changed/);return;
   }
   if(scenario==='wrong_file'){assert.ok(e('status').textContent.includes('prefix_changed'));assert.ok(!requests.some(row=>row.url.endsWith('/resume')));return;}
   if(['resume_cancel','fresh_session_cancel'].includes(scenario)){
     assert.ok(!requests.some(row=>row.url.endsWith('/inspect')));
     assert.ok(e('status').textContent.includes('canceled locally'));
     assert.equal(e('resume').disabled,false);return;
   }
   assert.equal(requests.filter(row=>row.url.endsWith('/resume')).length,1);
   assert.equal(requests.filter(row=>row.url.includes('/chunks')).length,1);
   assert.equal(server.status,'ready_to_activate');assert.equal(e('job').value,server.job_id);
   return;
 }
 if(scenario==='consent')e('admin').checked=false;
 if(scenario==='wrong_matter')localAgentPayload.local_agent_matter_id='';
 const pending=e('import').handlers.click();
 if(scenario==='transfer_matter_changed'){
   for(let i=0;i<20&&!releaseChunk;i++)await new Promise(resolve=>setImmediate(resolve));
   localAgentPayload.local_agent_matter_id='fictional-other';
   await e('panel').handlers['model-pack-context']({detail:{matterId:'fictional-other'}});
   releaseChunk();await pending;
   assert.ok(!requests.some(row=>row.url.endsWith('/inspect')||row.url.endsWith('/activate')));
   assert.equal(requests.filter(row=>row.url.includes('/chunks')).length,1);
   assert.ok(requests.filter(row=>row.url.includes('matter_id=')).every(row=>row.url.includes('fictional-matter')));
   assert.equal(e('activate').disabled,true);
   assert.ok(!e('details').textContent.includes(server.job_id));
   assert.match(e('status').textContent,/Matter changed/);return;
 }
 if(scenario==='double_click')await e('import').handlers.click();
 if(scenario==='cancel'){
   for(let i=0;i<8&&!releaseChunk;i++)await Promise.resolve();
   await e('cancel').handlers.click();releaseChunk();
 }
 await pending;
 assert.equal(e('panel').dataset.busy,'false');
 if(['consent','wrong_matter'].includes(scenario)){assert.equal(requests.length,0);return;}
 assert.equal(requests.filter(row=>row.url==='/api/model-packs/imports').length,1);
 assert.ok(!requests.some(row=>row.url.endsWith('/activate')));
 if(scenario==='failed_upload'){assert.ok(e('status').textContent.includes('model_pack_transfer_incomplete'));return;}
 if(scenario==='cancel'){assert.ok(e('status').textContent.includes('canceled'));assert.ok(!requests.some(row=>row.url.endsWith('/inspect')));return;}
 assert.equal(e('activate').disabled,false);
 assert.ok(e('details').textContent.includes('b'.repeat(64)));
 await e('activate').handlers.click();
 if(['decline','escape','keyboard','confirmation_matter_changed'].includes(scenario)){
   assert.equal(server.status,'ready_to_activate');assert.ok(!requests.some(row=>row.url.endsWith('/activate')));return;
 }
 assert.equal(server.status,'activated');
 assert.equal(localAgentRun.disabled,true);
 assert.ok(e('status').textContent.includes('Restart'));
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    if scenario in {"consent", "wrong_matter"}:
        checks = checks.replace("assert.equal(e('panel').dataset.busy,'false');", "")
    result = subprocess.run(
        [shutil.which("node") or "node", "-", scenario],
        input=(harness + implementation + checks).replace("process.argv[1]", "process.argv[2]"),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_model_pack_entries_ship_in_both_production_mirrors():
    root = Path(__file__).resolve().parents[1]
    for name in ("workbench.js", "workbench.html", "workbench.css"):
        primary = root / "maine_family_law_llm/ui" / name
        mirror = root / "src/maine_family_law_llm/ui" / name
        assert primary.read_bytes() == mirror.read_bytes()
    html = (root / "src/maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    assert '<details id="model-pack-panel">' in html
    assert 'id="model-pack-status" role="status" aria-live="polite"' in html
    assert 'id="model-pack-file" type="file"' in html
    assert "Signed model details and artifact identity" in html

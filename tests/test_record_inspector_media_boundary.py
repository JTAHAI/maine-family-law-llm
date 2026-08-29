"""Protected preview bytes and production JS lifecycle; not real-browser proof."""

from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "scenario",
    [
        "image",
        "pdf",
        "pdf_wrong_source",
        "pdf_wrong_page",
        "pdf_wrong_url_page",
        "pdf_bad_hash",
        "pdf_no_audit",
        "pdf_no_review",
        "pdf_bad_count",
        "audio",
        "video",
        "external_url",
        "wrong_token",
        "missing_hash",
        "unsafe_mime",
        "missing_verification",
        "http_error",
        "hash_mismatch",
        "oversized_header",
        "oversized_stream",
        "cancelled",
        "close_revokes",
        "open_success",
        "close_metadata_late",
        "close_media_late",
        "superseded",
        "safe_error",
    ],
)
def test_production_media_loader_and_inspector_lifecycle(scenario):
    node = shutil.which("node")
    assert node, "Node is required for production preview lifecycle tests"
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    functions = (
        script[
            script.index("    const RECORD_INSPECTOR_PREVIEW_MAX_BYTES") : script.index(
                "    function renderRecordInspector("
            )
        ]
        + script[
            script.index("    async function openRecordInspector(") : script.index(
                "    function changeInspectorPage("
            )
        ]
    )
    harness = r"""
const assert = require('node:assert/strict');
const crypto = require('node:crypto').webcrypto;
const bytes = new TextEncoder().encode('FICTIONAL protected media bytes');
const hash = require('node:crypto').createHash('sha256').update(bytes).digest('hex');
const token = 'a'.repeat(64), headers = {'X-MFLL-Client-Session':'fictional-session',
    'X-User-Role':'reviewer', 'X-Tenant-Id':'fictional-tenant'};
const element = () => ({hidden:false, innerHTML:'', textContent:'',
    setAttribute(name,value){this[name]=value}, replaceChildren(){this.innerHTML=''}, focus(){}});
const recordInspector=element(),recordInspectorViewer=element(),recordInspectorDetails=element(),
      recordInspectorBackdrop=element(),recordInspectorTitle=element(),recordInspectorSubtitle=element(),
      recordInspectorPageControls=element(),recordInspectorZoomControls=element(),recordInspectorClose=element();
let recordInspectorRequestEpoch=0,recordInspectorController=null,recordInspectorObjectUrl='',
    recordInspectorOwner=null,recordInspectorState=null;
const document={activeElement:element(),body:{classList:{add(){},remove(){}}}};
const revoked=[],created=[],rendered=[],requests=[],metadata=[];
const URL={createObjectURL(blob){const url='blob:fictional-'+created.length;
           created.push({url,blob});return url},
           revokeObjectURL(url){revoked.push(url)}};
const localRequestHeaders=()=>headers;
const makeSafeLocalError=({code,message})=>Object.assign(new Error(message||code),{safeCode:code});
const recordToken=b=>/^[a-f0-9]{64}$/i.test(b?.source_token||'')?b.source_token:'';
const closeSourcePreview=()=>{},showToast=()=>{},trackRecentWorkRecord=()=>{};
const renderRecordInspector=(p,url='')=>{recordInspectorState=p;rendered.push({p,url})};
const payload={token,open_url:'/api/records/open/'+token+'?page=1',preview_url:'/api/records/preview/'+token+'?page=1',page:1,source_hash:hash,
    source_hash_verified:true,viewer_kind:'image',size_bytes:bytes.length};
let mime='image/png',verified='true',ok=true,declared=bytes.length,changed=false,oversized=false,
    streamCancelled=false,responseCancelled=false,lockReleased=false,pendingMedia=null;
const pdfHeaders={'x-mfl-source-hash':hash,'x-mfl-preview-hash':hash,'x-mfl-page':'1',
    'x-mfl-page-count':'2','x-mfl-review-required':'true','x-mfl-audit-receipt':'f'.repeat(64)};
function response(){let sent=false;return {ok,headers:{get(name){return {
    ...pdfHeaders,'content-type':mime,'x-mfl-hash-verified':verified,'content-length':String(declared)}[name]}},
    body:{async cancel(){responseCancelled=true},getReader(){return {
        async read(){if(sent)return {done:true};sent=true;return {done:false,value:oversized?
            {byteLength:RECORD_INSPECTOR_PREVIEW_MAX_BYTES+1}:changed?new Uint8Array([0]):bytes}},
        async cancel(){streamCancelled=true},releaseLock(){lockReleased=true}
    }}}};}
let fetch=async(url,options)=>{requests.push({url,options});
    return pendingMedia?await pendingMedia:response()};
let fetchJson=async(url,options)=>{metadata.push({url,options});return payload};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
"""
    checks = r"""
(async()=>{
 const scenario=process.argv[1],controller=new AbortController();
 const rejectCode=async code=>assert.rejects(loadRecordInspectorMedia(payload,controller.signal),
    e=>e.safeCode===code);
 if(['image','pdf','audio','video'].includes(scenario)){
   payload.viewer_kind=scenario;mime={image:'image/png',pdf:'image/png',audio:'audio/wav',video:'video/mp4'}[scenario];
   assert.equal(await loadRecordInspectorMedia(payload,controller.signal),'blob:fictional-0');
   assert.equal(created[0].blob.type,mime);assert.equal(created[0].blob.size,bytes.length);
   assert.equal(requests[0].options.headers,headers);assert.equal(requests[0].options.redirect,'error');
   assert.equal(requests[0].options.mode,'same-origin');assert.equal(requests[0].options.cache,'no-store');
   assert.equal(requests[0].options.signal,controller.signal);assert.equal(lockReleased,true);
 } else if(scenario.startsWith('pdf_')){
   payload.viewer_kind='pdf';mime='image/png';
   if(scenario==='pdf_wrong_url_page'){
     payload.preview_url=payload.preview_url.replace('?page=1','?page=2');
     await rejectCode('record_preview_binding_invalid');assert.equal(requests.length,0);
   }else{
     const key={'pdf_wrong_source':'x-mfl-source-hash','pdf_wrong_page':'x-mfl-page',
       'pdf_bad_hash':'x-mfl-preview-hash','pdf_no_audit':'x-mfl-audit-receipt',
       'pdf_no_review':'x-mfl-review-required','pdf_bad_count':'x-mfl-page-count'}[scenario];
     pdfHeaders[key]='invalid';await rejectCode('record_preview_response_rejected');
     assert.equal(created.length,0);assert.equal(responseCancelled,true);
   }
 } else if(scenario==='external_url'||scenario==='wrong_token'||scenario==='missing_hash'){
   if(scenario==='external_url')payload.open_url='https://example.invalid/private';
   if(scenario==='wrong_token')payload.open_url=payload.open_url.replace(token,'b'.repeat(64));
   if(scenario==='missing_hash')payload.source_hash='';
   await rejectCode('record_preview_binding_invalid');assert.equal(requests.length,0);
 } else if(['unsafe_mime','missing_verification','http_error'].includes(scenario)){
   if(scenario==='unsafe_mime')mime='image/svg+xml';
   if(scenario==='missing_verification')verified='';
   if(scenario==='http_error')ok=false;
   await rejectCode('record_preview_response_rejected');assert.equal(responseCancelled,true);
 } else if(scenario==='hash_mismatch'){
   changed=true;await rejectCode('record_preview_hash_mismatch');assert.equal(created.length,0);
 } else if(scenario==='oversized_header'){
   declared=RECORD_INSPECTOR_PREVIEW_MAX_BYTES+1;await rejectCode('record_preview_too_large');
   assert.equal(responseCancelled,true);
 } else if(scenario==='oversized_stream'){
   oversized=true;await rejectCode('record_preview_too_large');assert.equal(streamCancelled,true);
   assert.equal(lockReleased,true);
 } else if(scenario==='cancelled'){
   controller.abort();await assert.rejects(loadRecordInspectorMedia(payload,controller.signal),
      e=>e.name==='AbortError');
   assert.equal(created.length,0);
 } else if(scenario==='close_revokes'){
   recordInspectorController=controller;recordInspectorObjectUrl='blob:prior';
   recordInspectorViewer.innerHTML='prior private media';closeRecordInspector();
   assert.equal(controller.signal.aborted,true);assert.deepEqual(revoked,['blob:prior']);
   assert.equal(recordInspectorViewer.innerHTML,'');assert.equal(recordInspector.hidden,true);
 } else if(scenario==='open_success'){
   assert.equal(await openRecordInspector({source_token:token}),true);
   assert.equal(metadata[0].options.signal.aborted,false);
   assert.equal(rendered.at(-1).url,'blob:fictional-0');
   closeRecordInspector();assert.deepEqual(revoked,['blob:fictional-0']);
 } else if(scenario==='close_metadata_late'||scenario==='superseded'){
   let resolve;fetchJson=()=>new Promise(r=>{resolve=r});
   const first=openRecordInspector({source_token:token});
   if(scenario==='close_metadata_late')closeRecordInspector();
   else {fetchJson=async()=>({...payload,filename:'current'});
      await openRecordInspector({source_token:token});}
   resolve({...payload,filename:'stale'});assert.equal(await first,false);
   assert.ok(!rendered.some(r=>r.p.filename==='stale'));
   if(scenario==='close_metadata_late'){assert.equal(created.length,0);assert.equal(recordInspector.hidden,true)}
   else assert.equal(rendered.at(-1).p.filename,'current');
 } else if(scenario==='close_media_late'){
   let resolve;pendingMedia=new Promise(r=>{resolve=r});
   const pending=openRecordInspector({source_token:token});await tick();
   closeRecordInspector();resolve(response());assert.equal(await pending,false);
   assert.equal(created.length,0);assert.equal(recordInspectorViewer.innerHTML,'');
 } else if(scenario==='safe_error'){
   fetch=async()=>{throw new Error('C:/private/REAL-RECORD sensitive detail')};
   assert.equal(await openRecordInspector({source_token:token}),false);
   assert.ok(!recordInspectorViewer.innerHTML.includes('sensitive'));
   assert.ok(recordInspectorViewer.innerHTML.includes('original was preserved'));
   assert.equal(recordInspectorViewer['aria-busy'],'false');
 }
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-e", harness + functions + checks, scenario],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_record_preview_stays_bound_to_session_matter_hash_and_inert_content(monkeypatch, tmp_path):
    # Fictional one-pixel PNG. No legal or private records.
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jfQAAAABJRU5ErkJggg=="
    )
    root = tmp_path / "fictional-matter"
    record = root / "02_PRIVATE_FORENSIC_MASTER/files/FICTIONAL.png"
    record.parent.mkdir(parents=True)
    record.write_bytes(data)
    row = {
        "evidence_id": "FICTIONAL",
        "private_copy_relpath": record.relative_to(root).as_posix(),
        "source_hash": hashlib.sha256(data).hexdigest(),
        "source_type": "png",
        "source_locator": record.name,
    }
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _: [row])
    api._record_open_tokens.clear()
    owner = {"role": "reviewer", "tenant_id": "fictional-tenant", "client_session_id": "a" * 48}
    context = api._record_capability_identity.set(owner)
    try:
        token = api._record_open_token(root, "FICTIONAL", record.name)
    finally:
        api._record_capability_identity.reset(context)
    headers = {
        "X-User-Role": owner["role"],
        "X-Tenant-Id": owner["tenant_id"],
        "X-MFLL-Client-Session": owner["client_session_id"],
    }
    client = TestClient(api.app)
    inspected = client.get(f"/api/records/inspect/{token}", headers=headers)
    assert inspected.status_code == 200
    assert inspected.json()["review_required"] is True
    url = inspected.json()["open_url"]
    assert client.get(url).status_code == 404  # Raw <img src> must not bypass the capability.
    opened = client.get(url, headers=headers)
    assert opened.status_code == 200 and opened.content == data
    assert opened.headers["x-mfl-hash-verified"] == "true"
    assert opened.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert client.get(url, headers={**headers, "X-Tenant-Id": "other"}).status_code == 404
    monkeypatch.setattr(api, "active_case_root", lambda: tmp_path / "other")
    assert client.get(url, headers=headers).status_code == 404
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    record.write_bytes(b"changed fictional bytes")
    assert client.get(url, headers=headers).status_code == 409


def test_preview_csp_allows_blobs_only_for_display_not_scripts_or_connections():
    csp = TestClient(api.app).get("/").headers["content-security-policy"]
    directives = {
        part.strip().split()[0]: part.strip().split()[1:] for part in csp.split(";") if part.strip()
    }
    for kind in ("img-src", "frame-src", "media-src"):
        assert "blob:" in directives[kind]
    assert directives["connect-src"] == ["'self'"]
    assert "blob:" not in directives["script-src"]
    assert directives["object-src"] == ["'none'"]


def test_production_and_mirrored_preview_assets_remain_identical():
    source = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_bytes()
    assert source == (ROOT / "maine_family_law_llm/ui/workbench.js").read_bytes()
    text = source.decode("utf-8")
    assert "const openUrl = mediaUrl;" in text
    assert "const openUrl = String(payload?.open_url" not in text
    activate = text[
        text.index("    async function activateSelectedCorpus(") : text.index(
            "    function sourceLane("
        )
    ]
    assert activate.index("closeRecordInspector();") < activate.index("'/api/activate-corpus'")


def test_irrelevant_inspector_controls_stay_hidden_in_both_shipped_stylesheets():
    css = (ROOT / "src/maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert css == (ROOT / "maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert (
        ".record-inspector-page-controls[hidden], .record-inspector-zoom-controls[hidden] "
        "{ display: none !important; }"
    ) in css
    # The hidden attribute removes irrelevant controls from layout, keyboard
    # navigation, and accessibility trees; a flex declaration must not undo it.
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "recordInspectorPageControls.hidden = kind !== 'pdf' || !pageCount;" in script
    assert "recordInspectorZoomControls.hidden = kind !== 'image';" in script


@pytest.mark.parametrize("native_viewer", [True, False, None])
def test_pdf_preview_renders_raster_and_text_without_native_plugin(native_viewer):
    import json

    node = shutil.which("node")
    assert node, "Node is required for production PDF fallback tests"
    source = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    render = source[source.index("    function renderRecordInspector(") : source.index(
        "    async function openRecordInspector("
    )]
    harness = r"""
const assert=require('node:assert/strict');
Object.defineProperty(globalThis,'navigator',{value:{pdfViewerEnabled:JSON.parse(process.argv[1])},configurable:true});
const el=()=>({hidden:false,innerHTML:'',textContent:'',querySelectorAll:()=>[],
  querySelector:()=>null,insertAdjacentHTML(){}});
let recordInspectorState=null,recordInspectorZoom=0;
const recordInspectorTitle=el(),recordInspectorSubtitle=el(),recordInspectorBadges=el(),
  recordInspectorDetails=el(),recordInspectorPageControls=el(),recordInspectorZoomControls=el(),
  recordInspectorPageInput=el(),recordInspectorPageCount=el(),recordInspectorPrevPage=el(),
  recordInspectorNextPage=el(),recordInspectorViewer=el();
const escapeHtml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const formatBytes=()=>'',recordInspectorMetaMarkup=()=>'';
"""
    checks = r"""
renderRecordInspector({viewer_kind:'pdf',filename:'FICTIONAL.pdf',page:2,page_count:3,
  preview:{page_text:'FICTIONAL indexed page <script>untrusted</script>'}},'blob:fictional');
const html=recordInspectorViewer.innerHTML;
assert.ok(html.includes('Indexed source text — page scope not verified'));
assert.ok(!html.includes('Indexed text for page 2'));
assert.ok(html.includes('FICTIONAL indexed page &lt;script&gt;'));
assert.ok(!html.includes('<script>'));
assert.ok(html.includes('not a visual reproduction'));
assert.ok(html.includes('Download verified copy'));
assert.ok(recordInspectorBadges.innerHTML.includes('Review required'));
assert.ok(!html.includes('<iframe'));
assert.ok(html.includes('Read indexed source text'));
assert.ok(html.includes('<img'));
assert.ok(html.includes('Locally rendered PDF page 2'));
assert.ok(html.includes('Local rendered page derivative'));
renderRecordInspector({viewer_kind:'pdf',page:2,page_count:3,preview:{page_text:'FICTIONAL'}},'');
assert.ok(recordInspectorViewer.innerHTML.includes('Rendering protected PDF page 2 locally'));
assert.ok(recordInspectorViewer.innerHTML.includes('FICTIONAL'));
"""
    result = subprocess.run([node, "-e", harness + render + checks, json.dumps(native_viewer)],
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr

"""Execute shipped export handlers: consent, bounded resources, honest delivery."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r"""
const assert = require('node:assert/strict');
const status={hidden:true,textContent:''}, events={}, timers=new Map();
const revoked=[], blobs=[], anchors=[];
let consent=true, confirms=0, clickError=false, appendError=false, buildCount=0;
const window={confirm(){confirms++;return consent;},
  setTimeout(fn,ms){assert.equal(ms,60000);const id=timers.size+1;timers.set(id,fn);return id;},
  clearTimeout(id){timers.delete(id);},addEventListener(name,fn){events[name]=fn;}};
const document={getElementById(){return status;},
  body:{appendChild(a){if(appendError)throw new Error('PRIVATE PATH');a.attached=true;}},
  createElement(){const a={attached:false,removed:false,
    click(){assert.ok(this.attached);if(clickError)throw new Error('PRIVATE PATH');},
    remove(){this.removed=true;}};anchors.push(a);return a;}};
const URL={createObjectURL(blob){blobs.push(blob);return 'blob:fictional-'+blobs.length;},
  revokeObjectURL(url){revoked.push(url);}};
const build=()=>{buildCount++;return 'Fictional private message';};
"""

CHECKS = {
    "cancel_no_materialization": """
consent=false;assert.equal(requestTranscriptDownload(build,'txt'),false);
assert.equal(confirms,1);assert.equal(buildCount,0);assert.equal(blobs.length,0);
assert.match(status.textContent,/cancelled/);assert.equal(status.hidden,false);
""",
    "retain_until_cleanup": """
assert.equal(requestTranscriptDownload(build,'txt'),true);
assert.equal(anchors[0].download,'maine-family-law-llm-transcript.txt');
assert.equal(anchors[0].hidden,true);assert.equal(revoked.length,0);
assert.match(status.textContent,/Download requested/);
assert.match(status.textContent,/confirm the file was saved/);
assert.equal(pendingTranscriptDownloads.size,1);
timers.values().next().value();assert.equal(revoked.length,1);
assert.equal(anchors[0].removed,true);assert.equal(pendingTranscriptDownloads.size,0);
""",
    "page_exit_releases_all": """
requestTranscriptDownload(build,'txt');requestTranscriptDownload(build,'json');
events.pagehide();assert.equal(revoked.length,2);assert.equal(timers.size,0);
assert.equal(pendingTranscriptDownloads.size,0);assert.ok(anchors.every(a=>a.removed));
events.pagehide();assert.equal(revoked.length,2);
""",
    "repeat_limit": """
for(let i=0;i<4;i++)assert.equal(requestTranscriptDownload(build,'txt'),true);
assert.equal(requestTranscriptDownload(build,'txt'),false);assert.equal(buildCount,4);
assert.match(status.textContent,/wait one minute/);assert.equal(revoked.length,0);
""",
    "oversize_utf8": """
assert.equal(requestTranscriptDownload(()=> 'é'.repeat(9*1024*1024),'txt'),false);
assert.equal(blobs.length,0);assert.match(status.textContent,/16 MiB/);
""",
    "serialization_failure": """
assert.equal(requestTranscriptDownload(()=>{throw new Error('PRIVATE PATH');},'json'),false);
assert.equal(blobs.length,0);assert.match(status.textContent,/could not start/);
assert.ok(!status.textContent.includes('PRIVATE'));
""",
    "click_failure": """
clickError=true;assert.equal(requestTranscriptDownload(build,'txt'),false);
assert.equal(revoked.length,1);assert.equal(pendingTranscriptDownloads.size,0);
assert.equal(timers.size,0);assert.match(status.textContent,/unchanged/);
assert.ok(!status.textContent.includes('PRIVATE'));
""",
    "attach_failure": """
appendError=true;assert.equal(requestTranscriptDownload(build,'json'),false);
assert.equal(revoked.length,1);assert.equal(pendingTranscriptDownloads.size,0);
assert.match(status.textContent,/could not start/);
""",
    "latest_public_turn_cannot_bypass_consent": """
const lastSources=[], lastPayload={search_mode:'maine_law'};
assert.equal(requestTranscriptDownload(build,'txt'),true);assert.equal(confirms,1);
""",
    "no_arbitrary_extension": """
assert.equal(requestTranscriptDownload(build,'exe'),false);
assert.equal(confirms,0);assert.equal(buildCount,0);assert.equal(blobs.length,0);
""",
}


def execute_js(checks, *, handlers=False):
    node = shutil.which("node")
    assert node, "Node is required to test production export functions"
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    functions = script[
        script.index("    function confirmFullLocalExport(") : script.index(
            "    function formatLocalTime("
        )
    ]
    if handlers:
        functions += script[
            script.index("    downloadButton.addEventListener('click'") : script.index(
                "    clearButton.addEventListener('click'"
            )
        ]
    result = subprocess.run(
        [node, "-"],
        input=HARNESS + checks[0] + functions + checks[1],
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("case", CHECKS)
def test_export_lifecycle(case):
    execute_js(("", CHECKS[case]))


def test_actual_txt_and_json_handlers_preserve_review_metadata():
    setup = """
const callbacks={};
const downloadButton={addEventListener(_,fn){callbacks.txt=fn;}};
const downloadJsonButton={addEventListener(_,fn){callbacks.json=fn;}};
const messages=[{at:'fictional-time',role:'user',text:'Fictional private earlier turn'}];
const lastPayload={grounded:false,review_required:true,local_agent_result:true,
  output_grounding:{status:'quoted_text_only',factual_claims_verified:false,legal_claims_verified:false}};
const lastSources=[{id:'fictional-source',text:'Fictional exact quotation'}], lastHandoffSources=[];
"""
    checks = """
(async()=>{
callbacks.txt();callbacks.json();assert.equal(confirms,2);
const txt=await blobs[0].text(), json=JSON.parse(await blobs[1].text());
assert.match(txt,/Fictional private earlier turn/);assert.match(txt,/Fictional exact quotation/);
assert.match(txt, /Review required/);assert.equal(json.schema_version,'local_chat_transcript_v3');
assert.deepEqual(json.latest_payload,lastPayload);assert.deepEqual(json.messages,messages);
assert.equal(json.review_required,true);assert.equal(json.not_legal_advice,true);
assert.deepEqual(json.latest_source_cards,lastSources);assert.equal(revoked.length,0);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    execute_js((setup, checks), handlers=True)


def test_production_assets_match_and_status_is_accessible():
    for name in ("workbench.js", "workbench.html", "workbench.css"):
        source = (ROOT / "src/maine_family_law_llm/ui" / name).read_bytes()
        assert source == (ROOT / "maine_family_law_llm/ui" / name).read_bytes()
    html = (ROOT / "src/maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    assert (
        'id="transcript-export-status" class="field-hint" role="status" '
        'aria-live="polite" aria-atomic="true" hidden' in html
    )

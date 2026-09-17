// One tiny local control: no app, API, model, network page or private records.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const output=path.join(root,'dist/model-candidates/compact-fleet-20260908');
const blobMode=process.argv.includes('--blob');
const tag=blobMode?'02':'01';
const target=path.join(output,`edge-download-control-${tag}.json`);
if(fs.existsSync(target)) throw new Error('Preserve prior evidence');
const require=createRequire(import.meta.url);
const {chromium}=require(path.join(process.env.MFL_PROOF_NODE_MODULES,'playwright'));
const scratch=path.join(root,'dist/qa/compact-ranked-ui');
const downloadScratch=path.resolve(process.env.TEMP || '');
if(!downloadScratch.startsWith(path.join(root,'dist','qa')+path.sep)) {
  throw new Error('A fresh repository-local QA TEMP is required');
}
const report={fictional_only:true,app_loaded:false,model_loaded:false,blob_mode:blobMode,events:[]};
let context;
try {
  context=await chromium.launchPersistentContext(path.join(scratch,'browser-profile'),{
    channel:'msedge',headless:true,acceptDownloads:true,
    downloadsPath:downloadScratch,
    env:{...process.env,TEMP:scratch,TMP:scratch,APPDATA:scratch,LOCALAPPDATA:scratch},
    serviceWorkers:'block',args:['--disable-background-networking','--disable-component-update'],
  });
  report.browser_version=context.browser().version();
  report.default_chromium_present=fs.existsSync(chromium.executablePath());
  context.on('close',()=>report.events.push('context_closed'));
  const page=context.pages()[0];
  page.on('crash',()=>report.events.push('page_crashed'));
  page.on('close',()=>report.events.push('page_closed'));
  await context.route('**/*',route=>route.abort());
  if(blobMode) {
    await page.setContent(`<button onclick="if(!confirm('Fictional export only'))return;const blob=new Blob(['fictional-control'],{type:'text/plain'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='fictional-control.txt';a.click();URL.revokeObjectURL(url);">Download control</button>`);
    page.once('dialog',dialog=>dialog.accept());
  } else {
    await page.setContent('<a download="fictional-control.txt" href="data:text/plain,fictional-control">Download control</a>');
  }
  const [download]=await Promise.all([page.waitForEvent('download',{timeout:15000}),page.locator(blobMode?'button':'a').click()]);
  report.events.push('download_event');
  await download.saveAs(path.join(output,`edge-download-control-${tag}.txt`));
  report.saved=fs.readFileSync(path.join(output,`edge-download-control-${tag}.txt`),'utf8')==='fictional-control';
} catch(error) {
  report.failure={name:error.name,message:error.message};
  process.exitCode=1;
} finally {
  if(context) await context.close().catch(()=>{});
  fs.writeFileSync(target,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify(report));
}

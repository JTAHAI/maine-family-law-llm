// Actual shipped page + canonical pack API; synthetic signatures/tensors only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
assert.match(input.run_id, /^[a-z0-9-]{1,20}$/);
assert.equal(new URL(input.base_url).hostname, '127.0.0.1');
assert.ok(path.resolve(input.pack_path).startsWith(path.join(root,'dist') + path.sep));
const output = path.join(root, 'dist/model-candidates/compact-fleet-20260908');
const target = path.join(output, `pack-browser-${input.run_id}.json`);
assert.ok(!fs.existsSync(target), 'Preserve prior evidence');
const require = createRequire(import.meta.url);
const {chromium} = require(path.join(process.env.MFL_PROOF_NODE_MODULES, 'playwright'));
const profile = path.join(root, 'dist/qa/compact-ranked-ui/browser-profile');
const report = {fictional_only:true, synthetic_pack:true, model_inference_tested:false,
  frozen_app_tested:false, ga_ready:false, page_errors:[], blocked_external_requests:[], assertions:[]};
let context, page;
try {
  context = await chromium.launchPersistentContext(profile, {
    channel:'msedge', headless:true, viewport:{width:1440,height:1000},
    env:{...process.env, TEMP:path.dirname(profile), TMP:path.dirname(profile), APPDATA:path.dirname(profile), LOCALAPPDATA:path.dirname(profile)},
    serviceWorkers:'block', args:['--disable-background-networking','--disable-component-update'],
  });
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin !== input.base_url) {
      report.blocked_external_requests.push(new URL(route.request().url()).origin); return route.abort();
    }
    return route.continue();
  });
  await context.addInitScript(({session}) => {
    localStorage.clear(); sessionStorage.clear();
    sessionStorage.setItem('mfl_local_capability_session_v1', session);
    localStorage.setItem('mfl-onboarding-complete', 'true');
  }, input);
  page = await context.newPage();
  page.on('pageerror', error => report.page_errors.push(error.message));
  await page.goto(input.base_url, {waitUntil:'networkidle'});
  assert.equal(await page.locator('body').getAttribute('data-production-ui'), 'workbench');
  assert.ok((await page.locator('body').innerText()).length > 300);
  assert.deepEqual(report.page_errors, []);
  report.assertions.push('whole_shipped_page_boots');
  await page.locator('#question').fill(input.question);
  await page.locator('#question').press('Enter');
  await page.getByRole('button',{name:'Review evidence',exact:true}).last().click();
  await page.locator('#model-pack-panel > summary').click();
  await page.locator('#model-pack-admin').check();
  await page.locator('#model-pack-refresh').click();
  await page.waitForFunction(() => document.getElementById('model-pack-status').textContent.includes('No active model pack'));
  report.assertions.push('canonical_inventory_no_active_pack');
  await page.locator('#model-pack-file').setInputFiles(input.pack_path);
  await page.locator('#model-pack-import').click();
  await page.waitForFunction(() => !document.getElementById('model-pack-activate').disabled, null, {timeout:30000});
  await page.getByText('Signed model details and artifact identity',{exact:true}).click();
  const details = JSON.parse(await page.locator('#model-pack-details').innerText());
  assert.match(details.pack_id, /^[a-f0-9]{64}$/);
  assert.ok(details.signed_details.models.every(row => row.evaluation_basis === 'synthetic'));
  assert.ok(details.signed_details.models.every(row => row.admission === 'admitted_for_dev'));
  report.pack_id = details.pack_id;
  report.assertions.push('real_chunk_upload_signature_hash_verification_and_identity_drilldown');
  await page.locator('#model-pack-activate').click();
  await page.locator('#model-pack-confirm-no').press('Escape');
  assert.equal(await page.locator('#model-pack-activate').isDisabled(), false);
  report.assertions.push('escape_declines_separate_activation');
  await page.locator('#model-pack-activate').click();
  await page.locator('#model-pack-confirm-yes').click();
  await page.waitForFunction(() => document.getElementById('model-pack-status').textContent.includes('Pack activated'));
  assert.equal(await page.locator('#local-agent-run').isDisabled(), true);
  await page.locator('#model-pack-refresh').click();
  await page.locator('#model-pack-job').selectOption('');
  await page.locator('#model-pack-refresh').click();
  await page.waitForFunction(() => document.getElementById('model-pack-status').textContent.includes('Research pack installed'));
  report.status_text = await page.locator('#model-pack-status').innerText();
  assert.match(report.status_text, /not approved for production use/);
  assert.match(report.status_text, /Hardware and worker startup have not been verified/);
  report.assertions.push('development_admission_not_misrepresented_as_operational_or_ga');
  await page.locator('#model-pack-status').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(output,`pack-browser-${input.run_id}-readiness.png`)});
  assert.deepEqual(report.page_errors, []);
  report.passed = true;
} catch (error) {
  report.failure = String(error);
  if (page) await page.screenshot({path:path.join(output,`pack-browser-${input.run_id}-failure.png`)}).catch(()=>{});
  process.exitCode = 1;
} finally {
  if (context) await context.close();
  report.browser_closed = true;
  fs.writeFileSync(target, JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
}

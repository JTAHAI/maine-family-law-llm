// Entire shipped page, real canonical HTTP/model, explicitly fictional startup/search.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
assert.match(input.run_id, /^[a-z0-9-]{1,20}$/);
assert.equal(new URL(input.base_url).hostname, '127.0.0.1');
const output = path.join(root, 'dist/model-candidates/compact-fleet-20260908');
const target = path.join(output, `ranked-browser-${input.run_id}.json`);
assert.ok(!fs.existsSync(target), 'Preserve prior evidence');
const require = createRequire(import.meta.url);
const {chromium} = require(path.join(process.env.MFL_PROOF_NODE_MODULES, 'playwright'));
// pytest supplies a fresh repo-local TEMP; never reuse a cleanup-denied target.
const downloadScratch = path.resolve(process.env.TEMP || '');
assert.ok(downloadScratch.startsWith(path.join(root,'dist','qa') + path.sep),
  'A fresh repository-local QA TEMP is required');
const profile = path.join(downloadScratch, 'browser-profile');
assert.ok(!fs.existsSync(profile), 'Never reuse an old or cleanup-denied profile');
const report = {fictional_only:true, production_page_boot_tested:false,
  live_browser_to_model_api_tested:false, production_factory_tested:false,
  frozen_app_tested:false, installed_package_tested:false, ga_ready:false,
  page_errors:[], blocked_external_requests:[], assertions:[], responses:[]};
report.browser_events = [];
report.phase = 'launch';
let context;
let browser;
let page;
try {
  const engine=input.browser_engine || 'msedge-ephemeral';
  assert.ok(['msedge','msedge-ephemeral','chromium'].includes(engine));
  const launchOptions={
    headless:true, downloadsPath:downloadScratch,
    env:{...process.env, TEMP:downloadScratch, TMP:downloadScratch,
      APPDATA:downloadScratch, LOCALAPPDATA:downloadScratch},
    args:['--disable-background-networking','--disable-component-update'],
  };
  const contextOptions={acceptDownloads:true,viewport:{width:1440,height:1000},serviceWorkers:'block'};
  if(engine!=='msedge') {
    if(engine==='chromium') assert.ok(fs.existsSync(chromium.executablePath()),'Use existing engine; do not download');
    browser=await chromium.launch({...launchOptions,...(engine==='msedge-ephemeral'?{channel:'msedge'}:{})});
    context=await browser.newContext(contextOptions);
  } else {
    context=await chromium.launchPersistentContext(profile,{...launchOptions,...contextOptions,channel:'msedge'});
  }
  report.browser_engine=engine;
  report.persistent_profile=engine==='msedge';
  report.browser_version=context.browser().version();
  context.on('close', () => report.browser_events.push({event:'context_closed',phase:report.phase}));
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin !== input.base_url) {
      report.blocked_external_requests.push(new URL(route.request().url()).origin);
      return route.abort();
    }
    return route.continue();
  });
  await context.addInitScript(({session}) => {
    localStorage.clear(); sessionStorage.clear();
    sessionStorage.setItem('mfl_local_capability_session_v1',session);
    localStorage.setItem('mfl-onboarding-complete','true');
  }, input);
  page = await context.newPage();
  page.on('close', () => report.browser_events.push({event:'page_closed',phase:report.phase}));
  page.on('crash', () => report.browser_events.push({event:'page_crashed',phase:report.phase}));
  page.on('pageerror', error => report.page_errors.push(error.message));
  page.on('response', async response => {
    const route = new URL(response.url()).pathname;
    if (route.startsWith('/api/local-agent/')) report.responses.push({route,status:response.status()});
    if (route === '/api/local-agent/run' && response.ok()) {
      const result = await response.json().catch(()=>null);
      if (result) {
        report.run_outcomes ??= [];
        report.run_outcomes.push({status:result.status,
          warnings:(result.warnings || []).filter(code => [
            'fast_interchange_generation_timeout','fast_interchange_compact_python_network_denied',
            'fast_interchange_compact_model_integrity_failed'
          ].includes(code))});
      }
    }
  });
  await page.goto(input.base_url, {waitUntil:'networkidle'});
  assert.equal(await page.locator('body').getAttribute('data-production-ui'), 'workbench');
  assert.ok((await page.locator('body').innerText()).length > 300);
  await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-startup.png`)});
  report.production_page_boot_tested = true;
  assert.deepEqual(report.page_errors, []);
  report.assertions.push('whole_shipped_page_boots');
  if (!input.sequence_only) {
  // Use the real composer and its streamed-result handler; only the initial search is fictional.
  await page.locator('#question').fill(input.question);
  await page.locator('#question').press('Enter');
  await page.getByRole('button',{name:'Review evidence',exact:true}).last().click();
  await page.locator('#local-agent-refresh-preview').waitFor({state:'visible'});
  await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
  await page.locator('#local-agent-model').fill(input.model_name || 'compact-research-record-passage-ranking');
  await page.locator('#local-agent-endpoint').fill('http://127.0.0.1:1');
  await page.locator('#local-agent-refresh-preview').click();
  if (input.hardware_fault_test) {
    await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
    assert.equal(await page.locator('#local-agent-run').isDisabled(), true);
    assert.match(await page.locator('#local-agent-preview-summary').innerText(), /Available RAM could not be confirmed or is exhausted/);
    const observation = await page.evaluate(async () => (await fetch('/__qa/worker-observation')).json());
    assert.equal(observation.process_started, false);
    await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-hardware-blocked.png`)});
    report.assertions.push('unknown_or_exhausted_memory_blocks_ui_without_worker_start');
    await page.evaluate(async () => {
      const response = await fetch('/__qa/restore-real-hardware', {method:'POST'});
      if (!response.ok) throw new Error('Hardware fixture reset failed');
    });
    await page.locator('#local-agent-refresh-preview').click();
  }
  await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
  if (input.hardware_fault_test) {
    assert.match(await page.locator('#local-agent-preview-summary').innerText(), /Hardware check passed.*CPU/);
    report.normal_hardware_gate_tested = true;
    report.assertions.push('real_host_headroom_and_cpu_policy_pass_after_fresh_preview');
  }
  assert.match(await page.locator('#local-agent-preview-summary').innerText(), /Research model — not approved for production use/);
  assert.match(await page.locator('#local-agent-preview-summary').innerText(), /private process pipes; no model network endpoint/);
  await page.locator('#local-agent-context-list details summary').first().click();
  assert.match(await page.locator('#local-agent-context-list').innerText(), input.field_mode ? /scheduled for 09:00 but began at 09:25/ : /the cost worksheet is missing/);
  if (input.field_mode) {
    assert.match(await page.locator('#local-agent-preview-summary').innerText(), /Research field contract: Time.*Reported-event wording/);
    assert.match(await page.locator('#local-agent-preview-summary').innerText(), /no deterministic fallback/);
    report.assertions.push('explicit_field_basis_and_model_producer_visible_before_approval');
  }
  await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-approval.png`)});
  report.assertions.push('exact_source_packet_visible_before_approval');
  const beforeCancel = await page.locator('.message.assistant').count();
  await page.locator('#local-agent-run').click();
  // Poll resolved JSON explicitly. A fulfilled JSHandle/Promise is not proof
  // that a subprocess exists; require the observation itself to be true.
  const observationDeadline = Date.now() + 45000;
  while (Date.now() < observationDeadline) {
    report.cancel_observation = await page.evaluate(async () => {
      const response = await fetch('/__qa/worker-observation', {cache:'no-store'});
      return await response.json();
    });
    if (report.cancel_observation.process_started === true) break;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  assert.equal(report.cancel_observation.process_started, true);
  assert.ok(Number.isInteger(report.cancel_observation.child_pid));
  await page.locator('#local-agent-cancel').click();
  await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled,
    null, {timeout:60000});
  assert.equal(await page.locator('.message.assistant').count(), beforeCancel);
  assert.match(await page.locator('#local-agent-status').innerText(), /cancel|discarded/i);
  report.assertions.push('cancel_real_worker_preserves_original_answer');
  await page.locator('#local-agent-refresh-preview').click();
  await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
  if (input.network_fault_test) {
    await page.evaluate(async () => {
      const response = await fetch('/__qa/arm-network-fault', {method:'POST'});
      if (!response.ok) throw new Error('Dependency fixture setup failed');
    });
    await page.locator('#local-agent-run').click();
    await page.waitForFunction(() => document.getElementById('local-agent-status').textContent.includes('Keep Local-only on'),
      null, {timeout:60000});
    assert.equal(await page.locator('.message.assistant').count(), beforeCancel);
    assert.equal(await page.locator('#local-agent-modal').isVisible(), true);
    assert.equal(await page.locator('#local-agent-run').isDisabled(), true);
    await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
    const blockedText = await page.locator('#local-agent-status').innerText();
    assert.match(blockedText, /original records and answer are unchanged/);
    assert.match(blockedText, /not OS-level isolation/);
    assert.match(blockedText, /Review required/);
    assert.doesNotMatch(blockedText, /fictional\.invalid/);
    const statusLayout = await page.locator('#local-agent-status').evaluate(element => {
      const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
      return {font:parseFloat(style.fontSize), bottom:rect.bottom, right:rect.right,
        width:innerWidth, height:innerHeight, role:element.getAttribute('role'),
        live:element.getAttribute('aria-live')};
    });
    assert.ok(statusLayout.font >= 14);
    assert.ok(statusLayout.bottom <= statusLayout.height && statusLayout.right <= statusLayout.width);
    assert.equal(statusLayout.role, 'status');
    assert.equal(statusLayout.live, 'polite');
    report.network_status_layout = statusLayout;
    await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-network-blocked.png`)});
    report.network_blocked_dom = blockedText;
    report.assertions.push('caught_child_network_attempt_discards_output_and_requires_new_approval');
    await page.evaluate(async () => {
      const response = await fetch('/__qa/restore-real-ranker', {method:'POST'});
      if (!response.ok) throw new Error('Ranker fixture reset failed');
    });
    await page.locator('#local-agent-refresh-preview').click();
    await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
  }
  if (input.timeout_fault_test) {
    await page.evaluate(async () => {
      const response = await fetch('/__qa/arm-timeout-fault', {method:'POST'});
      if (!response.ok) throw new Error('Timeout fixture setup failed');
    });
    await page.locator('#local-agent-run').click();
    await page.waitForFunction(() => document.getElementById('local-agent-status').textContent.includes('exceeded its time limit'));
    assert.equal(await page.locator('.message.assistant').count(), beforeCancel);
    assert.equal(await page.locator('#local-agent-modal').isVisible(), true);
    assert.equal(await page.locator('#local-agent-run').isDisabled(), true);
    await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
    const timeoutText = await page.locator('#local-agent-status').innerText();
    assert.match(timeoutText, /inspect the selected sources without the model/);
    assert.match(timeoutText, /original records and answer are unchanged/);
    assert.match(timeoutText, /Review required/);
    await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-timeout.png`)});
    report.timeout_recovery_dom = timeoutText;
    report.assertions.push('timeout_has_safe_source_fallback_and_requires_fresh_approval');
    await page.locator('#local-agent-refresh-preview').click();
    await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
  }
  if (input.inventory_fault_test) {
    await page.evaluate(async () => {
      const response = await fetch('/__qa/arm-inventory-fault', {method:'POST'});
      if (!response.ok) throw new Error('Inventory fixture setup failed');
    });
    await page.locator('#local-agent-run').click();
    await page.waitForFunction(() => document.getElementById('local-agent-status').textContent.includes('Do not edit its receipt'),
      null, {timeout:60000});
    assert.equal(await page.locator('.message.assistant').count(), beforeCancel);
    assert.equal(await page.locator('#local-agent-modal').isVisible(), true);
    assert.equal(await page.locator('#local-agent-run').isDisabled(), true);
    const message = await page.locator('#local-agent-status').innerText();
    assert.match(message, /Restore the original verified model package/);
    assert.match(message, /original records and answer are unchanged/);
    assert.match(message, /Review required/);
    assert.doesNotMatch(message, /[A-Z]:\\|tokenizer\.json|Traceback/);
    report.inventory_failure_dom = message;
    await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-inventory-blocked.png`)});
    await page.evaluate(async () => {
      const response = await fetch('/__qa/restore-inventory', {method:'POST'});
      if (!response.ok) throw new Error('Inventory fixture restoration failed');
    });
    await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
    await page.locator('#local-agent-refresh-preview').click();
    await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
    report.assertions.push('forged_tokenizer_receipt_is_rejected_and_requires_restoration_and_new_approval');
  }
  await page.locator('#local-agent-run').click();
  // Observe completion OR a visible blocked result; do not wait 90 seconds
  // for a modal that correctly stays open on failure. The runtime's existing
  // 90-second cold-load limit is unchanged; allow bounded response/cleanup time.
  await page.waitForFunction(() => document.getElementById('local-agent-modal').getAttribute('aria-hidden') === 'true'
      || !document.getElementById('local-agent-refresh-preview').disabled, null, {timeout:110000});
  assert.equal(await page.locator('#local-agent-modal').isVisible(), false,
    await page.locator('#local-agent-status').innerText());
  const answer = page.locator('.message.assistant').last();
  if (input.field_mode) {
    assert.match(await answer.innerText(), /Source-text candidate:.*09:25/);
    assert.match(await answer.innerText(), /Not a verified fact/);
    assert.match(await answer.innerText(), /no deterministic fallback/);
    report.assertions.push('real_qa_value_is_not_an_established_finding');
  } else {
    assert.match(await answer.innerText(), /relevance is unknown/i);
    assert.match(await answer.innerText(), /the cost worksheet is missing/);
    assert.match(await answer.innerText(), /promises to send/);
  }
  assert.match(await answer.innerText(), /review required/i);
  assert.match(await answer.locator('[data-model-grounding]').innerText(), /Quoted text checked; facts and law unverified/);
  const groundingBadges = await page.locator('#answer-badges').innerText();
  assert.match(groundingBadges, /Quoted text checked; facts and law unverified/);
  assert.doesNotMatch(groundingBadges, /source grounded/);
  report.assertions.push('model_quote_match_is_not_shown_as_grounded_claims');
  report.live_browser_to_model_api_tested = true;
  report.assertions.push(input.field_mode ? 'approved_canonical_request_returns_real_qa_field' : 'approved_canonical_request_returns_real_ranker_passages');
  await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-result.png`)});
  report.result_dom = (await answer.innerText()).slice(0,14000);
  // Real source-card listeners, not an extracted renderer harness.
  const source = answer.locator('.chat-evidence-card').first();
  await source.scrollIntoViewIfNeeded();
  await source.focus();
  assert.ok(await source.evaluate(el => document.activeElement === el));
  await source.press('Enter');
  await page.locator('#source-preview-flyout').waitFor({state:'visible'});
  const candidates = page.locator(input.field_mode
    ? '#source-preview-body section.source-preview-snippet:has(> strong:text-is("Exact source span"))'
    : '#source-preview-body details.source-preview-snippet');
  assert.equal(await candidates.count(), input.field_mode ? 1 : 3);
  for (let i=0;!input.field_mode && i<await candidates.count();i++) {
    const summary = candidates.nth(i).locator('summary');
    await summary.focus();
    if (await candidates.nth(i).getAttribute('open') === null) await summary.press('Enter');
    assert.equal(await candidates.nth(i).getAttribute('open'), '');
  }
  if (input.field_mode) {
    assert.match(await page.locator('#source-preview-body').innerText(), /09:25/);
    assert.match(await page.locator('#source-preview-body').innerText(), /scheduled for 09:00/);
  } else {
    assert.match(await page.locator('#source-preview-body').innerText(), /the cost worksheet is missing/);
    assert.match(await page.locator('#source-preview-body').innerText(), /promises to send/);
  }
  await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-source.png`)});
  report.assertions.push(input.field_mode ? 'exact_field_and_full_original_context_expand_from_source_card' : 'all_three_exact_passages_expand_from_actual_source_card');
  await page.locator('#source-preview-close').click();
  await page.locator('#source-preview-flyout').waitFor({state:'hidden'});
  assert.ok(await source.evaluate(el => document.activeElement === el));
  await source.press('Space');
  await page.locator('#source-preview-flyout').waitFor({state:'visible'});
  await page.locator('#source-preview-close').click();
  report.assertions.push('source_dialog_returns_focus_and_reopens_with_space');
  await answer.locator('.chat-context-manifest summary').click();
  const manifestText = await answer.locator('.chat-context-manifest').innerText();
  assert.match(manifestText, /Approved local-model context/);
  assert.doesNotMatch(manifestText, /Nothing was sent to a model/);
  report.assertions.push('post_run_manifest_does_not_claim_no_model_transmission');
  report.phase = 'export_cancel';
  let cancelledDownloads = 0;
  const unexpectedDownload = () => { cancelledDownloads++; };
  page.on('download', unexpectedDownload);
  page.once('dialog', dialog => dialog.dismiss());
  await page.locator('#download-button').focus();
  await page.locator('#download-button').press('Enter');
  await page.waitForFunction(() => document.getElementById('transcript-export-status').textContent.includes('Export cancelled'));
  assert.equal(cancelledDownloads, 0);
  page.off('download', unexpectedDownload);
  assert.equal(await answer.locator('[data-model-grounding]').count(), 1);
  report.assertions.push('keyboard_export_cancel_creates_no_download_and_preserves_answer');
  let exportConsent = null;
  report.phase = 'export_consent';
  page.once('dialog', async dialog => {
    exportConsent = {type:dialog.type(),message:dialog.message()};
    if (dialog.type() === 'confirm' && dialog.message().includes('private-record excerpts')) await dialog.accept();
    else await dialog.dismiss();
  });
  const [download] = await Promise.all([
    page.waitForEvent('download', {timeout:15000}),
    page.locator('#download-button').click()
  ]);
  assert.equal(exportConsent?.type, 'confirm');
  assert.match(exportConsent.message, /private-record excerpts/);
  const transcriptPath = path.join(output,`ranked-browser-${input.run_id}-transcript.txt`);
  assert.ok(!fs.existsSync(transcriptPath), 'Preserve prior export evidence');
  report.phase = 'export_save';
  await download.saveAs(transcriptPath);
  report.phase = 'export_validation';
  const transcript = fs.readFileSync(transcriptPath,'utf8');
  const metadata = JSON.parse(transcript.split('Latest payload metadata:\n')[1].split('\nLatest source cards (full local export):')[0].trim());
  assert.equal(metadata.grounded, false);
  assert.equal(metadata.output_grounding.status, 'quoted_text_only');
  assert.equal(metadata.output_grounding.quoted_text_checked, true);
  assert.equal(metadata.output_grounding.factual_claims_verified, false);
  assert.equal(metadata.output_grounding.legal_claims_verified, false);
  assert.equal(metadata.review_required, true);
  assert.match(transcript, input.field_mode ? /Not a verified fact/ : /relevance is unknown/);
  report.transcript_grounding = metadata.output_grounding;
  report.transcript_export = path.relative(root,transcriptPath);
  report.assertions.push('explicitly_confirmed_fictional_transcript_preserves_unverified_claim_status');
  assert.match(await page.locator('#transcript-export-status').innerText(), /Download requested.*confirm the file was saved/);
  assert.equal(await page.locator('#transcript-export-status').getAttribute('role'), 'status');
  assert.ok(await page.locator('#transcript-export-status').evaluate(el => parseFloat(getComputedStyle(el).fontSize) >= 14));
  report.phase = 'json_export';
  const more = page.locator('.composer-actions details.more-menu');
  if (await more.getAttribute('open') === null) await more.locator('summary').click();
  page.once('dialog', async dialog => {
    assert.equal(dialog.type(), 'confirm');
    assert.match(dialog.message(), /private-record excerpts/);
    await dialog.accept();
  });
  const [jsonDownload] = await Promise.all([
    page.waitForEvent('download', {timeout:15000}),
    page.locator('#download-json-button').press('Enter')
  ]);
  const jsonPath = path.join(output,`ranked-browser-${input.run_id}-transcript.json`);
  assert.ok(!fs.existsSync(jsonPath), 'Preserve prior export evidence');
  await jsonDownload.saveAs(jsonPath);
  const jsonTranscript = JSON.parse(fs.readFileSync(jsonPath,'utf8'));
  assert.equal(jsonTranscript.schema_version, 'local_chat_transcript_v3');
  assert.equal(jsonTranscript.review_required, true);
  assert.deepEqual(jsonTranscript.latest_payload.output_grounding, metadata.output_grounding);
  assert.equal(jsonTranscript.latest_payload.grounded, false);
  assert.ok(jsonTranscript.latest_source_cards.length > 0);
  assert.ok(jsonTranscript.messages.some(message => message.text.includes(input.question)));
  report.transcript_json_export = path.relative(root,jsonPath);
  report.assertions.push('confirmed_json_export_preserves_sources_messages_and_unverified_status');
  await more.locator('summary').click();
  await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-export.png`)});
  report.assertions.push('persistent_readable_download_status_does_not_claim_confirmed_save');
  report.phase = 'clear_export_context';
  assert.ok(await page.locator('a[download^="maine-family-law-llm-transcript."]').count() > 0);
  await more.locator('summary').click();
  page.once('dialog', async dialog => {
    assert.match(dialog.message(), /Clear the visible conversation/);
    await dialog.accept();
  });
  await page.locator('#clear-button').click();
  assert.equal(await page.locator('a[download^="maine-family-law-llm-transcript."]').count(), 0);
  assert.equal(await page.locator('#transcript-export-status').isVisible(), false);
  assert.equal(await page.locator('#transcript-export-status').innerText(), '');
  report.assertions.push('clearing_conversation_revokes_pending_private_export_links');
  }
  if (input.field_sequence) {
    report.field_sequence = [];
    for (const stage of ['mixed','withheld','recovered']) {
      await page.evaluate(async stage => {
        const response = await fetch('/__qa/field-sequence/'+stage, {method:'POST'});
        if (!response.ok) throw new Error('Fictional sequence fixture failed');
      }, stage);
      const reviewButtonsBefore = await page.getByRole('button',{name:'Review evidence',exact:true}).count();
      await page.locator('#question').fill(input.question);
      await page.locator('#question').press('Enter');
      await page.waitForFunction(previous => Array.from(document.querySelectorAll('button'))
        .filter(button=>button.textContent.trim()==='Review evidence').length > previous,
        reviewButtonsBefore, {timeout:30000});
      await page.getByRole('button',{name:'Review evidence',exact:true}).last().click();
      await page.locator('#local-agent-refresh-preview').waitFor({state:'visible'});
      await page.waitForFunction(() => !document.getElementById('local-agent-refresh-preview').disabled);
      await page.locator('#local-agent-model').fill(input.model_name);
      await page.locator('#local-agent-endpoint').fill('http://127.0.0.1:1');
      await page.locator('#local-agent-refresh-preview').click();
      await page.waitForFunction(() => !document.getElementById('local-agent-run').disabled);
      const responseReady = page.waitForResponse(response => new URL(response.url()).pathname === '/api/local-agent/run' && response.request().method() === 'POST');
      await page.locator('#local-agent-run').click();
      const response = await responseReady;
      assert.equal(response.status(),200);
      const payload = await response.json();
      await page.locator('#local-agent-modal').waitFor({state:'hidden',timeout:60000});
      const latest = page.locator('.message.assistant').last();
      const expectedIds = stage === 'mixed' ? ['REC-1','REC-2'] : stage === 'withheld' ? ['REC-2','REC-3'] : ['REC-4'];
      assert.deepEqual(payload.output_validation.fields.map(row=>row.source_id),expectedIds);
      assert.equal(payload.grounded,false);
      assert.equal(payload.review_required,true);
      assert.equal(payload.output_validation.absence_verified,false);
      assert.equal(payload.output_validation.deterministic_fallback_used,false);
      assert.equal(payload.output_validation.source_spans.length,stage === 'withheld' ? 0 : 1);
      assert.equal(await latest.locator('.chat-evidence-card').count(),expectedIds.length);
      const dom = await latest.innerText();
      assert.match(dom,/review required/i);
      if (stage === 'withheld') {
        assert.equal(payload.output_grounding.quoted_text_checked,false);
        assert.match(dom,/No source-field candidate retained — absence not established/i);
        assert.doesNotMatch(dom,/Source-text candidate|quotations checked/i);
      } else {
        assert.equal(payload.output_grounding.quoted_text_checked,true);
        assert.match(dom,stage === 'mixed' ? /09:25/ : /11:10/);
      }
      if (stage !== 'recovered') assert.match(dom,/does not establish absence/);
      if (stage === 'withheld') {
        assert.match(dom,/source contains dispute, attribution or conditional wording/);
        assert.match(dom,/Planned, conditional or attributed wording/);
      }
      if (stage === 'recovered') assert.doesNotMatch(dom,/09:25|10:20|REC-2|REC-3|No source-field candidate retained/);
      for (let index=0;index<expectedIds.length;index++) {
        const card=latest.locator('.chat-evidence-card').nth(index);
        await card.scrollIntoViewIfNeeded();
        await card.focus(); await card.press('Enter');
        await page.locator('#source-preview-flyout').waitFor({state:'visible'});
        const sourceDom=await page.locator('#source-preview-body').innerText();
        assert.ok(sourceDom.includes(expectedIds[index]));
        if ((stage==='mixed' && index===1) || stage==='withheld') {
          assert.match(sourceDom,/Exact source span unavailable/);
          assert.match(sourceDom,expectedIds[index]==='REC-2' ? /actual start is unknown/ : /account is disputed/);
          assert.doesNotMatch(sourceDom,/09:25|11:10/);
        }
        await page.locator('#source-preview-close').click();
        assert.ok(await card.evaluate(el=>document.activeElement===el));
      }
      report.field_sequence.push({stage,status:payload.status,fields:payload.output_validation.fields,
        grounding:payload.output_grounding,receipt:payload.provenance_receipt.receipt_sha256,
        dom:dom.slice(0,14000)});
      const reviewStatus=latest.locator('.local-agent-receipt[role="status"]').first();
      await reviewStatus.scrollIntoViewIfNeeded();
      const layout=await reviewStatus.evaluate(el=>({font:parseFloat(getComputedStyle(el).fontSize),
        paragraphFont:parseFloat(getComputedStyle(el.querySelector('p')).fontSize),
        color:getComputedStyle(el).color,background:getComputedStyle(el).backgroundColor,
        width:el.getBoundingClientRect().width,scroll:el.scrollWidth}));
      assert.ok(layout.font >= 14 && layout.paragraphFont >= 14);
      assert.ok(layout.scroll <= layout.width+1);
      report.field_sequence.at(-1).review_status_layout=layout;
      await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-${stage}.png`)});
      report.assertions.push('field_sequence_'+stage+'_has_own_results_sources_and_review_state');
    }
    assert.equal(new Set(report.field_sequence.map(row=>row.receipt)).size,3);
    report.assertions.push('repeated_field_runs_have_distinct_hash_bound_receipts');
  }
  assert.deepEqual(report.page_errors, []);
} catch (error) {
  report.failure = {name:error.name,message:error.message};
  if (page && !page.isClosed()) {
    report.failure_dom = await page.locator('body').innerText().then(text=>text.slice(0,16000)).catch(()=>null);
    await page.screenshot({path:path.join(output,`ranked-browser-${input.run_id}-failure.png`)}).catch(()=>{});
  }
  process.exitCode = 1;
} finally {
  report.phase = 'cleanup';
  if (context) await context.close();
  if (browser) await browser.close();
  report.browser_closed = true;
  fs.writeFileSync(target,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({assertions:report.assertions,failure:report.failure,errors:report.page_errors}));
}

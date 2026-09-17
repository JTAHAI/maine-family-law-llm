// Component verification of shipped functions/styles with fictional API data.
// NOT a production server, signed model, desktop/frozen, or installed-MSIX test.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const option = (name) => args[args.indexOf(name) + 1];
const runId = args.includes('--run-id') ? option('--run-id') : '01';
assert.match(runId, /^[a-z0-9-]{1,20}$/);
const output = path.join(root, 'dist/model-candidates/compact-fleet-20260908');
const reportPath = path.join(output, `ranked-ui-${runId}.json`);
assert.ok(!fs.existsSync(reportPath), 'Preserve previous evidence');
const sourcePath = path.join(root, 'src/maine_family_law_llm/ui/workbench.js');
const source = fs.readFileSync(sourcePath, 'utf8');
assert.equal(source, fs.readFileSync(path.join(root, 'maine_family_law_llm/ui/workbench.js'), 'utf8'));
const names = ['escapeHtml', 'normalizedSourceLane', 'sourceIdentity', 'sourceBasename',
  'sourceTextAtCodePoints', 'rankedSourceSpanMarkup', 'sourcePreviewMarkup',
  'localAgentCitationsWithVerifierSpans', 'renderLocalAgentReceipt', 'bindSourceCardActivation'];
const functions = names.map((name) => {
  const start = source.indexOf(`    function ${name}(`);
  assert.ok(start >= 0, `Production function missing: ${name}`);
  const end = source.indexOf('\n    function ', start + 1);
  assert.ok(end > start);
  return source.slice(start, end);
}).join('\n');
const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(functions, sandbox, {timeout: 1000});
const apiReceipt = JSON.parse(fs.readFileSync(path.join(output, 'ranked-canonical-api-02.json')));
assert.equal(apiReceipt.fictional_only, true);
const payload = apiReceipt.payload;
const clone = (value) => JSON.parse(JSON.stringify(value));
const sha = (value) => crypto.createHash('sha256').update(value).digest('hex');
const report = {
  level: 'shipped_component_functions_styles_and_markup_with_fictional_canonical_response',
  fictional_only: true, production_page_boot_tested: false,
  real_model_api_evidence_reused: 'ranked-canonical-api-02.json',
  live_browser_to_model_api_tested: false, frozen_app_tested: false,
  installed_package_tested: false, production_model_admitted: false, ga_ready: false,
  source_sha256: sha(source), tests: [], browser: {executed: false},
};
const record = (name, callback) => {
  try { callback(); report.tests.push({name, passed: true}); }
  catch (error) { report.tests.push({name, passed: false, failure: error.message}); }
};

record('all_three_passages_stay_on_one_source_card', () => {
  const cards = sandbox.localAgentCitationsWithVerifierSpans(payload);
  assert.equal(cards.length, 1);
  assert.equal(cards[0].metadata.source_span_candidates.length, 3);
  const markup = sandbox.sourcePreviewMarkup(cards[0]);
  assert.equal((markup.match(/<summary>Candidate /g) || []).length, 3);
  assert.match(markup, /the cost worksheet is missing/);
  assert.match(markup, /promises to send/);
  assert.match(markup, /relevance unknown/);
});
record('citation_numbering_and_source_identity_never_shift', () => {
  const changed = clone(payload);
  const second = clone(changed.citations[0]);
  second.source_id = 'REC-2';
  second.source_reference.source_id = 'REC-2';
  changed.citations.push(second);
  changed.output_validation.source_spans.push(...payload.output_validation.source_spans.map(
    row => ({...row, reference: 2, source_id: 'REC-2'})));
  const cards = sandbox.localAgentCitationsWithVerifierSpans(changed);
  assert.deepEqual(Array.from(cards, row => row.source_id), ['REC-1', 'REC-2']);
  assert.equal(cards[1].metadata.source_span_candidates.length, 3);
  assert.equal(cards[0].metadata.source_span_candidates[0].reference, 1);
  assert.equal(cards[1].metadata.source_span_candidates[0].reference, 2);
});
record('codepoint_offsets_nonzero_base_emoji_combining_text', () => {
  const text = '📄 A fictional café note. 🧩 The receipt is missing. e\u0301 is a combining sequence.';
  const chars = Array.from(text);
  const quote = '🧩 The receipt is missing.';
  const start = Array.from(text.split(quote)[0]).length;
  const row = {reference: 1, source_id: 'REC-1', start_offset: start,
    end_offset: start + Array.from(quote).length, status: 'exact',
    source_text_sha256: sha(text), quote_sha256: sha(quote)};
  const changed = clone(payload);
  Object.assign(changed.citations[0], {snippet: text});
  Object.assign(changed.citations[0].source_reference, {start_offset: 47, end_offset: 47 + chars.length});
  changed.output_validation.source_spans = [row];
  const card = sandbox.localAgentCitationsWithVerifierSpans(changed)[0];
  assert.equal(card.metadata.source_span_preview, quote);
  assert.equal(card.metadata.source_span_candidates[0].start_offset, 47 + start);
  assert.match(sandbox.rankedSourceSpanMarkup(card), /🧩 The receipt is missing\./);
});
record('legacy_single_selection_retains_one_highlight', () => {
  const changed = clone(payload);
  changed.output_validation.schema_version = 'evidence_selected_spans_boundary_v1';
  changed.output_validation.source_spans = [changed.output_validation.source_spans[0]];
  const card = sandbox.localAgentCitationsWithVerifierSpans(changed)[0];
  assert.equal(card.metadata.source_span_candidates, undefined);
  assert.match(sandbox.sourcePreviewMarkup(card), /Exact source span/);
  assert.match(sandbox.renderLocalAgentReceipt(changed), /quotations checked — review required/);
});
record('ranked_receipt_never_says_relevance_verified', () => {
  const markup = sandbox.renderLocalAgentReceipt(payload);
  assert.match(markup, /Candidate passages — relevance unknown/);
  assert.match(markup, /A high rank is not confidence or proof/);
  assert.doesNotMatch(markup, /quotations checked — review required/);
});
for (const [name, change] of [
  ['null-span', rows => { rows[1] = null; }],
  ['string-offset', rows => { rows[1].start_offset = '0'; }],
  ['boolean-offset', rows => { rows[1].start_offset = true; }],
  ['negative-offset', rows => { rows[1].start_offset = -1; }],
  ['unsafe-integer', rows => { rows[1].end_offset = Number.MAX_SAFE_INTEGER + 1; }],
  ['past-body', rows => { rows[1].end_offset = 99999; }],
  ['duplicate', rows => { rows[1] = {...rows[0]}; }],
  ['wrong-source', rows => { rows[1].source_id = 'REC-OTHER'; }],
  ['wrong-status', rows => { rows[1].status = 'approved'; }],
  ['malformed-hash', rows => { rows[1].quote_sha256 = 'not-a-hash'; }],
  ['too-many', rows => { rows.push({...rows[0]}); }],
]) record(`reject_candidate_${name}`, () => {
  const card = clone(sandbox.localAgentCitationsWithVerifierSpans(payload)[0]);
  change(card.metadata.source_span_candidates);
  const markup = sandbox.rankedSourceSpanMarkup(card);
  assert.match(markup, /Candidate spans unavailable/);
  assert.doesNotMatch(markup, /<summary>Candidate /);
});
record('markup_is_escaped_as_data', () => {
  const text = '<img src=x onerror="window.fixtureInjection=true"> & <script>alert(1)</script>';
  const changed = clone(payload);
  changed.citations[0].snippet = text;
  changed.output_validation.source_spans = [{reference: 1, source_id: 'REC-1', start_offset: 0,
    end_offset: Array.from(text).length, source_text_sha256: sha(text), quote_sha256: sha(text), status: 'exact'}];
  const markup = sandbox.sourcePreviewMarkup(sandbox.localAgentCitationsWithVerifierSpans(changed)[0]);
  assert.doesNotMatch(markup, /<img|<script/);
  assert.match(markup, /&lt;img/);
});

let context;
record('source_card_keyboard_activation_and_nested_controls', () => {
  const handlers = {};
  let opened = 0, prevented = 0;
  const card = {setAttribute(){}, contains(control){return control.nested === true;}, addEventListener(name,callback){handlers[name]=callback;}, closest(){return null;}};
  sandbox.bindSourceCardActivation(card, () => opened++);
  for (const key of ['Enter',' ']) handlers.keydown({target:card,key,repeat:false,preventDefault(){prevented++;}});
  assert.equal(opened,2); assert.equal(prevented,2);
  handlers.keydown({target:card,key:'Enter',repeat:true});
  handlers.keydown({target:{},key:'Enter',repeat:false});
  handlers.click({target:{closest(){return {nested:true};}}});
  assert.equal(opened,2, 'Nested controls and repeated keys must not reopen a dialog');
  handlers.click({target:card});
  assert.equal(opened,3);
  handlers.click({target:{closest(){return {nested:false};}}});
  assert.equal(opened,4, 'An enclosing collapsible panel is not a nested card control');
});
try {
  if (args.includes('--browser')) {
    const require = createRequire(import.meta.url);
    const {chromium} = require(option('--playwright-module'));
    const scratch = path.join(root, 'dist/qa/compact-ranked-ui');
    const profile = path.join(scratch, 'browser-profile');
    fs.mkdirSync(scratch, {recursive: true});
    context = await chromium.launchPersistentContext(profile, {
      executablePath: option('--browser-executable'), headless: true,
      viewport: {width: 1280, height: 900},
      env: {...process.env, TEMP: scratch, TMP: scratch, APPDATA: scratch, LOCALAPPDATA: scratch},
      args: ['--disable-background-networking', '--disable-component-update', '--disable-extensions',
        '--no-first-run', '--disable-breakpad', '--disable-crash-reporter'],
    });
    const page = context.pages()[0];
    const errors = [], blockedRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', route => { blockedRequests.push(route.request().url()); return route.abort(); });
    await page.setContent('<!doctype html><html lang="en"><meta charset="utf-8"><title>Fictional source-preview component verification</title><body><main><h1>Fictional component verification</h1><p>Not the full desktop application.</p></main></body></html>');
    await page.addStyleTag({content: fs.readFileSync(path.join(root, 'src/maine_family_law_llm/ui/workbench.css'), 'utf8')});
    await page.evaluate(({html, functions, payload}) => {
      const production = new DOMParser().parseFromString(html, 'text/html');
      document.body.append(document.importNode(production.getElementById('source-preview-flyout'), true));
      const script = document.createElement('script');
      script.textContent = functions;
      document.head.append(script);
      const cards = window.localAgentCitationsWithVerifierSpans(payload);
      window.fixtureCards = cards;
      const preview = document.getElementById('source-preview-flyout');
      preview.hidden = false;
      preview.classList.add('is-pinned');
      preview.setAttribute('aria-hidden', 'false');
      document.getElementById('source-preview-title').textContent = cards[0].title;
      document.getElementById('source-preview-body').innerHTML = window.sourcePreviewMarkup(cards[0]);
      // The real receipt belongs to the chat response, not the preview footer.
      // Putting it in the footer would artificially cover the scrollable body.
      document.querySelector('main').insertAdjacentHTML('beforeend', window.renderLocalAgentReceipt(payload));
    }, {html: fs.readFileSync(path.join(root, 'src/maine_family_law_llm/ui/workbench.html'), 'utf8'), functions, payload});
    const summaries = page.locator('#source-preview-body details > summary').filter({hasText: /^Candidate \d/});
    assert.equal(await summaries.count(), 3);
    await summaries.nth(1).focus();
    await page.keyboard.press('Enter');
    assert.equal(await summaries.nth(1).evaluate(node => node.parentElement.open), true);
    assert.match(await summaries.nth(1).evaluate(node => node.parentElement.innerText), /promises to send/);
    await summaries.nth(2).click();
    assert.equal(await summaries.nth(2).evaluate(node => node.parentElement.open), true);
    await page.screenshot({path: path.join(output, `ranked-ui-${runId}-desktop.png`)});
    await page.setViewportSize({width: 720, height: 800});
    await page.evaluate(() => { document.body.style.zoom = '2'; });
    await summaries.nth(2).focus();
    await page.keyboard.press('Enter');
    assert.equal(await summaries.nth(2).evaluate(node => node.parentElement.open), false);
    await summaries.nth(2).scrollIntoViewIfNeeded();
    const bounds = await summaries.nth(2).boundingBox();
    assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= 721
      && bounds.y >= 0 && bounds.y + bounds.height <= 801);
    assert.equal(await summaries.nth(2).evaluate(node => {
      const box = node.getBoundingClientRect();
      const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return hit === node || node.contains(hit);
    }), true, 'Candidate must be visible and not covered by fixed header/footer');
    await page.screenshot({path: path.join(output, `ranked-ui-${runId}-css-zoom.png`)});
    report.browser = {executed: true, component_rendered: true,
      keyboard_details_passed: true, mouse_details_passed: true,
      css_200_percent_zoom_passed: true, browser_os_zoom_tested: false,
      candidate_hit_target_unoccluded: true,
      full_dialog_focus_trap_tested: false, page_errors: errors,
      requests_blocked_by_test_harness: blockedRequests.length,
      network_observation_is_not_os_offline_proof: true,
      screenshots: [`ranked-ui-${runId}-desktop.png`, `ranked-ui-${runId}-css-zoom.png`],
    };
    assert.deepEqual(errors, []);
  }
} catch (error) {
  report.browser.failure = error.message;
} finally {
  if (context) await context.close();
  report.browser.owned_browser_closed = Boolean(context);
  report.passed = report.tests.every(row => row.passed) && !report.browser.failure;
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
}
console.log(JSON.stringify({passed: report.passed, tests: report.tests, browser: report.browser}));
if (!report.passed) process.exitCode = 1;

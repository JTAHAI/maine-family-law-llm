// Local-only, fictional proof. Arguments: loopback base URL and a fixture JSON path.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
const {chromium} = require(path.join(process.env.MFL_PROOF_NODE_MODULES, 'playwright'));
const base = new URL(process.argv[2]);
assert.equal(base.hostname, '127.0.0.1');
assert.equal(base.protocol, 'http:');
const fixture = JSON.parse(await fs.readFile(process.argv[3], 'utf8'));
const runtimeHash = process.argv[4];
const report = {
  checks: [], external_requests: 0, page_errors: [], fictional_only: true,
  frozen: Boolean(runtimeHash), runtime_sha256: runtimeHash || null, installed_msix: false,
};
const browser = await chromium.launch({
  channel: 'msedge', headless: true,
  args: ['--disable-background-networking', '--disable-component-update'],
});
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, serviceWorkers: 'block'});
  await context.route('**/*', route => {
    if (new URL(route.request().url()).origin === base.origin) return route.continue();
    report.external_requests++;
    return route.abort();
  });
  await context.addInitScript(() => localStorage.setItem('mfl-onboarding-complete', 'true'));
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.page_errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  const post = pathEnd => page.waitForResponse(r => r.url().endsWith(pathEnd) && r.request().method() === 'POST');
  await page.goto(base.href);
  assert.equal(await page.locator('body').getAttribute('data-production-ui'), 'workbench');
  await page.locator('#v8-view-menu summary').click();
  await page.locator('[data-v8-view="workspace"]').click();
  await page.locator('[data-workflow-action="draft"]').click();
  await page.locator('.document-workspace-list-item').first().click();
  await page.waitForFunction(() => document.getElementById('document-workspace-status').textContent.includes('Document opened.'));
  await page.locator('[data-document-stage="filing"]').click();
  report.checks.push('production_workbench_navigation');
  const credential = page.locator('#document-filing-credential');
  await credential.fill(fixture.credential);
  await page.locator('#document-review-facts').fill(fixture.fact);
  await page.locator('#document-filing-quotes').fill(fixture.source_id + ' | ' + fixture.quote);
  await page.locator('#document-filing-claims').fill(fixture.claims.map(c => fixture.source_id + ' | ' + c).join('\n'));
  const prepared = post('/review/prepare');
  await page.locator('#document-review-prepare').click();
  assert.equal((await prepared).status(), 200);
  await page.waitForFunction(() => document.querySelectorAll('[data-claim-status]').length >= 2);
  assert.equal(await credential.inputValue(), '');
  assert.match(await page.locator('#document-review-packet').innerText(), /Facts found 1 \/ 1/);
  for (const select of await page.locator('[data-claim-status]').all()) await select.selectOption('accepted');
  await page.locator('#document-review-decision').selectOption('approve_review');
  await page.locator('#document-review-attested').check();
  await page.locator('#document-filing-privacy').check();
  await credential.fill(fixture.credential);
  const committed = post('/review/commit');
  await page.locator('#document-review-commit').click();
  const result = await committed;
  assert.equal(result.status(), 200);
  const review = await result.json();
  assert.equal(review.reviewer.name, 'fixture-reviewer');
  assert.equal(review.filing_gate.filing_ready, true, JSON.stringify(review.filing_gate.blockers));
  await page.waitForFunction(() => document.getElementById('document-review-ledger-status').textContent.includes('recheck before export'));
  report.checks.push('authenticated_review_verified_rows_and_current_recheck_notice');
  await page.locator('#filing-packet-approved').check();
  const built = post('/build');
  await page.locator('#filing-packet-build').click();
  const pack = await (await built).json();
  assert.equal(pack.packet.filing_ready, true, JSON.stringify(pack.packet.blockers));
  const downloadLink = page.locator('[data-filing-credential-required]');
  await downloadLink.click();
  assert.equal(await credential.evaluate(el => document.activeElement === el), true);
  await credential.fill(fixture.credential);
  const downloaded = page.waitForEvent('download');
  await downloadLink.click();
  const download = await downloaded;
  assert.equal(download.suggestedFilename(), 'verified-filing-copy.txt');
  assert.equal(await fs.readFile(await download.path(), 'utf8'), fixture.draft);
  assert.equal(await credential.inputValue(), '');
  report.checks.push('download_requires_reentry_and_returns_exact_bytes');
  assert.deepEqual(report.page_errors, []);
  assert.equal(report.external_requests, 0);
} finally {
  await browser.close();
  process.stdout.write(JSON.stringify(report) + '\n');
}

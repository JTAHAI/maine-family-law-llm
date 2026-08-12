---
layout: default
title: v7.0.0 Release Status
description: Evidence-backed status of the Maine Family Law LLM v7.0.0 source and Windows package candidate.
permalink: /release-status/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Release truth · August 2026</div>
    <h1>v7 source is frozen. Store qualification is still blocked.</h1>
    <p class="lead">The v7.0.0 source and 7.0.0.0 x64 package candidate passed their available source, frozen-runtime, security, privacy, authority, and package audits. Clean isolated AppX installation and WACK were not executable in the available Windows environment.</p>
  </div>
</section>

<div class="content-wrap">
  <div class="callout">
    <h2>Decisions</h2>
    <p><strong>Microsoft Store package:</strong> <code>V7_MSIX_BLOCKED</code></p>
    <p><strong>Enterprise GA:</strong> <code>ENTERPRISE_GA_BLOCKED</code></p>
    <p>No v7 upload, publication, or Microsoft certification is claimed.</p>
  </div>

  <h2>What passed</h2>

  <ul class="check-list">
    <li>Product version 7.0.0 and package version 7.0.0.0 are frozen consistently.</li>
    <li>1,234 tests collected: 1,220 passed, 14 documented Windows skips, zero failures/errors.</li>
    <li>Final focused package/release set: 64 passed.</li>
    <li>16 filing-gate attacks: zero false passes.</li>
    <li>Exact frozen-runtime offline qualification: 18 checks passed, eight fictional records, zero external connections.</li>
    <li>Exact MSIX manifest, sealed payload, path, privacy, dependency, asset, and bundled-engine audits passed.</li>
    <li>External official-authority generation resolved a real statute/pinpoint, rule, current form, and Law Court opinion; the fake citation returned not found.</li>
    <li>Source-derived retrieval smoke used 25 rows and recorded Recall@5/10/20, MRR, and nDCG of 1.0. It is not attorney-reviewed gold.</li>
  </ul>

  <h2>What remains blocked</h2>

  <ul class="check-list">
    <li>The available machine had no Windows Sandbox.</li>
    <li>The current account lacked permission to manage a disposable Hyper-V VM.</li>
    <li>Developer Mode/sideloading was disabled, preventing isolated QA registration.</li>
    <li>WACK was installed but required elevation and therefore was not run.</li>
    <li>The v7 package was not clean-installed, restarted, uninstalled, reinstalled, or offline-qualified as an installed AppX.</li>
    <li>Enterprise GA lacks real attorney-reviewed gold data, attorney sandbox and controlled-pilot evidence, and legal/security/product/operations sign-offs.</li>
  </ul>

  <h2>Current Store link</h2>

  <p>The existing Microsoft Store listing remains available for the earlier 6.0.4.0 build. The v7 candidate must not be inferred from that listing until its qualification blockers are closed and a new submission is accepted by Microsoft.</p>

  <div class="cta-band">
    <div>
      <h2>Review the exact public scope.</h2>
      <p>The repository advertises only the smaller verified v7 feature set; incomplete slices and installed-only claims remain hidden.</p>
    </div>
    <a class="button button--warm" href="{{ '/features/' | relative_url }}">View verified features</a>
  </div>
</div>

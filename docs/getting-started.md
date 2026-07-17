---
layout: default
title: Getting Started
description: First-run instructions for installing Maine Family Law LLM, building a sample or matter corpus, opening Local AI Chat, and protecting private records.
permalink: /getting-started/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">First run</div>
    <h1>Start safely in about ten minutes.</h1>
    <p class="lead">Install the Windows app, build a neutral sample or a workspace from records you select, make that corpus active, and then open the local chat and review tools.</p>
    <div class="hero-actions">
      <a class="button button--primary" href="https://apps.microsoft.com/detail/9NV67WCQW0DM">Get it from Microsoft Store</a>
      <a class="button button--secondary" href="{{ '/privacy/' | relative_url }}">Read the privacy policy</a>
    </div>
  </div>
</section>

<div class="content-wrap">
  <div class="callout callout--teal">
    <h2>Fastest first-run path</h2>
    <ol>
      <li>Install and open <strong>Maine Family Law LLM</strong>.</li>
      <li>Select <strong>Build Neutral Sample Corpus</strong>.</li>
      <li>Wait for the background build to finish.</li>
      <li>Select the new sample in the <strong>Installed corpus library</strong>.</li>
      <li>Select <strong>Use selected corpus</strong>.</li>
      <li>Select <strong>Open Local AI Chat</strong>.</li>
    </ol>
    <p>The neutral sample contains fictional material and is the safest way to learn the workflow before importing private records.</p>
  </div>

  <h2>Create a workspace from your own records</h2>
  <ol>
    <li>Select <strong>Create New Case Corpus</strong>.</li>
    <li>Use <strong>Add folder</strong> or <strong>Add files</strong> to select only the records you intend to process.</li>
    <li>Enter a neutral case name or alias. Avoid placing children’s full names, Social Security numbers, or other sensitive details in the workspace name.</li>
    <li>Review the output location. Prefer a protected local folder or encrypted drive that you control.</li>
    <li>Select <strong>Build corpus</strong> and keep the app open while the background build runs.</li>
    <li>When complete, select the matter in the installed corpus library and choose <strong>Use selected corpus</strong>.</li>
    <li>Open <strong>Local AI Chat</strong>, <strong>Search / Indexes</strong>, or a review package.</li>
  </ol>

  <div class="callout">
    <h3>Use copies when practical</h3>
    <p>Keep original legal records preserved in their existing location. For large or sensitive matters, consider staging copies in a dedicated folder before intake. Review cloud-sync settings before choosing OneDrive, Dropbox, Google Drive, or another synchronized location.</p>
  </div>

  <h2>Open an existing matter</h2>
  <p>Select <strong>Open Existing Case Corpus</strong> and choose the matter workspace. You can also select a known matter in the installed corpus library and choose <strong>Use selected corpus</strong>.</p>

  <h2>Add more evidence later</h2>
  <p>Select <strong>Reopen Intake / Add More Evidence</strong>. Add only the new or changed records you want reviewed. The application tracks hashes and prior intake information so unchanged records can remain distinguishable from newly added material.</p>

  <h2>What Local AI Chat can see</h2>
  <p>Case-specific search and review depend on the currently active corpus. For the clearest first-run experience, activate the neutral sample or your own matter before opening Local AI Chat. General Maine-law research and personal-record review are separate tasks; always check which source scope is active before relying on an answer.</p>

  <h2>Before relying on an output</h2>
  <ul class="check-list">
    <li>Open the cited source card and confirm the source actually supports the statement.</li>
    <li>Check whether the source is official, current, and within Maine jurisdiction.</li>
    <li>Verify quoted language against the source text.</li>
    <li>Review generated timelines, evidence maps, classifications, and drafts for omissions or mistakes.</li>
    <li>Do not treat a generated document as filing-ready without qualified human review.</li>
  </ul>

  <h2>Privacy basics</h2>
  <ul class="check-list">
    <li>The standard application is designed to process selected records locally.</li>
    <li>Do not import records you are not authorized to possess or process.</li>
    <li>Protect your Windows account, matter folders, backups, and removable drives.</li>
    <li>Review every proposed export before sharing it.</li>
    <li>Do not post private matter files, logs, screenshots, or identifying facts in a public GitHub issue.</li>
  </ul>

  <h2>Troubleshooting</h2>
  <p>Use <strong>Repair / Troubleshoot</strong> from the launcher. Local logs are stored under <code>%LOCALAPPDATA%\MaineFamilyLawLLM\logs</code>. Redact private paths and matter information before sharing a log or screenshot.</p>

  <div class="cta-band">
    <div>
      <h2>Install, learn with the neutral sample, then create a protected matter workspace.</h2>
      <p>The sample-first workflow makes the controls familiar before any sensitive family records are added.</p>
    </div>
    <a class="button button--warm" href="https://apps.microsoft.com/detail/9NV67WCQW0DM">Open Microsoft Store</a>
  </div>
</div>

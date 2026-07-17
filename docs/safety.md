---
layout: default
title: Safety and data boundaries
description: Legal-safety, privacy, review, and local-data boundaries for Maine Family Law LLM.
permalink: /safety/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Safety and data boundaries</div>
    <h1>Useful without pretending to be the decision-maker.</h1>
    <p class="lead">The project is built around a simple rule: source correctness, privacy boundaries, and human review outrank fluent output.</p>
  </div>
</section>

<div class="content-wrap">
  <h2>Legal-information boundary</h2>

  <div class="callout">
    <p><strong>Maine Family Law LLM is not a lawyer and does not provide legal advice.</strong> It does not form an attorney-client relationship, decide legal rights, represent a person, guarantee an outcome, or replace review by a qualified professional.</p>
  </div>

  <h2>Review-required by default</h2>

  <p>Generated answers and drafts remain review-required. A document should not be described as filing-ready unless the required authority, citations, quote spans, facts, procedure, forms, record, and human-review checks have actually passed.</p>

  <ul class="check-list">
    <li>Unresolved or fake citations must be flagged.</li>
    <li>Quoted text must be found in the cited source.</li>
    <li>Unsupported legal assertions must be identified.</li>
    <li>Unknown or stale authority must block “current Maine law” language.</li>
    <li>Jurisdiction, procedure, service, deadline, and record problems must be surfaced.</li>
    <li>A failed filing-readiness gate cannot silently become a pass.</li>
  </ul>

  <h2>Local-first data boundary</h2>

  <p>The public source repository is intentionally separated from private and runtime data.</p>

  <div class="grid-2">
    <article class="card">
      <h3>Allowed in the public repository</h3>
      <ul class="plain-list">
        <li>Application source code</li>
        <li>Configuration and schemas</li>
        <li>Public policies and documentation</li>
        <li>Fictional demonstration material</li>
        <li>Tests and non-private evaluation scaffolds</li>
      </ul>
    </article>
    <article class="card">
      <h3>Kept outside the public repository</h3>
      <ul class="plain-list">
        <li>Private matter files and uploads</li>
        <li>Generated legal work product</li>
        <li>Runtime databases and logs</li>
        <li>Corpora, embeddings, and vector stores</li>
        <li>OCR caches and model weights</li>
        <li>External legal-data builds and private eval stores</li>
      </ul>
    </article>
  </div>

  <h2>Files are selected by the user</h2>

  <p>The local application is designed to access files through a user action, such as selecting a file, choosing a folder, opening a matter workspace, or adding more evidence to an existing workspace. Original source files are treated read-only; generated indexes, hashes, summaries, timelines, and exports are created separately.</p>

  <h2>Sensitive family records</h2>

  <p>Family-law files can contain information about children, health, finances, school, counseling, abuse allegations, protection orders, addresses, communications, and sealed or restricted proceedings. Users must protect access to their Windows account, storage locations, backups, removable drives, and exports.</p>

  <h2>External AI and cloud services</h2>

  <p>The core project is designed for local operation. A user or organization may configure an optional external model or service. When that happens, submitted information may leave the device and become subject to the provider’s privacy, retention, confidentiality, and training terms. External services should never be enabled for sensitive information without deliberate review and authorization.</p>

  <h2>Safety overrides software</h2>

  <div class="callout callout--teal">
    <p>Immediate danger, threats, abuse, coercive control, stalking, crisis, or child-safety concerns belong with emergency, crisis, advocacy, medical, or official support first. Call 911 for emergencies, call or text 988 for crisis support, and dial 211 in Maine for service routing.</p>
  </div>

  <h2>FOCaF’s support-first path</h2>

  <p><a href="https://focaf.jtforme.com/">For Our Children &amp; Families</a> emphasizes safety, stable child routines, trusted supports, school and provider coordination, calm communication, private record organization, and official or legal steps when genuinely needed. The LLM workbench is one tool inside that larger child- and family-centered mission.</p>

  <div class="cta-band">
    <div>
      <h2>Read the full privacy policy.</h2>
      <p>The privacy page explains local processing, storage, optional external services, retention, deletion, children’s information, support requests, and Microsoft Store distribution.</p>
    </div>
    <a class="button button--warm" href="{{ '/privacy/' | relative_url }}">Privacy policy</a>
  </div>
</div>

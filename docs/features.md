---
layout: default
title: Verified v7 Features
description: Evidence-backed public scope of the Maine Family Law LLM v7 local-first workbench.
permalink: /features/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Verified v7 public scope</div>
    <h1>Capabilities are public only after the full path works.</h1>
    <p class="lead">A backend class, API route, navigation label, static shell, or focused unit test is not enough. Public v7 features require coherent source and frozen-runtime behavior with matter protection, provenance, review-required status, and tests.</p>
  </div>
</section>

<div class="content-wrap">
  <h2>Records and privacy</h2>

  <div class="grid-2">
    <article class="card">
      <h3>Matter and corpus workspaces</h3>
      <p>Create, select, reopen, and isolate a user-controlled matter/corpus. The active context remains visible and wrong-matter access fails closed.</p>
    </article>
    <article class="card">
      <h3>Mixed-record import</h3>
      <p>Inventory selected PDF, DOCX, text, image, and communication records with hashes, parser state, privacy status, and source identity.</p>
    </article>
    <article class="card">
      <h3>OCR searchable derivatives</h3>
      <p>Run local OCR against image-only records, preserve the original, and create a distinct searchable derivative and receipt.</p>
    </article>
    <article class="card">
      <h3>Document intelligence</h3>
      <p>Use deterministic parsing and packaged local engines for structure and privacy review without a silent runtime download.</p>
    </article>
    <article class="card">
      <h3>Privacy and redaction</h3>
      <p>Review sensitive-data findings before producing a separate redacted derivative. Originals remain immutable.</p>
    </article>
    <article class="card">
      <h3>Duplicate and changed-copy review</h3>
      <p>Distinguish exact duplicates from changed copies using hashes and bounded comparisons rather than filename assumptions.</p>
    </article>
  </div>

  <h2>Research and exact sources</h2>

  <div class="grid-2">
    <article class="card">
      <h3>Ask Maine Family Law</h3>
      <p>Research against an admitted external official-authority generation. When authority is unavailable or stale, current-law wording fails closed.</p>
    </article>
    <article class="card">
      <h3>Source cards and exact preview</h3>
      <p>Open the official source, freshness and jurisdiction metadata, citation, and exact supporting span instead of relying on a summary alone.</p>
    </article>
    <article class="card">
      <h3>Citation and pinpoint resolution</h3>
      <p>Resolve real Maine statutes, subdivisions, court rules, current forms, and Law Court opinions. Fake citations return not found.</p>
    </article>
    <article class="card">
      <h3>Quote and claim verification</h3>
      <p>Expose exact, normalized, fuzzy-review-required, and not-found quote states plus supported, partial, unsupported, contradicted, stale, and wrong-jurisdiction claim states.</p>
    </article>
  </div>

  <h2>Drafting and review</h2>

  <div class="grid-2">
    <article class="card">
      <h3>Review-required drafts</h3>
      <p>Create working drafts from selected authority and evidence while keeping unsupported claims, citations, privacy, and human-review blockers visible.</p>
    </article>
    <article class="card">
      <h3>Immutable revision history</h3>
      <p>Preserve the original and each committed revision. Proposed edits remain distinct until accepted or rejected.</p>
    </article>
    <article class="card">
      <h3>Revision comparison</h3>
      <p>Inspect additions and removals before accepting a working revision.</p>
    </article>
    <article class="card">
      <h3>Review packets and receipts</h3>
      <p>Generate packets that retain review-required status, exact blockers, artifact receipts, and restart-safe state.</p>
    </article>
  </div>

  <h2>Fail-closed safeguards</h2>

  <ul class="check-list">
    <li>Local-only behavior is the default.</li>
    <li>Official authority, private evidence, and model analysis remain separate lanes.</li>
    <li>Private matter records are not legal authority.</li>
    <li>A verifier error cannot produce a green or filing-ready status.</li>
    <li>Unsupported claims, fake citations, stale authority, mismatched quotes, incomplete privacy review, and missing human review remain blockers.</li>
    <li>Backup and restore use synthetic acceptance fixtures; private matter data stays outside the repository.</li>
  </ul>

  <h2>Hidden or deferred</h2>

  <div class="callout">
    <p><strong>Not advertised in v7:</strong> slices 21–44, timeline correction, claim-disposition, current guided forms, installed tracked-DOCX, whole-matter command center/snapshots, and missing-attachment coverage. Their code may remain for development and non-destructive data compatibility, but that is not a production feature claim.</p>
  </div>

  <h2>Package qualification boundary</h2>

  <p>The v7 source, frozen runtime, authority product, filing gate, privacy checks, and exact MSIX package audits passed. Clean isolated AppX installation and WACK did not run in the available environment, so v7 remains blocked from an upload-ready claim.</p>

  <div class="cta-band">
    <div>
      <h2>Inspect the release evidence boundary.</h2>
      <p>See what passed, what was not executed, and what must happen before v7 can move to Partner Center.</p>
    </div>
    <a class="button button--warm" href="{{ '/release-status/' | relative_url }}">Read v7 status</a>
  </div>
</div>

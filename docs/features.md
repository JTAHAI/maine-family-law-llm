---
layout: default
title: What it does
description: Capabilities and workflow of the Maine Family Law LLM local-first legal-information workbench.
permalink: /features/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">What it does</div>
    <h1>A structured workbench for Maine family-law records.</h1>
    <p class="lead">The project combines local document organization, Maine-specific issue spotting, source retrieval, citation review, evidence mapping, and review-required drafting. It is designed to show its work rather than hide behind a polished answer.</p>
  </div>
</section>

<div class="content-wrap">
  <h2>Core user workflows</h2>

  <div class="grid-2">
    <article class="card">
      <h3>Ask a Maine family-law question</h3>
      <p>Searches available authority and returns a structured answer with source cards, source scope, freshness information, and review warnings.</p>
    </article>
    <article class="card">
      <h3>Upload and review documents</h3>
      <p>Identifies likely issues, procedural posture, missing information, privacy concerns, and red flags from the files the user selects.</p>
    </article>
    <article class="card">
      <h3>Build a timeline</h3>
      <p>Extracts events and dates into a reviewable chronology that links back to the original document and text span.</p>
    </article>
    <article class="card">
      <h3>Map facts to evidence</h3>
      <p>Connects a factual statement to supporting or conflicting records, source locations, dates, and confidence notes.</p>
    </article>
    <article class="card">
      <h3>Review citations and quotes</h3>
      <p>Parses legal citations, checks whether sources exist, verifies quote spans, and reports missing or unresolved support.</p>
    </article>
    <article class="card">
      <h3>Create working drafts</h3>
      <p>Produces review-required motions, affidavits, letters, objections, proposed findings, checklists, and plain-language explainers.</p>
    </article>
  </div>

  <h2>Designed outputs</h2>

  <ul class="check-list">
    <li>Issue tree and procedural-posture summary</li>
    <li>Authority matrix with source cards</li>
    <li>Fact-to-evidence map and case timeline</li>
    <li>Red-flag report and missing-record checklist</li>
    <li>Citation and quote-span verification tables</li>
    <li>Draft packet and unsupported-claim report</li>
    <li>Filing-readiness blocker report</li>
    <li>Human-review checklist and plain-language client explainer</li>
  </ul>

  <h2>Maine-specific issue coverage</h2>

  <p>The project ontology includes topics such as divorce, parental rights and responsibilities, primary residence, contact schedules, child support, parentage, post-judgment motions, enforcement, contempt, protection from abuse, grandparent visitation, guardianship, GAL issues, UCCJEA jurisdiction, Rule 52 findings, best-interest factor gaps, appeal preservation, transcript problems, Maine eCourts access, and third-party delegation concerns.</p>

  <h2>Authority before generation</h2>

  <div class="callout callout--teal">
    <p><strong>The generator does not decide whether legal authority is valid.</strong> Authority status comes from the source registry, citation resolver, freshness checks, quote verifier, claim-support checks, and human review.</p>
  </div>

  <h2>Current release truth</h2>

  <p>The public repository already supports local Windows launch, corpus-building workflows, source-backed chat surfaces, evidence-oriented work products, and release-control evidence. The project remains under active development. Microsoft Store packaging, real external official-source builds, attorney-reviewed evaluation packs, security hardening, and production release gates must be completed and measured before any claim of general availability.</p>

  <div class="cta-band">
    <div>
      <h2>Inspect the implementation.</h2>
      <p>The public repository contains code, policies, tests, release evidence, and the roadmap toward enterprise-grade legal-source verification.</p>
    </div>
    <a class="button button--warm" href="https://github.com/JTAHAI/maine-family-law-llm">Open GitHub</a>
  </div>
</div>

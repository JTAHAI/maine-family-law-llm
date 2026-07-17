---
layout: default
title: Fork your state
 description: A practical checklist for adapting Maine Family Law LLM into a properly verified state-specific legal-information workbench.
permalink: /fork-your-state/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Build one for your state</div>
    <h1>Fork the code. Replace and verify the law.</h1>
    <p class="lead">This project is intentionally open source so parents, advocates, legal-aid organizations, attorneys, researchers, and technologists can build properly validated editions for other states.</p>
  </div>
</section>

<div class="content-wrap">
  <div class="callout">
    <p><strong>Changing the state name or branding is not enough.</strong> Maine statutes, court rules, forms, case law, citation formats, procedure, deadlines, privacy requirements, and legal-review expectations must not be presented as authority in another state.</p>
  </div>

  <h2>State-port checklist</h2>

  <div class="grid-2">
    <article class="card">
      <h3>Official legal sources</h3>
      <ul class="plain-list">
        <li>State legislature and official statutes</li>
        <li>Judicial-branch rules and standing orders</li>
        <li>Official family-court forms and packets</li>
        <li>Appellate and supreme-court opinions</li>
        <li>Relevant administrative and federal authority</li>
      </ul>
    </article>
    <article class="card">
      <h3>Source integrity</h3>
      <ul class="plain-list">
        <li>Canonical source IDs and source classes</li>
        <li>Retrieval timestamps and hashes</li>
        <li>Parser status and exact source spans</li>
        <li>Fresh, stale, unknown, and superseded status</li>
        <li>Official-source priority over mirrors and summaries</li>
      </ul>
    </article>
    <article class="card">
      <h3>State legal intelligence</h3>
      <ul class="plain-list">
        <li>State-specific issue ontology</li>
        <li>Procedural-posture labels</li>
        <li>Authority-ranking policy</li>
        <li>Citation resolver and quote verifier</li>
        <li>State-specific red flags and filing gates</li>
      </ul>
    </article>
    <article class="card">
      <h3>Human-reviewed evaluation</h3>
      <ul class="plain-list">
        <li>Retrieval gold data</li>
        <li>Citation-validity and quote-span gold data</li>
        <li>False-premise and hallucination cases</li>
        <li>Forms-freshness checks</li>
        <li>Attorney-reviewed drafting and filing-gate tests</li>
      </ul>
    </article>
  </div>

  <h2>Privacy and professional boundaries</h2>

  <ul class="check-list">
    <li>Research the state’s confidentiality, court-record, juvenile-record, and privacy rules.</li>
    <li>Define what the application can access, store, transmit, retain, and delete.</li>
    <li>Keep private matter data out of the public repository and shared training by default.</li>
    <li>Address unauthorized-practice-of-law boundaries and the intended user audience.</li>
    <li>Require qualified human review for legal conclusions, drafts, and filing decisions.</li>
    <li>Publish a product-specific privacy policy and truthful Store listing.</li>
  </ul>

  <h2>Recommended porting order</h2>

  <ol>
    <li><strong>Fork the repository</strong> and document the new project’s jurisdiction and governance.</li>
    <li><strong>Remove Maine authority claims</strong> from user-facing surfaces before adding the new state’s law.</li>
    <li><strong>Build the official-source registry</strong> with hashes, freshness, parser audits, and authority classes.</li>
    <li><strong>Implement exact citation lookup</strong> before relying on semantic retrieval or drafting.</li>
    <li><strong>Create rule-based labels and red flags</strong> before training classifiers.</li>
    <li><strong>Build attorney-reviewed gold data</strong> and measure retrieval, citation, quote, hallucination, and gate performance.</li>
    <li><strong>Add drafting last</strong>, after retrieval and verification are working.</li>
    <li><strong>Pilot with qualified reviewers</strong> before real-matter or public reliance.</li>
  </ol>

  <h2>How to begin</h2>

  <div class="cta-band">
    <div>
      <h2>Start from the public repository.</h2>
      <p>Fork the code, open an issue describing your state edition, and preserve the project’s source-first, review-required, private-data-outside-the-repo architecture.</p>
    </div>
    <a class="button button--warm" href="https://github.com/JTAHAI/maine-family-law-llm/fork">Fork on GitHub</a>
  </div>

  <p class="microcopy">A fork is operated by its own maintainer. TAHAI and the Maine project do not certify the legal accuracy, privacy practices, or safety of third-party forks.</p>
</div>

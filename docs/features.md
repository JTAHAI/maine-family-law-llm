---
layout: default
title: v7 Feature Catalog
description: Complete verified and development-preview capability catalog for the Maine Family Law LLM v7 local-first workbench.
permalink: /features/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Current source release · v7.0.0</div>
    <h1>The complete v7 capability catalog.</h1>
    <p class="lead">The v7 source contains 16 end-to-end verified core workflows and 24 recently added specialized workbenches. Readiness labels distinguish proven public workflows from source-level development previews.</p>
  </div>
</section>

<div class="content-wrap">
  <div class="tier-legend" aria-label="Feature readiness legend">
    <span class="tier tier--verified">Verified end to end</span>
    <span>Production path and tests are proven.</span>
    <span class="tier tier--preview">Development preview</span>
    <span>Implemented in source; installed-package acceptance is pending.</span>
  </div>

  <h2>Verified end-to-end core</h2>

  <p>The following 16 workflows are the accepted public v7 scope.</p>

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

  <h2>Recently added specialized workbenches</h2>

  <p>These source-level vertical slices extend the workbench across the complete family-law matter lifecycle. Each remains a <strong>development preview</strong> until its canonical UI journey is accepted in the frozen executable and installed package.</p>

  <div class="feature-table-wrap">
    <table class="feature-table">
      <thead>
        <tr><th>Slice</th><th>Specialized workbench</th><th>Readiness</th></tr>
      </thead>
      <tbody>
        <tr><td>21</td><td>Matter intake, procedural posture, and issue tree</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>22</td><td>Operative-order resolver and supersession graph</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>23</td><td>Service, notice, deadline, and hearing calendar</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>24</td><td>Docket and MRECS record reconciliation</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>25</td><td>Discovery and disclosure workbench</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>26</td><td>Exhibit binder, Bates labeling, and chain of custody</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>27</td><td>Witness testimony and statement comparison</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>28</td><td>Hearing preparation and courtroom review pack</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>29</td><td>Appellate preservation and record-citation workbench</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>30</td><td>UCCJEA interstate jurisdiction map</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>31</td><td>ICWA tribal inquiry and notice review</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>32</td><td>Guardianship, adoption, and probate pathways</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>33</td><td>Protection-from-abuse and safety-resource workbench</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>34</td><td>Parenting-plan schedule and logistics engine</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>35</td><td>Mediation, negotiation, and proposal matrix</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>36</td><td>Property, debt, and valuation workbench</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>37</td><td>Modification and change-in-circumstances matrix</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>38</td><td>FOAA public-records request manager</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>39</td><td>Court-filing package and MRECS readiness validator</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>40</td><td>Digital image, screenshot, and photo evidence review</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>41</td><td>Email header, attachment, and export integrity</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>42</td><td>Secure reviewer handoff and portable matter bundle</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>43</td><td>Plain-language, accessibility, and translation workbench</td><td><span class="tier tier--preview">Development preview</span></td></tr>
        <tr><td>44</td><td>Maine family-resource navigator and warm handoff</td><td><span class="tier tier--preview">Development preview</span></td></tr>
      </tbody>
    </table>
  </div>

  <h2>Additional source capabilities under qualification</h2>

  <div class="grid-2">
    <article class="card"><h3>Timeline and event correction</h3><p>Build event chronology, preserve corrections, and inspect append-only history.</p></article>
    <article class="card"><h3>Claim disposition</h3><p>Review support, contradiction, qualification, missing context, and unsupported assertions.</p></article>
    <article class="card"><h3>Guided current forms</h3><p>Run form sessions with freshness, required-field, and stale-form safeguards.</p></article>
    <article class="card"><h3>Tracked DOCX review</h3><p>Compare working revisions and, where supported, produce tracked Word review artifacts.</p></article>
    <article class="card"><h3>Whole-matter command center</h3><p>Aggregate review blockers, coverage, status, and snapshot controls across a matter.</p></article>
    <article class="card"><h3>Record coverage and missing attachments</h3><p>Expose evidence gaps, missing records, missing attachments, and source-bound coverage.</p></article>
  </div>

  <h2>Availability and qualification</h2>

  <p>The current GitHub source is v7.0.0, and v7 is available as a free download from the Microsoft Store. Development-preview labels remain on specialized workbenches whose individual frozen-app and installed-package acceptance records are incomplete; Store availability does not silently change a feature’s evidence tier.</p>

  <div class="cta-band">
    <div>
      <h2>Inspect the release evidence boundary.</h2>
      <p>See the current Store availability, source evidence, safety boundary, and separate enterprise-validation status.</p>
    </div>
    <a class="button button--warm" href="https://apps.microsoft.com/detail/9NV67WCQW0DM">Download v7</a>
  </div>
</div>

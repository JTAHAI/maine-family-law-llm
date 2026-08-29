---
layout: default
title: v8 Feature Catalog
description: Complete verified capability catalog for the Maine Family Law LLM v8 local-first workbench.
permalink: /features/
---

<section class="page-hero">
  <div class="shell">
    <div class="eyebrow">Current source release · v8.0.0</div>
    <h1>The complete v8 capability catalog.</h1>
    <p class="lead">The v8 source contains 16 verified core workflows, 24 verified specialized workbenches, 10 Matter Productivity Studio capabilities, and 20 verified Add-on Studio verticals. Each public capability has a production UI, protected local API, source drill-down, review boundary, and focused tests.</p>
  </div>
</section>

<div class="content-wrap">
  <div class="tier-legend" aria-label="Feature readiness legend">
    <span class="tier tier--verified">Verified end to end</span>
    <span>Production path and tests are proven.</span>
    <span>70 public workflows currently meet this evidence tier in the current source.</span>
  </div>

  <h2>Verified end-to-end core</h2>

  <p>The following 16 workflows are the accepted core scope retained in v8.</p>

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

  <h2>Verified specialized workbenches</h2>

  <p>These vertical slices extend the workbench across the family-law matter lifecycle. Each passed meaningful fictional-matter actions through its canonical local API and shipped desktop UI, exact-source inspection, review-required status, focused tests, and full-tier frozen-runtime reachability.</p>

  <div class="feature-table-wrap">
    <table class="feature-table">
      <thead>
        <tr><th>Slice</th><th>Specialized workbench</th><th>Readiness</th></tr>
      </thead>
      <tbody>
        <tr><td>21</td><td>Matter intake, procedural posture, and issue tree</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>22</td><td>Operative-order resolver and supersession graph</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>23</td><td>Service, notice, deadline, and hearing calendar</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>24</td><td>Docket and MRECS record reconciliation</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>25</td><td>Discovery and disclosure workbench</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>26</td><td>Exhibit binder, Bates labeling, and chain of custody</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>27</td><td>Witness testimony and statement comparison</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>28</td><td>Hearing preparation and courtroom review pack</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>29</td><td>Appellate preservation and record-citation workbench</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>30</td><td>UCCJEA interstate jurisdiction map</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>31</td><td>ICWA tribal inquiry and notice review</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>32</td><td>Guardianship, adoption, and probate pathways</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>33</td><td>Protection-from-abuse and safety-resource workbench</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>34</td><td>Parenting-plan schedule and logistics engine</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>35</td><td>Mediation, negotiation, and proposal matrix</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>36</td><td>Property, debt, and valuation workbench</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>37</td><td>Modification and change-in-circumstances matrix</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>38</td><td>FOAA public-records request manager</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>39</td><td>Court-filing package and MRECS readiness validator</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>40</td><td>Digital image, screenshot, and photo evidence review</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>41</td><td>Email header, attachment, and export integrity</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>42</td><td>Secure reviewer handoff and portable matter bundle</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>43</td><td>Plain-language, accessibility, and translation workbench</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>44</td><td>Maine family-resource navigator and warm handoff</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
      </tbody>
    </table>
  </div>

  <h2>Verified Matter Productivity Studio</h2>

  <div class="table-wrap">
    <table>
      <thead><tr><th>ID</th><th>Capability</th><th>Safety boundary</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>45</td><td>Smart Matter Inbox</td><td>Explicit manifest; no silent watch or import</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>46</td><td>Saved workflow recipes</td><td>Allow-listed steps and explicit confirmation</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>47</td><td>Local audio/video transcription</td><td>Source-hash bound; no silent engine download</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>48</td><td>Calendar interoperability</td><td>Local ICS export; no calendar-account write</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>49</td><td>Local model hardware optimizer</td><td>Safe limits; no automatic model download</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>50</td><td>Research notebook and source pinboard</td><td>Exact span, hash, locator, and freshness</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>51</td><td>Redaction Studio</td><td>Immutable original; pending privacy review</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>52</td><td>Matter health and next actions</td><td>Corrective queue; no legal-priority decision</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>53</td><td>Courtroom presentation mode</td><td>Source-bound cards; private notes hidden</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>54</td><td>Encrypted automatic backup</td><td>Verified container; isolated recovery restore</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
      </tbody>
    </table>
  </div>

  <h2>Verified Add-on Studio</h2>

  <p>Twenty additional local-first tools now run through the active matter, canonical API, production desktop UI, review-required receipts, immutable review decisions, and exact-result and artifact drill-down. Native transcription uses a bundled, hash-pinned whisper.cpp runtime and performs no runtime download.</p>

  <div class="feature-table-wrap">
    <table class="feature-table">
      <thead><tr><th>ID</th><th>Add-on</th><th>Safety boundary</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>55</td><td>Native Whisper transcription</td><td>Bundled hash-pinned local engine; no runtime download or network</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>56</td><td>OCR correction studio</td><td>Immutable original and append-only correction receipt</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>57</td><td>Universal communications importer</td><td>Explicit exported messages; no account connection</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>58</td><td>Evidence relationship graph</td><td>Source-bound reviewer assertions, never findings</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>59</td><td>Local model manager</td><td>No automatic download, selection, or removal</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>60</td><td>Court-form autofill</td><td>Current-form and required-field gates; never filing-ready alone</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>61</td><td>Advanced table extraction</td><td>Cell-level source locators retained</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>62</td><td>Financial-document intelligence</td><td>Review flags only; no valuation or ownership conclusion</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>63</td><td>Semantic order comparison</td><td>Exposes wording changes; does not decide the operative order</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>64</td><td>Authority update center</td><td>Audits candidates without network update or activation</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>65</td><td>Guided legal-research builder</td><td>Maine-first plan; no unverified current-law claim</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>66</td><td>Evidence annotation studio</td><td>Exact-span notes; original record unchanged</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>67</td><td>Local automation scheduler</td><td>Allow-listed tasks while the app is active</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>68</td><td>Secure reviewer collaboration</td><td>Encrypted bundle; no send or live-matter sharing</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>69</td><td>Matter template library</td><td>Selected fields only; no unrelated matter copy</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>70</td><td>Conflict and entity resolver</td><td>Candidates only; no automatic identity merge</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>71</td><td>Desktop notification center</td><td>Local corrective notices; no external service</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>72</td><td>Courtroom bundle exporter</td><td>Offline source cards with private notes excluded</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>73</td><td>Voice drafting and commands</td><td>Review-required working draft; never filing-ready alone</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
        <tr><td>74</td><td>Extension SDK permission center</td><td>Signed allow-list, default disabled, no arbitrary network</td><td><span class="tier tier--verified">Verified end to end</span></td></tr>
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

  <p>The current GitHub source is v8.0.0 and exposes 70 accepted workflows: 16 verified core workflows, 24 specialized workbenches, 10 Matter Productivity Studio capabilities, and 20 verified Add-on Studio verticals. The full-tier v8.0.0.0 candidate passed frozen-runtime smoke and package-boundary audits. Microsoft upload, signing, and distribution remain separate steps.</p>

  <p>Fast Interchange support is an optional local-model-pack boundary, not a bundled legal-model claim. The current candidate includes no legal weights or adapters. Future packs must be explicitly installed, hash-verified, rights-cleared, admitted, and review-required before they can be activated.</p>

  <div class="cta-band">
    <div>
      <h2>Inspect the release evidence boundary.</h2>
      <p>See the current Store availability, source evidence, safety boundary, and separate enterprise-validation status.</p>
    </div>
    <a class="button button--warm" href="https://apps.microsoft.com/detail/9NV67WCQW0DM">Download v7</a>
  </div>
</div>

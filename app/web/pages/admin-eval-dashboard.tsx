export default function AdminEvalDashboard() {
  return (
    <main data-review-status="review_required" data-attorney-eval-lab="visible" data-eval-export-bundle="visible" aria-labelledby="eval-lab-title">
      <header>
        <h1 id="eval-lab-title">Evaluation &amp; Review Lab</h1>
        <p>Dataset review, recusal, adjudication, regression runs, release comparison, and failure triage for attorney-reviewed gold evidence.</p>
      </header>

      <nav aria-label="Evaluation lab sections">
        <ul>
          <li><a href="#overview">Overview</a></li>
          <li><a href="#review-queue">Review Queue</a></li>
          <li><a href="#second-review">Second Review</a></li>
          <li><a href="#recusal-ledger">Recusal Ledger</a></li>
          <li><a href="#adjudication">Adjudication</a></li>
          <li><a href="#supersession">Supersession</a></li>
          <li><a href="#evaluation-runs">Evaluation Runs</a></li>
          <li><a href="#metrics-dashboard">Metrics Dashboard</a></li>
          <li><a href="#exports">Exports</a></li>
          <li><a href="#failure-triage">Failure Triage</a></li>
        </ul>
      </nav>

      <section id="overview" aria-labelledby="overview-title" data-source-card="visible" data-honest-participation="visible">
        <h2 id="overview-title">Overview</h2>
        <ul>
          <li>Dataset counts, reviewed and unreviewed rows, conflicts, promoted gold, stale data, and release blockers stay visible.</li>
          <li>Every accepted row keeps source IDs, source hashes, exact spans, reviewer metadata, and decision history.</li>
          <li>Seed, generated, synthetic, and private-training evidence remain smoke-test material and cannot satisfy production thresholds.</li>
          <li>Honest attorney participation reporting keeps the lab from claiming bar-reviewed evidence where the local audit only observed review-role usage.</li>
        </ul>
      </section>

      <section id="review-queue" aria-labelledby="review-queue-title" data-claim-drilldown="answer-to-claim">
        <h2 id="review-queue-title">Review Queue</h2>
        <ul>
          <li>Source preview, exact span, candidate label, structured response, confidence, rationale, recusal, and save-and-continue flow.</li>
          <li>Generated candidates are marked needs_attorney_review and never promoted automatically.</li>
          <li>Queue items preserve assignment history and can be filtered by source class, issue, posture, or dataset type.</li>
        </ul>
      </section>

      <section id="second-review" aria-labelledby="second-review-title" data-citation-drilldown="claim-to-citation">
        <h2 id="second-review-title">Second Review</h2>
        <ul>
          <li>Blinded mode hides the first reviewer&apos;s conclusion until the second review is recorded.</li>
          <li>Independent review status and disagreement indicators stay attached to the row history.</li>
        </ul>
      </section>

      <section id="recusal-ledger" aria-labelledby="recusal-ledger-title" data-recusal-ledger="visible">
        <h2 id="recusal-ledger-title">Recusal Ledger</h2>
        <ul>
          <li>Conflicts of interest, reviewer recusal reasons, and comments are recorded as append-only events.</li>
          <li>Recusal events remain visible in row history and in the exported review bundle.</li>
        </ul>
      </section>

      <section id="adjudication" aria-labelledby="adjudication-title" data-source-text-drilldown="citation-to-source-text">
        <h2 id="adjudication-title">Adjudication</h2>
        <ul>
          <li>Side-by-side review history, exact source span, resolution controls, and immutable decision receipts are preserved.</li>
          <li>Conflict resolution never deletes prior history and can supersede a row with a resolved version.</li>
        </ul>
      </section>

      <section id="supersession" aria-labelledby="supersession-title" data-supersession-ledger="visible">
        <h2 id="supersession-title">Supersession</h2>
        <ul>
          <li>Corrected rows are appended as new gold evidence instead of mutating or deleting the earlier row.</li>
          <li>Superseded rows keep lineage, rationale, and fixed-in-version metadata for later audit.</li>
        </ul>
      </section>

      <section id="evaluation-runs" aria-labelledby="evaluation-runs-title" data-verifier-result-drilldown="source-text-to-verifier-result">
        <h2 id="evaluation-runs-title">Evaluation Runs</h2>
        <ul>
          <li>Choose an eligible dataset and admitted model or index, start a run, monitor progress, and cancel when needed.</li>
          <li>Run records include dataset hash, config hash, sample size, freshness status, and attorney-reviewed eligibility basis.</li>
        </ul>
      </section>

      <section id="metrics-dashboard" aria-labelledby="metrics-dashboard-title">
        <h2 id="metrics-dashboard-title">Metrics Dashboard</h2>
        <ul>
          <li>Metric value, threshold, sample size, attorney-reviewed count, evidence eligibility, and comparison with the accepted release are shown together.</li>
          <li>Metrics explain when values could not be computed because the evidence was undersized, synthetic, stale, or unreviewed.</li>
        </ul>
      </section>

      <section id="exports" aria-labelledby="exports-title" data-eval-exports="visible">
        <h2 id="exports-title">Exports</h2>
        <ul>
          <li>JSONL review bundle, dataset manifest, metrics JSON, failure clusters, release comparison, and attorney-review evidence summary are written under the external eval root.</li>
          <li>Export files stay outside the repository and preserve exact lineage to the accepted dataset hashes.</li>
        </ul>
      </section>

      <section id="failure-triage" aria-labelledby="failure-triage-title" data-blocked-export-explanation="visible">
        <h2 id="failure-triage-title">Failure Triage</h2>
        <ul>
          <li>Failure clusters, row drill-down, source links, regression status, owner status, fixed-in version, and retest actions remain auditable.</li>
          <li>Blocked exports explain every missing gate: authority, citation, quote, claim, fact, procedure, form, or human review.</li>
        </ul>
      </section>
    </main>
  );
}

export default function CommandCenter() {
  return (
    <main className="command-center-shell" data-review-status="review_required" data-command-center="visible">
      <header className="command-center-hero">
        <p className="command-center-kicker">Whole-matter review command center</p>
        <h1>Full-Record Coverage and Exportable Evidence Packet</h1>
        <p>
          Freeze the matter, review every indexed record, and export a receipt-backed packet without collapsing
          metadata, redaction, and review history into a single opaque export.
        </p>
      </header>
      <section aria-label="Coverage" data-full-record-coverage="visible" data-stale-snapshot-warning="visible">
        <h2>Coverage</h2>
        <ul>
          <li>Every indexed record stays visible in the frozen snapshot.</li>
          <li>Included and excluded record IDs remain explicit in the receipt.</li>
          <li>Stale-snapshot warnings stay visible when the current record set changes.</li>
        </ul>
      </section>
      <section aria-label="Export" data-exportable-packet="visible" data-no-binary-originals="true">
        <h2>Exportable packet</h2>
        <ul>
          <li>Metadata-first packet exports stay review-required.</li>
          <li>Receipt and packet hashes are preserved for comparison and audit.</li>
          <li>Original binary sources are not embedded by default.</li>
        </ul>
      </section>
      <section aria-label="Review history" data-review-history="visible" data-packet-compare="visible">
        <h2>Review history and compare</h2>
        <p>Packet review history, compare, and snapshot refresh actions remain separate so the audit trail stays clear.</p>
      </section>
    </main>
  );
}

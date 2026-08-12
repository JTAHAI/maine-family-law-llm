import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function ReviewHistory() {
  return (
    <EvidenceWorkbench
      activeTab="/review-history"
      kicker="Evidence work product"
      title="Review History"
      description="Keep append-only correction and reviewer history visible across the full evidence workflow."
    >
      <section aria-label="Review history" className="evidence-workbench-card">
        <h2>Append-only history</h2>
        <ul>
          <li data-append-only-history="visible">Original values and corrected values both remain visible in history.</li>
          <li data-review-handoff="visible">Exported review handoffs carry the selected scope and export receipt hash.</li>
          <li data-generated-at="visible">Generated timestamps and matter-safe IDs stay attached to every review artifact.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

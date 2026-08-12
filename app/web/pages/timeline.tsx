import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function Timeline() {
  return (
    <EvidenceWorkbench
      activeTab="/timeline"
      kicker="Evidence work product"
      title="Evidence Timeline"
      description="Build a chronology from selected records, preserve undated material, and drill every event back to the exact source page or block."
    >
      <section aria-label="Timeline controls" className="evidence-workbench-card" data-review-status="review_required">
        <h2>Timeline controls</h2>
        <ul>
          <li data-date-source-display="visible">Date source, date type, and confidence basis stay visible for each event.</li>
          <li data-date-type-filter="available">Date type, issue, participant, and source-type filters are available in the review API.</li>
          <li data-undated-lane="visible">Undated events stay in a separate lane instead of being hidden.</li>
          <li data-source-drilldown="available">Every event links back to the exact record page and block.</li>
        </ul>
      </section>
      <section aria-label="Timeline summary" className="evidence-workbench-card">
        <h2>Timeline summary</h2>
        <p>Records by date, empty date ranges, duplicate concentration, and parser/OCR failures all remain review-visible.</p>
      </section>
    </EvidenceWorkbench>
  );
}

import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function Coverage() {
  return (
    <EvidenceWorkbench
      activeTab="/coverage"
      kicker="Evidence work product"
      title="Record Coverage"
      description="See which dates, source types, and record groups are represented, excluded, or still need review."
    >
      <section aria-label="Coverage summary" className="evidence-workbench-card">
        <h2>Coverage summary</h2>
        <ul>
          <li data-date-coverage="visible">Date coverage and empty date ranges are shown together.</li>
          <li data-source-type-coverage="visible">Source-type coverage includes duplicates, parser failures, and OCR failures.</li>
          <li data-excluded-records="visible">Records excluded from the current scope stay visible.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

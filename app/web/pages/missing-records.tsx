import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function MissingRecords() {
  return (
    <EvidenceWorkbench
      activeTab="/missing-records"
      kicker="Evidence work product"
      title="Missing Records"
      description="Organize user-created checklists, matter templates, and heuristic suggestions without treating any expected record as a legal presumption."
    >
      <section aria-label="Missing record checklist" className="evidence-workbench-card">
        <h2>Checklist basis</h2>
        <ul>
          <li data-checklist-origin="visible">User, template, and heuristic origins stay labeled separately.</li>
          <li data-basis-for-expectation="visible">Every item explains why it may matter and what search was performed.</li>
          <li data-review-required="true">Missing-record suggestions remain review-required aids, not conclusions.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

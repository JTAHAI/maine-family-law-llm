import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function Contradictions() {
  return (
    <EvidenceWorkbench
      activeTab="/contradictions"
      kicker="Evidence work product"
      title="Contradictions"
      description="Compare conflicting dates and statements while keeping the underlying source text and classification visible."
    >
      <section aria-label="Contradiction review" className="evidence-workbench-card">
        <h2>Review lanes</h2>
        <ul>
          <li data-conflict-marker="visible">Conflicting dates remain visible as separate evidence cards.</li>
          <li data-authenticity-caveat="visible">Authenticity and reliability caveats stay separate from contradiction cards.</li>
          <li data-copy-comparison="visible">Compare copies and surrounding context remain available for review.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function Evidence() {
  return (
    <EvidenceWorkbench
      activeTab="/evidence"
      kicker="Evidence work product"
      title="Claims Review"
      description="Enter a claim, promote a record sentence, or review a draft line against selected records without collapsing allegations into findings."
    >
      <section aria-label="Claim support matrix" className="evidence-workbench-card" data-review-status="review_required">
        <h2>Support matrix</h2>
        <ul>
          <li data-claim-support="visible">Support, contradiction, qualification, alternative explanation, and unresolved cards remain separate.</li>
          <li data-exact-source-span="visible">Every card keeps an exact source span and date context.</li>
          <li data-no-binary-truth-score="true">No binary truth score is shown.</li>
          <li data-context-window="visible">Show surrounding context and compare copies are available in the API.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

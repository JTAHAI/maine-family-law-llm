import { EvidenceWorkbench } from "../components/evidence-workbench";

export default function Enforcement() {
  return (
    <EvidenceWorkbench
      activeTab="/enforcement"
      kicker="Evidence work product"
      title="Enforcement Ledger"
      description="Pin the exact current order language beside alleged or observed conduct and keep contempt undecided."
    >
      <section aria-label="Enforcement ledger" className="evidence-workbench-card">
        <h2>Ledger safeguards</h2>
        <ul>
          <li data-order-language-required="true">Exact operative order language is mandatory.</li>
          <li data-stale-order-warning="visible">Stale or superseded orders are flagged.</li>
          <li data-no-contempt-conclusion="true">The ledger never decides contempt or willfulness.</li>
        </ul>
      </section>
    </EvidenceWorkbench>
  );
}

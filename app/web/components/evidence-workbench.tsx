import type { ReactNode } from "react";

const tabs = [
  ["/timeline", "Timeline"],
  ["/evidence", "Claims"],
  ["/contradictions", "Contradictions"],
  ["/coverage", "Record Coverage"],
  ["/missing-records", "Missing Records"],
  ["/enforcement", "Enforcement Ledger"],
  ["/review-history", "Review History"],
] as const;

type EvidenceWorkbenchProps = {
  activeTab: (typeof tabs)[number][0];
  title: string;
  kicker: string;
  description: string;
  children: ReactNode;
};

export function EvidenceWorkbench({ activeTab, title, kicker, description, children }: EvidenceWorkbenchProps) {
  return (
    <main className="evidence-workbench-shell" data-review-status="review_required">
      <header className="evidence-workbench-hero">
        <div>
          <p className="evidence-workbench-kicker">{kicker}</p>
          <h1>{title}</h1>
          <p className="evidence-workbench-description">{description}</p>
        </div>
        <aside className="evidence-workbench-note">
          <strong>Review required.</strong>
          <span>Record presence is not proof. Every event, claim, or ledger row remains linked to source spans and hashes.</span>
        </aside>
      </header>
      <nav aria-label="Evidence work product tabs" className="evidence-workbench-tabs" role="tablist">
        {tabs.map(([href, label]) => (
          <a
            aria-selected={href === activeTab}
            className={href === activeTab ? "is-active" : ""}
            href={href}
            key={href}
            role="tab"
          >
            {label}
          </a>
        ))}
      </nav>
      <section className="evidence-workbench-panel">{children}</section>
    </main>
  );
}

export const evidenceWorkbenchTabs = tabs;

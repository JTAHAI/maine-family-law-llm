import "./focaf-family-law-llm-theme.css";

export function FocafBrandHeader() {
  return (
    <header className="focaf-app-header">
      <div className="focaf-brand">
        <img className="focaf-brand__mark" src="/assets/logo/focaf-family-law-llm-mark.svg" alt="For Our Children & Families" />
        <div>
          <span className="focaf-brand__eyebrow">For Our Children & Families</span>
          <h1 className="focaf-brand__title">Maine Family Law LLM</h1>
          <p className="focaf-brand__sub">Local source-backed research • Review required • Not legal advice</p>
        </div>
      </div>
      <span className="focaf-status">local AI online</span>
    </header>
  );
}

export function LegalNotice() {
  return (
    <div className="focaf-legal-notice">
      This tool provides Maine family-law research from retrieved source snippets. It does not create an attorney-client relationship, does not replace review by a qualified professional, and does not accept private case intake.
    </div>
  );
}

export function SourceCard({ title, excerpt, type = "official source" }) {
  return (
    <article className="focaf-source-card">
      <span className="focaf-source-card__type">{type}</span>
      <h3 className="focaf-source-card__title">{title}</h3>
      <p className="focaf-source-card__excerpt">{excerpt}</p>
      <div>
        <button className="focaf-button focaf-button--secondary">Copy source card</button>{" "}
        <button className="focaf-button focaf-button--ghost">Inspect source</button>
      </div>
    </article>
  );
}

export function ReviewerHandoff() {
  return (
    <section className="focaf-handoff">
      <h3>Reviewer handoff</h3>
      <p>Review required. Verify source status, missing facts, and whether the answer remains within research-only boundaries.</p>
      <ul>
        <li>What facts were assumed?</li>
        <li>Which official source supports the main point?</li>
        <li>What should a clerk, lawyer, or qualified professional review?</li>
      </ul>
    </section>
  );
}

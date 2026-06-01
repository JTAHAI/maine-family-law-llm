const views = [
  ["/", "Matter Dashboard"],
  ["/ask", "Ask Maine Family Law"],
  ["/upload", "Upload Documents"],
  ["/sources", "Source Library"],
  ["/authority", "Authority Matrix"],
  ["/timeline", "Timeline"],
  ["/evidence", "Evidence Map"],
  ["/draft", "Draft Workspace"],
  ["/citations", "Citation Report"],
  ["/quotes", "Quote Report"],
  ["/filing-ready", "Filing-Readiness Gate"],
  ["/review-queue", "Human Review Queue"],
  ["/settings", "Settings / Data Policy"],
  ["/admin/evals", "Admin Eval Dashboard"],
];

export default function App() {
  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }} data-review-status="review_required">
      <h1>Maine Family Law LLM</h1>
      <p data-blocked-export-explanation="visible">All product views are review-required until source, citation, quote, claim, fact, procedure, form, and human-review gates pass.</p>
      <nav aria-label="Production views">
        <ul>
          {views.map(([href, label]) => (
            <li key={href}><a href={href}>{label}</a></li>
          ))}
        </ul>
      </nav>
      <section data-source-card="visible" data-claim-drilldown="answer-to-claim" data-citation-drilldown="claim-to-citation" data-source-text-drilldown="citation-to-source-text" data-verifier-result-drilldown="source-text-to-verifier-result">
        Source-card and verifier drilldown chain: answer → claim → citation → source text → verifier result.
      </section>
    </div>
  );
}

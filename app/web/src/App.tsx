const views = [
  ["/", "Matter Dashboard"],
  ["/ask", "Ask Maine Family Law"],
  ["/upload", "Upload Documents"],
  ["/sources", "Source Library"],
  ["/authority", "Authority Matrix"],
  ["/timeline", "Timeline"],
  ["/evidence", "Evidence Map"],
  ["/contradictions", "Contradictions"],
  ["/coverage", "Record Coverage"],
  ["/missing-records", "Missing Records"],
  ["/enforcement", "Enforcement Ledger"],
  ["/review-history", "Review History"],
  ["/command-center", "Command Center"],
  ["/child-continuity", "Child Continuity"],
  ["/deliberation", "Local Deliberation Workspace"],
  ["/connections", "Connections & Deliberation"],
  ["/draft", "Draft Workspace"],
  ["/citations", "Citation Report"],
  ["/quotes", "Quote Report"],
  ["/communications", "Communications & Parenting-Time"],
  ["/hearing-media", "Hearing Media & Records"],
  ["/filing-ready", "Filing-Readiness Gate"],
  ["/review-queue", "Human Review Queue"],
  ["/settings", "Settings / Data Policy"],
  ["/admin/evals", "Evaluation & Review Lab"],
  ["/admin/release", "Release Control Center"],
  ["/admin/maintenance", "Release Maintenance Center"],
  ["/admin/models", "Local Intelligence Control Center"],
  ["/admin/security", "Security & Privacy Fortress"],
];

const highlights = [
  ["Local only", "All work stays on this device unless the user intentionally opens an external source."],
  ["Review required", "No draft, packet, or export is treated as final without a visible review gate."],
  ["Source first", "Every answer stays anchored to official sources, quote spans, and verifier drill-downs."],
];

const paths = [
  ["Research", "Ask, browse source cards, and inspect exact spans."],
  ["Evidence", "Import records, OCR, scan privacy, and build the case record."],
  ["Release", "Audit the control plane, pilot evidence, and ship-readiness gates."],
];

export default function App() {
  return (
    <main
      data-review-status="review_required"
      style={{
        minHeight: "100vh",
        padding: "2rem",
        color: "#18313a",
        background:
          "radial-gradient(circle at top left, rgba(13, 92, 115, 0.1), transparent 26%), radial-gradient(circle at top right, rgba(140, 90, 43, 0.1), transparent 25%), linear-gradient(180deg, #fbf8f3 0%, #efe6d8 100%)",
        fontFamily: '"Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif',
      }}
    >
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            display: "grid",
            gap: "1rem",
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(103, 123, 119, 0.18)",
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(247,242,233,0.92)), radial-gradient(circle at top right, rgba(13,92,115,0.08), transparent 25%)",
            boxShadow: "0 26px 70px rgba(10, 32, 39, 0.12)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(13, 92, 115, 0.1)", color: "#0d5c73", fontWeight: 700 }}>
              Local only
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(140, 90, 43, 0.1)", color: "#8c5a2b", fontWeight: 700 }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(31, 122, 67, 0.1)", color: "#1f7a43", fontWeight: 700 }}>
              Source first UX
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.45fr) minmax(240px, 0.85fr)", gap: "1rem", alignItems: "end" }}>
            <div>
              <p style={{ margin: 0, textTransform: "uppercase", letterSpacing: "0.24em", color: "#0d5c73", fontWeight: 800, fontSize: "0.77rem" }}>
                Maine Family Law LLM
              </p>
              <h1 style={{ margin: "0.35rem 0 0", fontSize: "clamp(2.4rem, 5vw, 4.8rem)", lineHeight: 0.94, letterSpacing: "-0.05em" }}>
                A desktop legal workbench that feels calm, capable, and unmistakably premium.
              </h1>
              <p style={{ maxWidth: 900, margin: "0.95rem 0 0", lineHeight: 1.72, color: "#4d5a61", fontSize: "1.02rem" }}>
                The UI keeps every workflow local, review-required, and source-backed while giving ordinary users a polished command center instead of a generic internal tool.
              </p>
            </div>
            <div style={{ display: "grid", gap: "0.75rem" }}>
              {highlights.map(([label, body]) => (
                <article key={label} style={{ padding: "0.95rem 1rem", borderRadius: 20, background: "rgba(255,255,255,0.75)", border: "1px solid rgba(103, 123, 119, 0.14)" }}>
                  <h2 style={{ margin: 0, fontSize: "0.95rem" }}>{label}</h2>
                  <p style={{ margin: "0.35rem 0 0", lineHeight: 1.55, color: "#54646c" }}>{body}</p>
                </article>
              ))}
            </div>
          </div>
        </header>

        <section aria-label="Workflow paths" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
          {paths.map(([title, body]) => (
            <article key={title} style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.76)", border: "1px solid rgba(103, 123, 119, 0.14)", boxShadow: "0 16px 40px rgba(10, 32, 39, 0.08)" }}>
              <h2 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1.05rem" }}>{title}</h2>
              <p style={{ margin: 0, lineHeight: 1.7, color: "#506068" }}>{body}</p>
            </article>
          ))}
        </section>

        <section
          style={{
            padding: "1.2rem",
            borderRadius: 24,
            border: "1px solid rgba(103, 123, 119, 0.16)",
            background: "linear-gradient(180deg, rgba(255,255,255,0.86), rgba(247,242,233,0.9))",
            boxShadow: "0 18px 48px rgba(10, 32, 39, 0.08)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", alignItems: "end" }}>
            <div>
              <p style={{ margin: 0, textTransform: "uppercase", letterSpacing: "0.2em", color: "#0d5c73", fontWeight: 800, fontSize: "0.76rem" }}>
                Production views
              </p>
              <h2 style={{ margin: "0.4rem 0 0", fontSize: "1.8rem", lineHeight: 1.08 }}>Navigate from public research to release operations without losing context.</h2>
            </div>
            <div style={{ color: "#5f6b74", maxWidth: 420, lineHeight: 1.65 }}>
              The navigation below is the shared jump table for the shipped desktop, keeping the control center, maintenance center, and workbench pages one click away.
            </div>
          </div>

          <nav aria-label="Production views" style={{ marginTop: "1rem" }}>
            <ul style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.7rem", listStyle: "none", padding: 0, margin: 0 }}>
              {views.map(([href, label]) => (
                <li key={href}>
                  <a
                    href={href}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "0.75rem",
                      padding: "0.9rem 1rem",
                      borderRadius: 18,
                      background: "rgba(13, 92, 115, 0.06)",
                      border: "1px solid rgba(13, 92, 115, 0.12)",
                      color: "#123d4c",
                      textDecoration: "none",
                      fontWeight: 650,
                    }}
                  >
                    <span>{label}</span>
                    <span aria-hidden="true" style={{ color: "#0d5c73" }}>
                      ↗
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </section>

        <section
          data-source-card="visible"
          data-claim-drilldown="answer-to-claim"
          data-citation-drilldown="claim-to-citation"
          data-source-text-drilldown="citation-to-source-text"
          data-verifier-result-drilldown="source-text-to-verifier-result"
          data-attorney-eval-lab="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(103, 123, 119, 0.14)",
            background: "linear-gradient(135deg, rgba(13, 92, 115, 0.08), rgba(255,255,255,0.88))",
            boxShadow: "0 16px 40px rgba(10, 32, 39, 0.08)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <p style={{ margin: 0, textTransform: "uppercase", letterSpacing: "0.2em", color: "#0d5c73", fontWeight: 800, fontSize: "0.76rem" }}>
                Drill-down chain
              </p>
              <h2 style={{ margin: "0.4rem 0 0", fontSize: "1.5rem" }}>Answer → claim → citation → source text → verifier result</h2>
            </div>
            <div style={{ color: "#4f5d65", lineHeight: 1.65, maxWidth: 460 }}>
              The desk never asks users to trust a black box. It makes each step of the legal reasoning chain inspectable before anything is treated as review-worthy.
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

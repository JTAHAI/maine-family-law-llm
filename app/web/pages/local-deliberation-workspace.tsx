const stageCards = [
  {
    title: "Scope Freeze",
    body: "Create a local-only run, lock the matter scope, and record the exact question, records, and authority lanes before any analysis begins.",
  },
  {
    title: "Blind Worker Pass",
    body: "Let the worker set produce the first-pass positions without seeing each other’s names, then collect claims, critiques, and omission notes.",
  },
  {
    title: "Claim Ledger",
    body: "Align worker positions into a durable ledger that preserves dissent, correction history, support status, and record or authority provenance.",
  },
  {
    title: "Verification Bridge",
    body: "Send only allowlisted read-only tool calls through the local broker so citations, quote spans, freshness, and record slices stay auditable.",
  },
];

const lifecycle = [
  "draft_scope",
  "awaiting_local_confirmation",
  "queued",
  "running_independent",
  "aligning_claims",
  "cross_review",
  "rebuttal",
  "omission_hunt",
  "final_positions",
  "verifying",
  "synthesizing",
  "completed_review_required",
];

export default function LocalDeliberationWorkspace() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="local-deliberation-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f4f7fb",
        background:
          "radial-gradient(circle at top left, rgba(0, 174, 239, 0.22), transparent 34%), radial-gradient(circle at top right, rgba(255, 176, 62, 0.18), transparent 30%), linear-gradient(180deg, #07111d 0%, #0d1727 45%, #060b12 100%)",
      }}
    >
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>
        <header
          style={{
            display: "grid",
            gap: "1rem",
            marginBottom: "1.25rem",
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.09)",
            background: "rgba(11, 18, 31, 0.8)",
            boxShadow: "0 28px 90px rgba(0, 0, 0, 0.38)",
            backdropFilter: "blur(18px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", alignItems: "center" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(0, 174, 239, 0.16)", color: "#9fe9ff" }}>
              Local only
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 176, 62, 0.16)", color: "#ffe0b2" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(129, 103, 255, 0.16)", color: "#d9cfff" }}>
              Read-only broker
            </span>
          </div>
          <div>
            <h1 id="local-deliberation-title" style={{ margin: 0, fontSize: "clamp(2.1rem, 4.5vw, 4rem)", lineHeight: 0.98 }}>
              Local Deliberation Workspace
            </h1>
            <p style={{ maxWidth: 820, margin: "0.9rem 0 0", fontSize: "1.05rem", lineHeight: 1.7, color: "#c4d3ea" }}>
              This workspace keeps the prefrontal node, claim ledger, omission hunt, dissent preservation, and verification bridge entirely on the local machine. Nothing here depends on outbound network access or remote MCP providers.
            </p>
          </div>
        </header>

        <section
          aria-label="Deliberation workflow"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
            marginBottom: "1rem",
          }}
        >
          {stageCards.map((card) => (
            <article
              key={card.title}
              style={{
                padding: "1.2rem",
                minHeight: 180,
                borderRadius: 24,
                border: "1px solid rgba(255,255,255,0.08)",
                background: "linear-gradient(180deg, rgba(18, 27, 44, 0.92), rgba(10, 16, 28, 0.92))",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.6rem", fontSize: "1.15rem" }}>{card.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.7, color: "#c7d3e9" }}>{card.body}</p>
            </article>
          ))}
        </section>

        <section
          aria-label="Lifecycle"
          style={{
            display: "grid",
            gap: "0.9rem",
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(255,255,255,0.09)",
            background: "rgba(9, 15, 26, 0.84)",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "1.25rem" }}>Run lifecycle</h2>
            <p style={{ margin: "0.45rem 0 0", color: "#c9d5ea", lineHeight: 1.6 }}>
              The state machine keeps the deliberation path explicit so every run can be audited from scope freeze through synthesis.
            </p>
          </div>
          <ol
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "0.65rem",
              listStyle: "none",
              padding: 0,
              margin: 0,
            }}
          >
            {lifecycle.map((state, index) => (
              <li
                key={state}
                style={{
                  padding: "0.8rem 0.95rem",
                  borderRadius: 18,
                  background: index === lifecycle.length - 1 ? "rgba(0, 174, 239, 0.16)" : "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <span style={{ display: "block", fontSize: "0.78rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "#8fa2c4" }}>
                  Step {index + 1}
                </span>
                <span style={{ display: "block", marginTop: "0.25rem", fontWeight: 600 }}>{state}</span>
              </li>
            ))}
          </ol>
        </section>

        <section
          aria-label="Operational guardrails"
          data-blocked-export-explanation="visible"
          style={{
            marginTop: "1rem",
            padding: "1.25rem",
            borderRadius: 24,
            background: "linear-gradient(90deg, rgba(255, 176, 62, 0.16), rgba(255,255,255,0.04))",
            border: "1px solid rgba(255, 203, 137, 0.24)",
            color: "#f7ebdb",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Guardrails</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.7 }}>
            <li>No outbound traffic, remote MCP, browser, or provider calls are allowed inside the deliberation host.</li>
            <li>Every tool invocation is read-only, allowlisted, and tied to a run-scoped token audit.</li>
            <li>Dissent, corrections, omissions, and authority freshness remain visible all the way to the final synthesis.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

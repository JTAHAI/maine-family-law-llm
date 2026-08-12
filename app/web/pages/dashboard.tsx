const activity = [
  ["Source cards", "Browse official citations, exact spans, and freshness state before relying on any answer."],
  ["Review queue", "Keep blocked exports, contradictions, and missing facts visible until a human resolves them."],
  ["Case continuity", "The matter dashboard preserves the path from research to draft without losing context."],
];

const metrics = [
  ["Local", "Offline-first workbench"],
  ["Review", "Human required"],
  ["Traceability", "Source + span linked"],
  ["Exports", "Gate enforced"],
];

export default function Dashboard() {
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
      <div style={{ maxWidth: 1360, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
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
              Matter dashboard
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(140, 90, 43, 0.1)", color: "#8c5a2b", fontWeight: 700 }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(31, 122, 67, 0.1)", color: "#1f7a43", fontWeight: 700 }}>
              Source first
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(260px, 0.9fr)", gap: "1rem", alignItems: "end", marginTop: "0.9rem" }}>
            <div>
              <p style={{ margin: 0, textTransform: "uppercase", letterSpacing: "0.22em", color: "#0d5c73", fontWeight: 800, fontSize: "0.77rem" }}>
                Shipped desktop
              </p>
              <h1 style={{ margin: "0.35rem 0 0", fontSize: "clamp(2.2rem, 4.6vw, 4.2rem)", lineHeight: 0.96, letterSpacing: "-0.05em" }}>
                A matter workspace that turns legal work into a visible, guided, source-backed flow.
              </h1>
              <p style={{ maxWidth: 900, margin: "0.95rem 0 0", lineHeight: 1.72, color: "#4d5a61", fontSize: "1.02rem" }}>
                Source cards, citations, contradictions, blocked exports, and review gates live in one place so an ordinary user can move from intake to draft without manually piecing the system together.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "0.75rem" }}>
              {metrics.map(([label, value]) => (
                <article key={label} style={{ padding: "0.95rem", borderRadius: 18, background: "rgba(255,255,255,0.78)", border: "1px solid rgba(103, 123, 119, 0.14)" }}>
                  <div style={{ fontSize: "0.76rem", textTransform: "uppercase", letterSpacing: "0.14em", color: "#7a6a58", fontWeight: 800 }}>{label}</div>
                  <div style={{ marginTop: "0.35rem", fontWeight: 700, color: "#1f3440" }}>{value}</div>
                </article>
              ))}
            </div>
          </div>
        </header>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
          {activity.map(([title, body]) => (
            <article
              key={title}
              style={{
                padding: "1.15rem",
                borderRadius: 22,
                background: "rgba(255,255,255,0.76)",
                border: "1px solid rgba(103, 123, 119, 0.14)",
                boxShadow: "0 16px 40px rgba(10, 32, 39, 0.08)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.5rem", fontSize: "1.05rem" }}>{title}</h2>
              <p style={{ margin: 0, lineHeight: 1.7, color: "#506068" }}>{body}</p>
            </article>
          ))}
        </section>

        <section
          data-source-card="visible"
          data-claim-drilldown="answer-to-claim"
          data-citation-drilldown="claim-to-citation"
          data-source-text-drilldown="citation-to-source-text"
          data-verifier-result-drilldown="source-text-to-verifier-result"
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
                Source card
              </p>
              <h2 style={{ margin: "0.4rem 0 0", fontSize: "1.5rem" }}>Jurisdiction, authority, freshness, citation, and quote span availability</h2>
            </div>
            <div style={{ color: "#4f5d65", lineHeight: 1.65, maxWidth: 460 }}>
              The dashboard keeps drill-down markers visible so every legal claim can move back to exact source text without dropping context.
            </div>
          </div>
        </section>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
          <article
            data-blocked-export-explanation="visible"
            style={{
              padding: "1.25rem",
              borderRadius: 24,
              border: "1px solid rgba(255, 193, 109, 0.2)",
              background: "linear-gradient(180deg, rgba(255, 184, 77, 0.12), rgba(255,255,255,0.03))",
            }}
          >
            <h2 style={{ marginTop: 0 }}>Blocked export explanation</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.75, color: "#5a4931" }}>
              Exports stay blocked until authority, citation, quote, claim, fact, procedure, form, and human review gates are satisfied.
            </p>
          </article>
          <article style={{ padding: "1.25rem", borderRadius: 24, border: "1px solid rgba(103, 123, 119, 0.14)", background: "rgba(255,255,255,0.76)" }}>
            <h2 style={{ marginTop: 0 }}>Recent activity</h2>
            <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#506068" }}>
              <li>Matter import, source review, and blocked export traces stay visible together.</li>
              <li>Contradictions and missing context remain open until resolved by a reviewer.</li>
              <li>Freshness and source status carry forward into the workbench and draft flow.</li>
            </ul>
          </article>
        </section>
      </div>
    </main>
  );
}

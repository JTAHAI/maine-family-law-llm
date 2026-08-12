const providerCards = [
  {
    name: "OpenAI",
    status: "Disconnected",
    model: "Operator selected",
    api: "Responses API",
    summary:
      "BYOK credentials stay in Windows Credential Manager and no provider traffic is sent until a manifest is approved.",
  },
  {
    name: "Gemini",
    status: "Limited",
    model: "Operator selected",
    api: "Gemini API",
    summary:
      "Capability visibility is available, but outbound use stays disabled unless the endpoint and consent path are explicitly configured.",
  },
  {
    name: "xAI",
    status: "Limited",
    model: "Operator selected",
    api: "xAI API",
    summary: "Connection metadata and retention disclosure stay visible, but no transmission happens without exact approval.",
  },
];

const consentModes = [
  {
    title: "Local only",
    body: "No external traffic, discovery, health checks, or telemetry. This is the default.",
  },
  {
    title: "Question only",
    body: "Only the question and non-sensitive instructions can be transmitted.",
  },
  {
    title: "Selected excerpts",
    body: "Only the previewed excerpts are eligible for outbound use.",
  },
  {
    title: "Selected document",
    body: "Requires a second confirmation and exact preview before any transmission.",
  },
];

const previewFields = [
  "Exact question",
  "Selected excerpts",
  "Provider metadata",
  "Pinned model",
  "Tool permissions",
  "Data-control disclosure",
  "Estimated usage",
  "Serialized payload",
  "Payload hash",
];

const liveTimeline = [
  "Prepare connection",
  "Verify provider status",
  "Preview exact payload",
  "Approve hash",
  "Start or cancel run",
  "Review usage summary",
];

const participation = [
  "Question only remains the lowest-disclosure mode.",
  "Selected excerpts keep private-record sharing bounded.",
  "Selected document requires a second explicit confirmation.",
  "All provider sessions remain isolated from each other.",
];

const failures = [
  "Auth failures stay visible and block transmission.",
  "Rate limits and outage states fail closed.",
  "Schema or destination changes invalidate approval.",
  "Tool mismatch or stale approval stops the run.",
];

const budgets = [
  "Pre-run estimate",
  "Total cap",
  "Provider cap",
  "Round cap",
  "Context cap",
  "Output cap",
  "Tool-call cap",
  "Private-record tool cap",
  "Retry cap",
  "Timeout",
  "Circuit breaker",
];

const synthesisPoints = [
  "The local verifier remains the truth gate.",
  "Consensus cannot certify unsupported claims.",
  "Dissent stays visible instead of being collapsed away.",
  "The verified synthesis is review-required, not authoritative.",
];

const sharingSummaryPoints = [
  "No provider sharing happens while local-only is active.",
  "Exact outbound preview is shown before approval.",
  "Provider-to-provider communication is prohibited.",
  "Returned-to-local-only mode clears active sessions without hiding the status change.",
];

const redactions = [
  "Paths",
  "Usernames",
  "Internal IDs",
  "Credentials",
  "Unrelated PII",
  "Unrelated text",
  "Hidden metadata",
];

export default function ConnectionsDeliberation() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="connections-deliberation-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f5f7fb",
        background:
          "radial-gradient(circle at top left, rgba(73, 118, 255, 0.26), transparent 34%), radial-gradient(circle at bottom right, rgba(20, 190, 170, 0.22), transparent 34%), linear-gradient(180deg, #09111f 0%, #10172a 46%, #08101d 100%)",
      }}
    >
      <div style={{ maxWidth: 1240, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(11, 18, 34, 0.84)",
            boxShadow: "0 28px 70px rgba(0,0,0,0.35)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(20, 190, 170, 0.18)", color: "#96f0e4" }}>
              Local-only by default
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(73, 118, 255, 0.18)", color: "#d7e1ff" }}>
              Exact hash approval
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 184, 77, 0.16)", color: "#ffe1b3" }}>
              Review required
            </span>
          </div>
          <h1 id="connections-deliberation-title" style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3.6rem)", lineHeight: 1.02 }}>
            Connections & Deliberation
          </h1>
          <p style={{ maxWidth: 900, marginTop: "0.9rem", lineHeight: 1.65, color: "#c8d2ea" }}>
            Connect your own provider credentials, preview the exact outbound packet, approve the hash, and keep every provider session isolated from the others.
          </p>
        </header>

        <section aria-label="Provider connections" style={{ display: "grid", gap: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "1rem", flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>Provider connections</h2>
            <p style={{ margin: 0, color: "#99a8c8" }}>BYOK credentials stay out of config files, prompts, and exports.</p>
          </div>
          <div
            data-provider-connection-card="visible"
            style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}
          >
            {providerCards.map((provider) => (
              <article
                key={provider.name}
                style={{
                  padding: "1.1rem",
                  borderRadius: 22,
                  border: "1px solid rgba(255,255,255,0.1)",
                  background: "linear-gradient(180deg, rgba(19,28,49,0.95), rgba(10,16,29,0.95))",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", alignItems: "start" }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{provider.name}</h3>
                    <p style={{ margin: "0.35rem 0 0", color: "#aebcde" }}>{provider.summary}</p>
                  </div>
                  <span style={{ padding: "0.3rem 0.6rem", borderRadius: 999, background: "rgba(255,255,255,0.08)", color: "#e8eefc" }}>{provider.status}</span>
                </div>
                <dl style={{ margin: "1rem 0 0", display: "grid", gap: "0.65rem" }}>
                  <div>
                    <dt style={{ color: "#8ea0c8", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>Pinned model</dt>
                    <dd style={{ margin: "0.2rem 0 0", fontWeight: 600 }}>{provider.model}</dd>
                  </div>
                  <div>
                    <dt style={{ color: "#8ea0c8", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>Official API class</dt>
                    <dd style={{ margin: "0.2rem 0 0", fontWeight: 600 }}>{provider.api}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        </section>

        <section aria-label="Provider status" data-provider-status-card="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Provider status</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Windows Credential Manager</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>Secrets remain in the local credential store and do not appear in prompts or exports.</p>
            </article>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Provider isolation</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>Each provider keeps its own context, budget, cancellation, and audit trail.</p>
            </article>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Local-only reset</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>The return-local-only route clears active sessions and restores the zero-network posture.</p>
            </article>
          </div>
        </section>

        <section aria-label="Run setup" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Run setup</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {consentModes.map((mode) => (
              <article key={mode.title} style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <h3 style={{ marginTop: 0 }}>{mode.title}</h3>
                <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>{mode.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section aria-label="Exact outbound preview" data-outbound-manifest="visible" data-exact-outbound-preview="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Exact outbound preview</h2>
          <article
            style={{
              padding: "1.25rem",
              borderRadius: 22,
              border: "1px solid rgba(255,255,255,0.1)",
              background: "linear-gradient(180deg, rgba(31, 39, 69, 0.92), rgba(16, 21, 39, 0.94))",
            }}
          >
            <p style={{ marginTop: 0, color: "#bfd0ff" }}>
              The preview includes the exact question, selected excerpts, provider metadata, tool permissions, estimated usage, retention disclosure, and payload hash before anything can move to transmission.
            </p>
            <ol style={{ marginBottom: 0, lineHeight: 1.8, color: "#e2e8fb" }}>
              {previewFields.map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ol>
          </article>
        </section>

        <section aria-label="Redactions" data-redactions="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Redactions</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.8rem" }}>
            {redactions.map((item) => (
              <article key={item} style={{ padding: "0.95rem 1rem", borderRadius: 18, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <strong>{item}</strong>
              </article>
            ))}
          </div>
        </section>

        <section aria-label="Approval" data-approval="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Approval</h2>
          <article
            style={{
              padding: "1.1rem",
              borderRadius: 22,
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <p style={{ marginTop: 0, color: "#d1d9ef", lineHeight: 1.65 }}>
              Approval is hash-bound. Any change to the question, excerpts, provider, pinned model, tools, or scope invalidates the consent and requires a fresh review.
            </p>
            <ul style={{ marginBottom: 0, lineHeight: 1.7, color: "#e2e8fb" }}>
              <li>Approval is not recurring.</li>
              <li>Approval does not grant future runs.</li>
              <li>Approval never bypasses local verification.</li>
            </ul>
          </article>
        </section>

        <section aria-label="Live timeline" data-live-timeline="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Live timeline</h2>
          <ol
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "0.75rem",
              listStyle: "none",
              padding: 0,
              margin: 0,
            }}
          >
            {liveTimeline.map((step, index) => (
              <li key={step} style={{ padding: "0.85rem 0.95rem", borderRadius: 18, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <span style={{ display: "block", fontSize: "0.78rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "#8fa2c4" }}>Step {index + 1}</span>
                <span style={{ display: "block", marginTop: "0.25rem", fontWeight: 600 }}>{step}</span>
              </li>
            ))}
          </ol>
        </section>

        <section aria-label="Participation" data-participation="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Participation</h2>
          <article style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <ul style={{ margin: 0, lineHeight: 1.7, color: "#d1d9ef" }}>
              {participation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>

        <section aria-label="Failures" data-failures="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Failures</h2>
          <article style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <ul style={{ margin: 0, lineHeight: 1.7, color: "#d1d9ef" }}>
              {failures.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>

        <section aria-label="Budgets" data-budgets="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Budgets</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem" }}>
            {budgets.map((item) => (
              <article key={item} style={{ padding: "0.9rem 1rem", borderRadius: 18, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <strong>{item}</strong>
              </article>
            ))}
          </div>
        </section>

        <section aria-label="Final verified synthesis" data-final-verified-synthesis="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Final verified synthesis</h2>
          <article style={{ padding: "1.1rem", borderRadius: 22, background: "linear-gradient(180deg, rgba(14, 22, 40, 0.96), rgba(9, 15, 26, 0.96))", border: "1px solid rgba(255,255,255,0.08)" }}>
            <ul style={{ margin: 0, lineHeight: 1.7, color: "#d1d9ef" }}>
              {synthesisPoints.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>

        <section aria-label="Sharing summary" data-sharing-summary="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Sharing summary</h2>
          <article style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <ul style={{ margin: 0, lineHeight: 1.7, color: "#d1d9ef" }}>
              {sharingSummaryPoints.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </section>

        <section aria-label="Privacy controls" data-privacy-controls="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Privacy controls</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem" }}>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Return to local only</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>Flip back to local-only mode whenever you want to clear the outbound path.</p>
            </article>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Disconnect all</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>Drop all active provider sessions without revealing credentials in the UI.</p>
            </article>
            <article style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Revoke credentials</h3>
              <p style={{ marginBottom: 0, color: "#d1d9ef", lineHeight: 1.65 }}>Remove provider secrets from Windows Credential Manager, then re-connect only if you mean to.</p>
            </article>
          </div>
        </section>
      </div>
    </main>
  );
}

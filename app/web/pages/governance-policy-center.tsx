const sections = [
  {
    title: "Controls",
    marker: "data-governance-control-registry",
    body: "A versioned control registry shows implementation status, evidence, gaps, owners, reviewers, due dates, exceptions, and release-blocking status.",
  },
  {
    title: "Framework mappings",
    marker: "data-framework-mappings",
    body: "Project controls are mapped to NIST AI RMF, NIST AI 600-1, OWASP LLM risks, privacy, application security, accessibility, supply chain, human review, source freshness, and legal verification.",
  },
  {
    title: "Policies",
    marker: "data-policy-library",
    body: "Versioned policy documents keep purpose, limitations, owners, evidence references, supersession, and change history visible without claiming certification.",
  },
  {
    title: "Policy packs",
    marker: "data-policy-packs",
    body: "Role-based packs constrain workers, providers, sharing, exports, retention, evaluation, redaction, and filing gates without weakening baseline safeguards.",
  },
  {
    title: "Model cards",
    marker: "data-model-cards",
    body: "Cards are generated from the real model registry and preserve role, license, hash, runtime, evidence, context limits, fallback, and admission status.",
  },
  {
    title: "Data cards",
    marker: "data-data-cards",
    body: "Cards describe authority stores, parsed authority, indexes, evaluation data, synthetic fixtures, private matter stores, OCR derivatives, audit records, and evidence packets.",
  },
  {
    title: "Vendor risks",
    marker: "data-vendor-risks",
    body: "Provider records state what data may be sent, what is not sent, retention summaries, boundaries, risks, compensating controls, and a disable plan.",
  },
  {
    title: "Exceptions",
    marker: "data-exceptions",
    body: "Exceptions are versioned and expiring, and expired exceptions stay visible so they cannot be mistaken for current approval.",
  },
  {
    title: "Sign-offs",
    marker: "data-sign-offs",
    body: "Safe identities, scope, evidence reviewed, unresolved gaps, approve/reject state, conditions, and expiration are kept separate for each owner role.",
  },
  {
    title: "Diligence packet",
    marker: "data-diligence-packet",
    body: "The redacted packet bundles architecture, control mappings, policies, cards, evidence hashes, gaps, and sign-offs while excluding private matter content and secrets.",
  },
  {
    title: "Gaps and remediation",
    marker: "data-gaps-remediation",
    body: "Visible gaps keep an owner, risk, remediation plan, and due date so missing evidence is treated as work, not as hidden success.",
  },
  {
    title: "History",
    marker: "data-governance-history",
    body: "Policy and sign-off changes are hash-chained so activation, rollback, expiration, and supersession remain auditable.",
  },
];

export default function GovernancePolicyCenter() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="governance-policy-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f4f1ea",
        background:
          "radial-gradient(circle at top left, rgba(103, 80, 164, 0.18), transparent 32%), radial-gradient(circle at top right, rgba(46, 204, 113, 0.14), transparent 30%), linear-gradient(180deg, #0f1218 0%, #151922 44%, #090b10 100%)",
        fontFamily: '"Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif',
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.09)",
            background: "rgba(15, 18, 24, 0.84)",
            boxShadow: "0 28px 80px rgba(0,0,0,0.38)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(103, 80, 164, 0.16)", color: "#dccfff" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(46, 204, 113, 0.14)", color: "#baf3cb" }}>
              Evidence before claims
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 183, 77, 0.16)", color: "#ffe0ae" }}>
              No certification claim
            </span>
          </div>
          <h1 id="governance-policy-title" style={{ margin: 0, fontSize: "clamp(2.2rem, 4.5vw, 4rem)", lineHeight: 1.01 }}>
            Governance &amp; Policy Center
          </h1>
          <p style={{ maxWidth: 900, marginTop: "0.9rem", lineHeight: 1.68, color: "#d8d0c4", fontSize: "1.03rem" }}>
            A single admin view for the control registry, framework mappings, policies, policy packs, model cards, data cards, vendor risk notes, exceptions, sign-offs, and diligence packet evidence.
          </p>
        </header>

        <section
          aria-label="Governance overview"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
          }}
        >
          {sections.map((section) => (
            <article
              key={section.title}
              data-testid={section.marker}
              style={{
                minHeight: 180,
                padding: "1.15rem",
                borderRadius: 22,
                border: "1px solid rgba(255,255,255,0.09)",
                background: "linear-gradient(180deg, rgba(27, 32, 41, 0.96), rgba(12, 15, 21, 0.98))",
                boxShadow: "0 18px 44px rgba(0,0,0,0.24)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.55rem", fontSize: "1.08rem" }}>{section.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.68, color: "#d7d0c7" }}>{section.body}</p>
            </article>
          ))}
        </section>

        <section
          aria-label="Policy guardrails"
          data-blocked-export-explanation="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(255, 193, 109, 0.2)",
            background: "linear-gradient(180deg, rgba(255, 184, 77, 0.12), rgba(255,255,255,0.03))",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Guardrails</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f5ead6" }}>
            <li>Policy packs cannot weaken baseline safeguards.</li>
            <li>Missing evidence stays visible with an owner and remediation plan.</li>
            <li>Expired exceptions remain visible until they are renewed or removed.</li>
            <li>Sign-offs cannot override deterministic release gates.</li>
            <li>No private matter content, credentials, or raw local paths are exported.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

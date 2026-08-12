const sections = [
  { title: "Communications workbench", marker: "data-communications-workbench", body: "Import email, SMS, parenting-app, calendar, call-log, school, childcare, transportation, and medical appointment communications from local synthetic or case-approved exports only." },
  { title: "Thread reconstruction", marker: "data-thread-reconstruction", body: "Rebuild threads from reply chains, subjects, and explicit thread IDs while preserving ambiguity and alternative thread candidates." },
  { title: "Schedule history", marker: "data-schedule-history", body: "Keep proposals, confirmations, disagreements, delays, informal changes, and court orders separate so silence never becomes agreement." },
  { title: "Parenting-time review", marker: "data-parenting-time-review", body: "Track alleged missed exchanges, contrary communications, and source-linked parenting-time events without reaching custody, fitness, or abuse conclusions." },
  { title: "Agreement mapping", marker: "data-agreement-mapping", body: "Map each claim to support, contradiction, qualification, and missing context before any human review decision is recorded." },
  { title: "Completeness", marker: "data-completeness", body: "Show missing attachments, uncertain time zones, duplicates, and partial records so gaps stay visible instead of being silently collapsed." },
  { title: "Export receipt", marker: "data-export-receipt", body: "Exports are review-required, hash-bound, and tied to the exact imported records and thread reconstruction state." },
  { title: "Privacy review", marker: "data-privacy-review", body: "No credentials, raw paths, or private diagnostics appear in the shipped UI." },
  { title: "Review history", marker: "data-review-history", body: "History stays append-only in meaning even when records are corrected, clarified, or superseded." },
];

export default function CommunicationsParentingTime() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="communications-parenting-time-title"
      style={{
        minHeight: "100vh",
        padding: "2rem 1.25rem 3rem",
        color: "#f5f7ff",
        background:
          "radial-gradient(circle at top left, rgba(247, 170, 92, 0.18), transparent 36%), radial-gradient(circle at bottom right, rgba(92, 176, 255, 0.18), transparent 36%), linear-gradient(180deg, #0a1020 0%, #121c33 44%, #07101d 100%)",
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.12)",
            background: "rgba(9, 15, 30, 0.9)",
            boxShadow: "0 30px 72px rgba(0,0,0,0.36)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(92, 176, 255, 0.18)", color: "#d8e7ff" }}>Local-only</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(247, 170, 92, 0.18)", color: "#ffe7c4" }}>Review required</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(123, 220, 185, 0.16)", color: "#c6f5e6" }}>Hash-bound exports</span>
          </div>
          <h1 id="communications-parenting-time-title" style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3.5rem)", lineHeight: 1.03 }}>
            Communications and Parenting-Time
          </h1>
          <p style={{ maxWidth: 960, marginTop: "0.9rem", lineHeight: 1.7, color: "#cad5f2" }}>
            The shipped workbench turns local email, SMS, parenting-app, calendar, call-log, school, childcare, transportation, and medical appointment records into source-linked thread reconstructions and parenting-time review aids.
          </p>
          <p style={{ margin: 0, color: "#aebfdf" }}>
            No parent ranking, no custody score, no fitness conclusion, and no abuse conclusion appear anywhere in this workflow.
          </p>
        </header>

        <section aria-label="Workspace promise" data-communications-workbench="visible" style={{ display: "grid", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Workspace promise</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.9rem" }}>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Exact source drill-down</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>Every thread, schedule change, parenting-time event, claim, and export receipt stays tied to a source reference and source hash.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Ambiguity stays visible</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>Incomplete reply chains, quoted duplication, missing attachments, and uncertain time zones stay marked instead of being silently resolved.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Review-required exports</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>The export receipt binds the exact imported records and reconstruction state to the generated bundle hash.</p>
            </article>
          </div>
        </section>

        <section aria-label="Thread reconstruction" data-thread-reconstruction="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Thread reconstruction</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              The workbench groups messages by explicit thread ID, reply chain, or subject normalization and keeps alternative thread candidates when the reconstruction is not certain.
            </p>
            <p style={{ marginBottom: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Duplicate messages, quoted snippets, and missing attachments stay visible as review items rather than being erased from the record.
            </p>
          </article>
        </section>

        <section
          aria-label="Schedule history"
          data-schedule-history="visible"
          data-agreement-mapping="visible"
          data-parenting-time-review="visible"
          data-completeness="visible"
          data-privacy-review="visible"
          data-review-history="visible"
          style={{ display: "grid", gap: "1rem" }}
        >
          <h2 style={{ margin: 0 }}>Schedule history</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Proposals, confirmations, disagreements, delays, informal changes, and court orders stay distinct so silence never becomes agreement and an order never gets overwritten by an informal message.
            </p>
            <p style={{ marginBottom: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              The same record keeps agreement mapping, parenting-time review, completeness, and review history visible to the reviewer.
            </p>
          </article>
        </section>

        <section aria-label="Workflow sections" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Workflow sections</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {sections.map((section) => (
              <article
                key={section.title}
                data-review-status="review_required"
                style={{
                  padding: "1rem 1.05rem",
                  borderRadius: 22,
                  background: "linear-gradient(180deg, rgba(22, 28, 49, 0.96), rgba(13, 18, 34, 0.96))",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <h3 style={{ marginTop: 0 }}>{section.title}</h3>
                <p style={{ marginBottom: "0.75rem", color: "#d0d9f0", lineHeight: 1.6 }}>{section.body}</p>
                <code style={{ display: "inline-block", padding: "0.25rem 0.5rem", borderRadius: 999, background: "rgba(255,255,255,0.08)" }}>{section.marker}</code>
              </article>
            ))}
          </div>
        </section>

        <section aria-label="Export receipt" data-export-receipt="visible" style={{ display: "grid", gap: "0.9rem" }}>
          <h2 style={{ margin: 0 }}>Export receipt</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)" }}>
            <p style={{ marginTop: 0, color: "#d0d9f0", lineHeight: 1.65 }}>
              The receipt tracks message counts, thread counts, source hashes, and review history hashes so the bundle can be reopened against the exact imported communication set later.
            </p>
            <p style={{ marginBottom: 0, color: "#aac0ef" }}>
              Accessible keyboard operation, visible focus, and status text that does not depend on color are preserved in the shipped desktop shell.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}

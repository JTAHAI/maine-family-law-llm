const profileSections = [
  { title: "Child profile", marker: "data-child-profile", body: "Keep the child record local, encrypted, and review-required. Sensitive names, dates of birth, and school details stay masked by default." },
  { title: "School", marker: "data-school-records", body: "Track school contacts, attendance notes, and school-date conflicts without connecting external school accounts." },
  { title: "Health and care", marker: "data-health-care", body: "Record medical and behavioral-care appointments, provider recommendations, prescriptions, referrals, and attendance status as documented only." },
  { title: "Childcare and services", marker: "data-care-records", body: "Keep childcare, therapeutic services, and service handoffs separate from diagnosis or custody conclusions." },
  { title: "Service records", marker: "data-service-records", body: "Service records stay source-linked and distinct from custody or diagnosis conclusions." },
  { title: "Routines", marker: "data-routine-records", body: "Capture bedtime, homework, medication, and transition routines as neutral continuity facts." },
  { title: "Transportation", marker: "data-transportation-records", body: "Log exchanges, ride changes, and route gaps as logistics only. No parent ranking or score appears here." },
  { title: "Parent-child and sibling contact", marker: "data-contact-records", body: "Show contact patterns and missed connection claims while preserving source spans and ambiguity." },
  { title: "Appointment ledger", marker: "data-appointment-ledger", body: "Scheduled, attended, missed, and rescheduled appointments remain distinct so uncertainty never collapses into a conclusion." },
  { title: "Schedule scenarios", marker: "data-schedule-scenarios", body: "Neutral scenario comparisons calculate continuity load, handoffs, and commute burden without custody scoring." },
  { title: "Neutral schedule", marker: "data-neutral-schedule", body: "Neutral schedule analysis compares logistics only and never ranks parents." },
  { title: "Continuity gaps", marker: "data-continuity-gaps", body: "Surface missing school, care, transport, or appointment evidence so the gap itself stays visible." },
  { title: "Claims and contradictions", marker: "data-claims-contradictions", body: "Link every claim to support, contradiction, qualification, and missing context." },
  { title: "Privacy review", marker: "data-privacy-review", body: "Mask child-safe text by default and keep private details out of diagnostics, logs, and exports." },
  { title: "Review history", marker: "data-review-history", body: "History remains append-only in meaning, even when corrections or added context are recorded." },
  { title: "Child-focused packet", marker: "data-child-focused-packet", body: "Exports are review-required, hash-bound, and ready for a human review step before reuse." },
];

export default function ChildContinuity() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="child-continuity-title"
      style={{
        minHeight: "100vh",
        padding: "2rem 1.25rem 3rem",
        color: "#f3f6ff",
        background:
          "radial-gradient(circle at top right, rgba(112, 171, 255, 0.22), transparent 34%), radial-gradient(circle at bottom left, rgba(75, 200, 165, 0.18), transparent 34%), linear-gradient(180deg, #0b1020 0%, #121a31 48%, #09101d 100%)",
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.12)",
            background: "rgba(10, 17, 32, 0.88)",
            boxShadow: "0 30px 72px rgba(0,0,0,0.36)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.6rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(75, 200, 165, 0.18)", color: "#9fe9d7" }}>Local-only</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(112, 171, 255, 0.18)", color: "#d8e5ff" }}>Encrypted child workspace</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 194, 92, 0.16)", color: "#ffe4bb" }}>Review required</span>
          </div>
          <h1 id="child-continuity-title" style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3.5rem)", lineHeight: 1.03 }}>
            Child-Centered Continuity and Logistics
          </h1>
          <p style={{ maxWidth: 930, marginTop: "0.9rem", lineHeight: 1.7, color: "#c8d3ef" }}>
            Track child profile data, school and care continuity, routines, transportation, contact patterns, appointment ledgers, and review-ready exports from one shipped desktop workflow.
          </p>
          <p style={{ margin: 0, color: "#aec0e6" }}>
            No custody score, no diagnosis, and no parent ranking appear anywhere in this workspace.
          </p>
        </header>

        <section aria-label="Workspace promise" data-child-safe-alias="visible" data-child-masking="visible" style={{ display: "grid", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Workspace promise</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.9rem" }}>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Child-safe alias</strong>
              <p style={{ marginBottom: 0, color: "#d0d9f0", lineHeight: 1.6 }}>The default view shows a safe alias and masks sensitive fields until a reviewer explicitly opens the protected record.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Source-linked facts</strong>
              <p style={{ marginBottom: 0, color: "#d0d9f0", lineHeight: 1.6 }}>Every event, claim, and contradiction stays tied to a source span or is labeled user-entered for audit clarity.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Review-required exports</strong>
              <p style={{ marginBottom: 0, color: "#d0d9f0", lineHeight: 1.6 }}>Packets and receipts are hash-bound so the child continuity record can be verified before reuse or sharing.</p>
            </article>
          </div>
        </section>

        <section aria-label="Child profile" data-child-profile="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Child overview</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa" }}>
              Keep the profile local, encrypted, and masked. The shipped desktop app can create the child record, update it, and return a safe summary without exposing private details in diagnostics.
            </p>
            <ul>
              <li>data-child-safe-alias</li>
              <li>data-child-masking</li>
              <li>data-review-status</li>
            </ul>
          </article>
        </section>

        <section aria-label="Health and care" data-health-care="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Health and care</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Medical and behavioral-care items stay descriptive, source-grounded, and review-required. The workbench shows scheduled, attended, missed, and rescheduled records without providing medical advice or conclusions about compliance.
            </p>
            <p style={{ marginBottom: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Provider names, diagnoses, and medication references remain privacy-reviewed and masked unless a reviewer explicitly approves a fuller view.
            </p>
          </article>
        </section>

        <section aria-label="Continuity sections" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Continuity sections</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {profileSections.map((section) => (
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

        <section aria-label="Workflow receipt" data-child-focused-packet="visible" style={{ display: "grid", gap: "0.9rem" }}>
          <h2 style={{ margin: 0 }}>Workflow receipt</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)" }}>
            <p style={{ marginTop: 0, color: "#d0d9f0", lineHeight: 1.65 }}>
              The packet export keeps the child continuity build hash, manifest hash, and receipt hash linked together so review can reopen the exact version later.
            </p>
            <p style={{ marginBottom: 0, color: "#aac0ef" }}>
              Accessible keyboard navigation, visible focus, and clear status text are preserved in the shipped desktop shell.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}

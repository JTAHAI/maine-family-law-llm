const readinessRows = [
  ["Admission", "Review required"],
  ["Fallback", "Deterministic"],
  ["Runtime", "Loopback-only"],
  ["Model root", "External"],
];

const sections = [
  {
    title: "Hardware Readiness",
    body: "Shows local CPU, memory, disk, and GPU hints before a model worker is admitted or benchmarked.",
    marker: "data-hardware-profile",
  },
  {
    title: "Model Registry",
    body: "Lists candidate, admitted, quarantined, rejected, and superseded records with lineage, hash, license, and provenance.",
    marker: "data-model-registry",
  },
  {
    title: "Role Permissions",
    body: "Shows which worker roles are permitted, which tasks are prohibited, and where certification stays outside model control.",
    marker: "data-role-permissions",
  },
  {
    title: "Benchmark Runner",
    body: "Captures benchmark evidence, resource estimates, and regression history without auto-admitting an unmeasured worker.",
    marker: "data-benchmark-runner",
  },
  {
    title: "Routing and Fallbacks",
    body: "Explains safe routing, exact lookup, and deterministic fallback when no admitted model should be used.",
    marker: "data-routing-fallbacks",
  },
  {
    title: "Health and Failures",
    body: "Surfaces health checks, degraded states, refusals, and failures with the exact reason visible to the operator.",
    marker: "data-health-failures",
  },
  {
    title: "Storage and Cache",
    body: "Shows the external model root, cache, benchmark, and quarantine paths while keeping them outside the repo and MSIX.",
    marker: "data-storage-cache",
  },
  {
    title: "Quarantine and Removal",
    body: "Records quarantine, rejection, and removal-style actions without mutating previous history or evidence.",
    marker: "data-quarantine-removal",
  },
  {
    title: "Degraded Modes",
    body: "Makes no-model mode, low-memory mode, and reduced-capability mode explicit instead of silently falling back.",
    marker: "data-degraded-modes",
  },
  {
    title: "Admission History",
    body: "Preserves an append-only admission trail with reviewer, reason, benchmark, and health history visible for audit.",
    marker: "data-admission-history",
  },
];

export default function LocalIntelligenceControlCenter() {
  return (
    <main
      data-review-status="review_required"
      data-local-intelligence-control-center="visible"
      aria-labelledby="local-intelligence-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f6f7fb",
        background:
          "radial-gradient(circle at top left, rgba(125, 92, 255, 0.22), transparent 36%), radial-gradient(circle at top right, rgba(23, 185, 178, 0.2), transparent 32%), linear-gradient(180deg, #0d1220 0%, #11182a 42%, #0a1020 100%)",
      }}
    >
      <div style={{ maxWidth: 1240, margin: "0 auto" }}>
        <header
          style={{
            display: "grid",
            gap: "1rem",
            marginBottom: "1.25rem",
            padding: "1.5rem",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 24,
            background: "rgba(14, 20, 36, 0.78)",
            boxShadow: "0 24px 80px rgba(0, 0, 0, 0.35)",
            backdropFilter: "blur(14px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(23, 185, 178, 0.18)", color: "#9ff3ed" }}>
              Local-only control
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(125, 92, 255, 0.18)", color: "#d8cdff" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 159, 67, 0.18)", color: "#ffd7a8" }}>
              External model root
            </span>
          </div>
          <div>
            <h1 id="local-intelligence-title" style={{ fontSize: "clamp(2rem, 4vw, 3.5rem)", lineHeight: 1.02, margin: 0 }}>
              Local Intelligence Control Center
            </h1>
            <p style={{ maxWidth: 820, marginTop: "0.85rem", fontSize: "1.05rem", lineHeight: 1.6, color: "#c8d0e8" }}>
              Manage the external model store, inspect hardware readiness, admit or quarantine workers, and keep safe deterministic fallback routing visible before any local model is used.
            </p>
          </div>
          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "0.75rem",
              margin: 0,
            }}
          >
            {readinessRows.map(([label, value]) => (
              <div key={label} style={{ padding: "0.9rem 1rem", borderRadius: 18, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <dt style={{ fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#91a0c2" }}>{label}</dt>
                <dd style={{ margin: "0.3rem 0 0", fontSize: "1rem", fontWeight: 600 }}>{value}</dd>
              </div>
            ))}
          </dl>
        </header>

        <section
          aria-label="Control center sections"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
            gap: "1rem",
            marginBottom: "1rem",
          }}
        >
          {sections.map((section) => (
            <article
              key={section.title}
              data-review-status="review_required"
              data-testid={section.marker}
              style={{
                minHeight: 190,
                padding: "1.2rem",
                borderRadius: 22,
                border: "1px solid rgba(255,255,255,0.1)",
                background: "linear-gradient(180deg, rgba(22,30,54,0.88), rgba(14,18,32,0.9))",
                boxShadow: "0 16px 44px rgba(0,0,0,0.24)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.6rem", fontSize: "1.1rem" }}>{section.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.65, color: "#c9d4ee" }}>{section.body}</p>
            </article>
          ))}
        </section>

        <section
          aria-label="Guardrails"
          data-blocked-export-explanation="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 22,
            background: "linear-gradient(90deg, rgba(255, 159, 67, 0.16), rgba(255, 255, 255, 0.04))",
            border: "1px solid rgba(255, 203, 137, 0.24)",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Guardrails</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.7, color: "#f3eadf" }}>
            <li>Model artifacts stay outside the repo, MSIX payload, and matter directories.</li>
            <li>Certification and filing-readiness gates remain deterministic and cannot be self-certified by a model.</li>
            <li>Quarantine, rejection, and fallback states are visible before a model is admitted to production routing.</li>
            <li>Health checks, benchmark history, and admission history stay reviewable with exact hashes and no private prompt logs.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

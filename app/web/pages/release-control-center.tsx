const statusCards = [
  {
    title: "Local observability",
    body: "Privacy-safe telemetry, bounded metric rows, and hash-chained logs stay local-only. Nothing here substitutes for a live production SLO dashboard.",
  },
  {
    title: "Accessibility",
    body: "The release dashboard keeps semantic sections, visible headings, and marker-based checks so keyboard and screen-reader review remain auditable.",
  },
  {
    title: "Supply chain",
    body: "Source SBOM, release manifest, and external evidence stay separated so source packaging is visible without pretending to be release approval.",
  },
  {
    title: "Ship gates",
    body: "Release candidate, shipment readiness, WACK/signing, and red-team evidence all remain fail-closed until the underlying proof exists.",
  },
];

const evidenceRows = [
  ["SBOM", "Source-only"],
  ["Vulns", "Grype / pip-audit / Semgrep"],
  ["MSIX", "Signing + WACK evidence"],
  ["Pilot", "Attorney sandbox + feedback"],
];

const blockers = [
  "Missing release evidence leaves the ship gate blocked.",
  "A passing dashboard never substitutes for actual Store approval or GA shipment.",
  "Release metrics remain review-required until measured evidence replaces policy targets.",
];

export default function ReleaseControlCenter() {
  return (
    <main
      data-review-status="review_required"
      data-release-control-center="visible"
      aria-labelledby="release-control-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f7f3ed",
        background:
          "radial-gradient(circle at top left, rgba(252, 163, 17, 0.23), transparent 34%), radial-gradient(circle at top right, rgba(56, 189, 248, 0.2), transparent 30%), radial-gradient(circle at bottom right, rgba(45, 212, 191, 0.12), transparent 28%), linear-gradient(180deg, #130f13 0%, #161b22 46%, #0a0e14 100%)",
        fontFamily: '"Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif',
      }}
    >
      <div style={{ maxWidth: 1280, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 30,
            border: "1px solid rgba(255,255,255,0.09)",
            background: "rgba(12, 16, 23, 0.84)",
            boxShadow: "0 28px 80px rgba(0,0,0,0.38)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(56, 189, 248, 0.16)", color: "#bdefff" }}>
              Local observability
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(252, 163, 17, 0.16)", color: "#ffe0a8" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(45, 212, 191, 0.14)", color: "#c5fff5" }}>
              Fail closed
            </span>
          </div>
          <h1 id="release-control-title" style={{ margin: 0, fontSize: "clamp(2.2rem, 4.5vw, 4rem)", lineHeight: 1.01 }}>
            Release Control Center
          </h1>
          <p style={{ maxWidth: 900, marginTop: "0.9rem", lineHeight: 1.68, color: "#d8d0c4", fontSize: "1.03rem" }}>
            A single operator view for observability, accessibility, SBOM and vulnerability evidence, MSIX signing and WACK audits, pilot feedback, red-team results, release metrics, and fail-closed ship gates.
          </p>
          <dl
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "0.75rem",
              margin: "1.2rem 0 0",
            }}
          >
            {evidenceRows.map(([label, value]) => (
              <div key={label} style={{ padding: "0.95rem 1rem", borderRadius: 18, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <dt style={{ fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#9fb0c9" }}>{label}</dt>
                <dd style={{ margin: "0.35rem 0 0", fontSize: "1rem", fontWeight: 650 }}>{value}</dd>
              </div>
            ))}
          </dl>
        </header>

        <nav aria-label="Release control sections" style={{ padding: "1rem 1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <ul style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem 1.2rem", margin: 0, paddingLeft: "1.1rem", lineHeight: 1.6 }}>
            <li><a href="#observability">Observability</a></li>
            <li><a href="#accessibility">Accessibility</a></li>
            <li><a href="#supply-chain">Supply Chain</a></li>
            <li><a href="#vulnerability-evidence">Vulnerability Evidence</a></li>
            <li><a href="#msix-audit">MSIX / Store Audit</a></li>
            <li><a href="#metrics-gates">Metrics Gates</a></li>
            <li><a href="#pilot-evidence">Pilot Evidence</a></li>
            <li><a href="#red-team">Red Team</a></li>
            <li><a href="#ship-blockers">Blockers</a></li>
          </ul>
        </nav>

        <section
          aria-label="Release control overview"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
          }}
        >
          {statusCards.map((card) => (
            <article
              key={card.title}
              style={{
                minHeight: 188,
                padding: "1.15rem",
                borderRadius: 22,
                border: "1px solid rgba(255,255,255,0.09)",
                background: "linear-gradient(180deg, rgba(27, 32, 41, 0.96), rgba(12, 15, 21, 0.98))",
                boxShadow: "0 18px 44px rgba(0,0,0,0.24)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.55rem", fontSize: "1.08rem" }}>{card.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.68, color: "#d7d0c7" }}>{card.body}</p>
            </article>
          ))}
        </section>

        <section id="observability" aria-labelledby="observability-title" data-release-observability="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="observability-title" style={{ margin: 0 }}>Observability and SLOs</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#e5ddd1" }}>
              Local telemetry stays privacy-safe, bounded, and hash chained. SLOs are shown as measured evidence when it exists, not as a promise that production capacity is already green.
            </p>
            <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f2e8d8" }}>
              <li>API, retrieval, drafting, and uptime thresholds remain visible next to the evidence they depend on.</li>
              <li>Large matter performance stays review-required until actual measurements replace offline targets.</li>
              <li>Crash, chaos, and restore drills are surfaced as separate evidence, not as implied readiness.</li>
            </ul>
          </article>
        </section>

        <section id="accessibility" aria-labelledby="accessibility-title" data-release-accessibility="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="accessibility-title" style={{ margin: 0 }}>Accessibility pass</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "linear-gradient(180deg, rgba(56, 189, 248, 0.08), rgba(255,255,255,0.03))", border: "1px solid rgba(148, 208, 255, 0.16)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#e4eef8" }}>
              The page keeps semantic landmarks, descriptive headings, visible contrast, and explicit marker attributes so keyboard and screen-reader review stay testable.
            </p>
            <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f0f7ff" }}>
              <li>Navigation is anchor-based and sectioned for fast scanning.</li>
              <li>Review-required state remains visible at the top and in the body copy.</li>
              <li>No accessibility claim is made without the contract markers present in the page source.</li>
            </ul>
          </article>
        </section>

        <section id="supply-chain" aria-labelledby="supply-chain-title" data-release-supply-chain="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="supply-chain-title" style={{ margin: 0 }}>Supply chain evidence</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            <article style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Source SBOM</h3>
              <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#d9d3c9" }}>
                Source-only SBOM output stays separate from the actual Store package evidence so the dashboard can show provenance without pretending to sign anything.
              </p>
            </article>
            <article style={{ padding: "1.1rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <h3 style={{ marginTop: 0 }}>Release manifest</h3>
              <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#d9d3c9" }}>
                Packaging hygiene remains visible through the manifest scan for private data, runtime state, and other blocked artifacts.
              </p>
            </article>
          </div>
        </section>

        <section id="vulnerability-evidence" aria-labelledby="vulnerability-title" data-release-vulnerability-evidence="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="vulnerability-title" style={{ margin: 0 }}>Vulnerability adjudication</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#ddd7cc" }}>
              Grype, pip-audit, and Semgrep results remain individually visible so the control center can show what was checked, what failed, and why the ship gate stays closed.
            </p>
          </article>
        </section>

        <section id="msix-audit" aria-labelledby="msix-title" data-release-msix-audit="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="msix-title" style={{ margin: 0 }}>MSIX and Store audit</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "linear-gradient(90deg, rgba(252, 163, 17, 0.12), rgba(255,255,255,0.03))", border: "1px solid rgba(255, 205, 132, 0.22)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#f1e5d4" }}>
              Signing, x64 package identity, install-launch-uninstall smoke tests, and WACK results are shown as evidence-only fields. Store approval still depends on the external audit trail.
            </p>
          </article>
        </section>

        <section id="metrics-gates" aria-labelledby="metrics-title" data-release-metrics-gates="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="metrics-title" style={{ margin: 0 }}>Release metric gates</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <ul style={{ marginTop: 0, marginBottom: 0, lineHeight: 1.75, color: "#e8dfd2" }}>
              <li>Measured SLO thresholds stay separate from policy targets.</li>
              <li>Failing metrics are shown as blockers, not as hidden operator notes.</li>
              <li>Release eligibility remains review-required until the measured evidence is attached.</li>
            </ul>
          </article>
        </section>

        <section id="pilot-evidence" aria-labelledby="pilot-title" data-release-pilot-evidence="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="pilot-title" style={{ margin: 0 }}>Attorney sandbox pilot evidence</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#ddd8cf" }}>
              Feedback, eligibility, session history, and review-required export flags remain visible for the pilot. Real matter use stays blocked.
            </p>
          </article>
        </section>

        <section id="red-team" aria-labelledby="red-team-title" data-release-red-team="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 id="red-team-title" style={{ margin: 0 }}>Red-team pack</h2>
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, lineHeight: 1.72, color: "#ddd7cc" }}>
              False premises, fake citations, prompt injection, stale law, jurisdiction mismatch, confidentiality leakage, and filing-ready bypass attempts stay in the testing frame until each case is proven safe.
            </p>
          </article>
        </section>

        <section
          id="ship-blockers"
          aria-labelledby="blockers-title"
          data-release-blockers="visible"
          data-blocked-export-explanation="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(255, 193, 109, 0.2)",
            background: "linear-gradient(180deg, rgba(255, 184, 77, 0.12), rgba(255,255,255,0.03))",
          }}
        >
          <h2 id="blockers-title" style={{ marginTop: 0 }}>Blockers</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f5ead6" }}>
            {blockers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

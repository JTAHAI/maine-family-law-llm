const controlCards = [
  {
    title: "Matter encryption",
    body: "Matter metadata and document payloads stay inside encrypted envelopes, and the dashboard refuses to treat legacy plaintext artifacts as acceptable.",
  },
  {
    title: "Role separation",
    body: "Admin, attorney, reviewer, and viewer permissions stay distinct so read, write, export, and incident actions cannot silently collapse into one role.",
  },
  {
    title: "Prompt-defense",
    body: "Prompt, document, and tool-injection checks run through an allowlist and output filter before any response can claim to be safe.",
  },
  {
    title: "Incident handling",
    body: "Incidents are opened, closed, and audited with hash-chained records, and restore operations stay rehearsal-only until a reviewer approves them.",
  },
  {
    title: "Session capability",
    body: "Sensitive actions use short-lived scoped capability tokens and CSRF checks instead of trusting a bare browser session.",
  },
  {
    title: "Emergency controls",
    body: "Revoke, rollback, and lock-recovery controls stay visible so operators can contain a compromised session without touching originals.",
  },
];

const metrics = [
  ["Storage", "Encrypted envelope"],
  ["Audit", "Hash chained"],
  ["Restore", "Rehearsal only"],
  ["Deletion", "Policy bound"],
];

const layers = [
  "Encrypted matter root",
  "Role-scoped access checks",
  "Signed session capability token",
  "Prompt/document/tool sandboxing",
  "Immutable audit and incident chain",
  "Redacted diagnostics and retention review",
  "Restore preview and rollback receipt",
];

export default function SecurityPrivacyCenter() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="security-privacy-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f6f3ec",
        background:
          "radial-gradient(circle at top left, rgba(255, 174, 84, 0.22), transparent 34%), radial-gradient(circle at top right, rgba(52, 211, 153, 0.18), transparent 32%), linear-gradient(180deg, #111015 0%, #17191f 44%, #0b0f14 100%)",
      }}
    >
      <div style={{ maxWidth: 1220, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 28,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "rgba(16, 18, 26, 0.86)",
            boxShadow: "0 28px 70px rgba(0,0,0,0.4)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(52, 211, 153, 0.18)", color: "#9df4cd" }}>
              Matter encrypted
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 174, 84, 0.18)", color: "#ffd5a1" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(147, 197, 253, 0.16)", color: "#d6e8ff" }}>
              Hash chained audit
            </span>
          </div>
          <h1 id="security-privacy-title" style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3.7rem)", lineHeight: 1.02 }}>
            Security & Privacy Fortress
          </h1>
          <p style={{ maxWidth: 860, marginTop: "0.9rem", lineHeight: 1.65, color: "#d7d0c7" }}>
            Keep matter-level encryption, role separation, prompt-injection defense, audit integrity, backup/restore rehearsal, retention, and incident controls visible in one fail-closed place.
          </p>
        </header>

        <section
          aria-label="Security controls"
          data-security-controls="visible"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
          }}
        >
          {controlCards.map((card) => (
            <article
              key={card.title}
              style={{
                minHeight: 188,
                padding: "1.15rem",
                borderRadius: 22,
                border: "1px solid rgba(255,255,255,0.1)",
                background: "linear-gradient(180deg, rgba(31, 34, 43, 0.94), rgba(18, 20, 28, 0.96))",
                boxShadow: "0 18px 44px rgba(0,0,0,0.24)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.6rem", fontSize: "1.08rem" }}>{card.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.65, color: "#d7d3cd" }}>{card.body}</p>
            </article>
          ))}
        </section>

        <section
          aria-label="Matter encryption"
          data-matter-encryption="visible"
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(280px, 1.2fr) minmax(220px, 0.8fr)",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.2rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Encrypted matter root</h2>
            <p style={{ lineHeight: 1.7, color: "#ddd6cb" }}>
              The store layer writes matter metadata as encrypted envelopes, keeps document payloads encrypted at rest, and treats plaintext legacy artifacts as a blocker.
            </p>
            <ol style={{ marginBottom: 0, lineHeight: 1.8, color: "#efe8db" }}>
              {layers.map((layer) => (
                <li key={layer}>{layer}</li>
              ))}
            </ol>
          </article>
          <dl style={{ display: "grid", gap: "0.75rem", margin: 0 }}>
            {metrics.map(([label, value]) => (
              <div
                key={label}
                style={{
                  padding: "0.95rem 1rem",
                  borderRadius: 18,
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <dt style={{ fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#b7ad9f" }}>{label}</dt>
                <dd style={{ margin: "0.3rem 0 0", fontSize: "1rem", fontWeight: 600 }}>{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section
          aria-label="Audit integrity"
          data-audit-integrity="visible"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Hash-chained audit</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#ddd8cf" }}>
              Every security event is chained to the previous hash so tampering, truncation, or insertion becomes visible.
            </p>
          </article>
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Redacted diagnostics</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#ddd8cf" }}>
              Diagnostic payloads are sanitized before display so paths, credentials, and matter content do not leak into the operator console.
            </p>
          </article>
        </section>

        <section
          aria-label="Backup and restore"
          data-backup-restore="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(255,255,255,0.1)",
            background: "linear-gradient(90deg, rgba(52, 211, 153, 0.12), rgba(255,255,255,0.04))",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Backup and restore</h2>
          <p style={{ marginTop: 0, lineHeight: 1.7, color: "#efe9de" }}>
            Matter backups are hashed and restore is rehearsed against an isolated copy before any recovery path can be treated as trusted.
          </p>
        </section>

        <section
          aria-label="Retention"
          data-retention-controls="visible"
          style={{
            display: "grid",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Retention controls</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#dcd6cc" }}>
              Retention decisions stay tied to the configured data class, and deletion actions can be documented without exposing the underlying content.
            </p>
          </article>
        </section>

        <section
          aria-label="Incident controls"
          data-incident-controls="visible"
          style={{
            display: "grid",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Incident controls</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#dcd6cc" }}>
              Incident open, close, and escalation records remain review-required and hash chained, with emergency revocation surfaced as a distinct action.
            </p>
          </article>
        </section>

        <section
          aria-label="Session capability"
          data-session-capability="visible"
          style={{
            display: "grid",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Session capability</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#dcd6cc" }}>
              Backup, restore, incident, and emergency controls require a short-lived scoped capability and CSRF token so the local API can reject unauthenticated reuse.
            </p>
          </article>
        </section>

        <section
          aria-label="Lock and recovery"
          data-lock-recovery="visible"
          style={{
            display: "grid",
            gap: "1rem",
          }}
        >
          <article style={{ padding: "1.15rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <h2 style={{ marginTop: 0 }}>Lock and recovery</h2>
            <p style={{ marginBottom: 0, lineHeight: 1.7, color: "#dcd6cc" }}>
              Matter locks, stale-lock recovery, and restore previews make concurrent edits and rollback preparation visible instead of silent.
            </p>
          </article>
        </section>

        <section
          aria-label="Injection defense"
          data-injection-defense="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            background: "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Injection defense</h2>
          <p style={{ marginTop: 0, lineHeight: 1.7, color: "#ddd8cf" }}>
            Prompt, document, and tool-injection defenses stay isolated from the response path, so untrusted text cannot become policy or capability.
          </p>
        </section>

        <section
          data-blocked-export-explanation="visible"
          style={{
            padding: "1.2rem",
            borderRadius: 22,
            background: "rgba(255, 174, 84, 0.12)",
            border: "1px solid rgba(255, 213, 161, 0.2)",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Guardrails</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f3e6d3" }}>
            <li>Legacy plaintext matter metadata is treated as a blocker, not as a safe fallback.</li>
            <li>Restore is rehearsal-only until a reviewer approves it.</li>
            <li>Audit, incident, and diagnostics views stay review-required and redacted by default.</li>
            <li>Emergency revoke is a distinct action rather than a hidden side effect.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

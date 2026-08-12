import { useEffect, useState } from "react";

const sections = [
  {
    title: "Release pilot hardening",
    marker: "data-release-pilot-hardening",
    body: "Status, observability, backup rehearsal, and pilot feedback remain review-required and local-only until the underlying evidence passes.",
  },
  {
    title: "Attorney sandbox operations",
    marker: "data-attorney-sandbox-operations",
    body: "Programs, cohorts, assignments, reviews, triage, and evidence builds stay synthetic-only and preserve an immutable review trail.",
  },
  {
    title: "Limited real-matter pilot",
    marker: "data-limited-real-matter-pilot",
    body: "Tenant allowlists, explicit consent, no-training-use controls, daily reviews, export gating, incidents, and signoffs remain visible.",
  },
  {
    title: "GA release candidate",
    marker: "data-ga-release-candidate",
    body: "Release candidate freeze, blockers, signoffs, and evidence packet generation remain separate from any shipment claim.",
  },
  {
    title: "GA shipment readiness",
    marker: "data-ga-shipment-readiness",
    body: "Shipment channels, controls, rollback evidence, and release-channel qualification stay fail-closed until the evidence exists.",
  },
  {
    title: "Feedback to gold loop",
    marker: "data-feedback-loop",
    body: "Feedback can be collected, triaged, and turned into corrective work, but no review path silently promotes unvetted work to gold.",
  },
  {
    title: "Rollback and support bundle",
    marker: "data-support-bundle",
    body: "Rollback preparation, backup/restore rehearsal, and operator support bundles stay visible without exposing private matter content or raw paths.",
  },
];

const monitoredEndpoints = [
  { key: "releasePilot", label: "Release pilot", endpoint: "/api/release-pilot-hardening/status" },
  { key: "sandboxOps", label: "Sandbox operations", endpoint: "/api/attorney-sandbox-operations/status" },
  { key: "realMatter", label: "Real-matter pilot", endpoint: "/api/limited-real-matter-pilot/status" },
  { key: "releaseCandidate", label: "Release candidate", endpoint: "/api/ga-release-candidate/status" },
  { key: "shipment", label: "Shipment readiness", endpoint: "/api/ga-shipment-readiness/status" },
];

type SnapshotMap = Record<string, any>;

function StatusCard({ label, endpoint, data }: { label: string; endpoint: string; data: any }) {
  const status = String(data?.status || "unknown");
  const blockers = Array.isArray(data?.blockers) ? data.blockers.length : 0;
  return (
    <article
      style={{
        padding: "1rem 1.05rem",
        borderRadius: 18,
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.04)",
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: "0.45rem", fontSize: "1rem" }}>{label}</h3>
      <p style={{ margin: 0, lineHeight: 1.55, color: "#d5d8e6" }}>
        <strong>Status:</strong> {status}
        <br />
        <strong>Blockers:</strong> {blockers}
        <br />
        <span style={{ opacity: 0.82 }}>{endpoint}</span>
      </p>
    </article>
  );
}

export default function MaintenanceCenter() {
  const [snapshot, setSnapshot] = useState<SnapshotMap>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    try {
      const responses = await Promise.all(
        monitoredEndpoints.map(async (item) => {
          const response = await fetch(item.endpoint, {
            credentials: "same-origin",
            headers: { "X-User-Role": "admin", "X-Tenant-Id": "tenant-maintenance" },
            signal: controller.signal,
          });
          const payload = await response.json();
          return [item.key, payload] as const;
        }),
      );
      setSnapshot(Object.fromEntries(responses));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh maintenance status.");
    } finally {
      setLoading(false);
    }
    return () => controller.abort();
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <main
      data-review-status="review_required"
      data-release-maintenance-center="visible"
      aria-labelledby="maintenance-center-title"
      style={{
        minHeight: "100vh",
        padding: "3rem 1.5rem 4rem",
        color: "#f8f5ef",
        background:
          "radial-gradient(circle at top left, rgba(100, 181, 246, 0.18), transparent 32%), radial-gradient(circle at top right, rgba(255, 183, 77, 0.16), transparent 30%), linear-gradient(180deg, #0f1218 0%, #151c2a 46%, #090c12 100%)",
        fontFamily: '"Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif',
      }}
    >
      <div style={{ maxWidth: 1320, margin: "0 auto", display: "grid", gap: "1rem" }}>
        <header
          style={{
            padding: "1.5rem",
            borderRadius: 30,
            border: "1px solid rgba(255,255,255,0.09)",
            background: "rgba(12, 16, 24, 0.86)",
            boxShadow: "0 28px 80px rgba(0,0,0,0.38)",
            backdropFilter: "blur(16px)",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.65rem", marginBottom: "0.9rem" }}>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(100, 181, 246, 0.16)", color: "#c8ecff" }}>
              Local-only operations
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 183, 77, 0.16)", color: "#ffe1ac" }}>
              Review required
            </span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(46, 204, 113, 0.14)", color: "#c8ffd9" }}>
              Fail closed
            </span>
          </div>
          <h1 id="maintenance-center-title" style={{ margin: 0, fontSize: "clamp(2.2rem, 4.5vw, 4rem)", lineHeight: 1.01 }}>
            Release Maintenance Center
          </h1>
          <p style={{ maxWidth: 920, marginTop: "0.9rem", lineHeight: 1.68, color: "#d9d2c5", fontSize: "1.03rem" }}>
            Keep the shipped desktop on one operator screen for pilot hardening, synthetic attorney review, limited real-matter controls, release candidate freeze, and shipment readiness.
          </p>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => void refresh()}
              style={{
                padding: "0.75rem 1rem",
                borderRadius: 14,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(255,255,255,0.08)",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              Refresh status
            </button>
            <span aria-live="polite" style={{ alignSelf: "center", color: "#d6e3f3" }}>
              {loading ? "Refreshing maintenance snapshot..." : "Snapshot ready"}
            </span>
          </div>
          {error ? (
            <p role="alert" style={{ marginTop: "0.85rem", color: "#ffccbc" }}>
              {error}
            </p>
          ) : null}
        </header>

        <section
          aria-label="Maintenance snapshot"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "1rem",
          }}
        >
          {monitoredEndpoints.map((item) => (
            <StatusCard key={item.key} label={item.label} endpoint={item.endpoint} data={snapshot[item.key]} />
          ))}
        </section>

        <section
          aria-label="Maintenance workstreams"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
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
                background: "linear-gradient(180deg, rgba(28, 34, 47, 0.96), rgba(12, 15, 20, 0.98))",
                boxShadow: "0 18px 44px rgba(0,0,0,0.24)",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: "0.55rem", fontSize: "1.08rem" }}>{section.title}</h2>
              <p style={{ margin: 0, lineHeight: 1.68, color: "#d8d2c7" }}>{section.body}</p>
            </article>
          ))}
        </section>

        <section
          aria-label="Maintenance notes"
          data-feedback-loop="visible"
          data-support-bundle="visible"
          style={{
            padding: "1.25rem",
            borderRadius: 24,
            border: "1px solid rgba(255, 193, 109, 0.2)",
            background: "linear-gradient(180deg, rgba(255, 184, 77, 0.12), rgba(255,255,255,0.03))",
          }}
        >
          <h2 style={{ marginTop: 0 }}>Operator notes</h2>
          <ul style={{ marginBottom: 0, lineHeight: 1.75, color: "#f5ead6" }}>
            <li>Feedback can be captured and triaged, but no path silently promotes a model, matter, or release candidate to gold.</li>
            <li>Rollback preparation, backup rehearsal, and support bundles remain separate from package identity and public evidence.</li>
            <li>Maintenance diagnostics avoid raw private paths and keep the latest review-required state visible to the operator.</li>
          </ul>
        </section>
      </div>
    </main>
  );
}

const sections = [
  {
    title: "Media inventory",
    marker: "data-media-inventory",
    body: "Import audio and video records with exact hashes, duplicate groups, recording metadata, and an immutable original-media policy.",
  },
  {
    title: "Transcript viewer",
    marker: "data-transcript-viewer",
    body: "Show the derived transcript beside the verified media record, with line-by-line spans and a clear review-required status.",
  },
  {
    title: "Speaker review",
    marker: "data-speaker-review",
    body: "Apply manual speaker labels only. No biometric identity inference, emotion detection, or deception analysis is used or implied.",
  },
  {
    title: "Hearing timeline",
    marker: "data-hearing-timeline",
    body: "Build a timestamped hearing chronology from exact transcript segments without collapsing objections, rulings, recesses, or exhibits.",
  },
  {
    title: "Transcript comparison",
    marker: "data-transcript-comparison",
    body: "Compare an official transcript with the derived transcript and keep matches, changes, omissions, and line spans visible.",
  },
  {
    title: "Exhibit references",
    marker: "data-exhibit-references",
    body: "Mentioning an exhibit does not prove admission. The workbench keeps mentioned, missing, and ambiguous references separate.",
  },
  {
    title: "Appellate record completeness",
    marker: "data-appellate-record-completeness",
    body: "Show whether the transcript, speaker review, timeline, exhibits, citations, privacy review, and redacted derivative are present.",
  },
  {
    title: "Record citations",
    marker: "data-record-citations",
    body: "Citation rows stay tied to exact spans and unresolved citations block export until a reviewer resolves them.",
  },
  {
    title: "Privacy redaction",
    marker: "data-privacy-redaction",
    body: "A redacted derivative is created separately from the original transcript and original media, with a distinct receipt and hash.",
  },
  {
    title: "Review history",
    marker: "data-review-history",
    body: "Append-only history preserves speaker changes, citation updates, timeline builds, privacy scans, and export events.",
  },
  {
    title: "Export receipt",
    marker: "data-export-receipt",
    body: "Exports are review-required, hash-bound, and tied to the exact media, transcript, and redaction state.",
  },
];

export default function HearingMediaWorkbench() {
  return (
    <main
      data-review-status="review_required"
      aria-labelledby="hearing-media-workbench-title"
      style={{
        minHeight: "100vh",
        padding: "2rem 1.25rem 3rem",
        color: "#f6f7ff",
        background:
          "radial-gradient(circle at top left, rgba(110, 192, 255, 0.20), transparent 34%), radial-gradient(circle at bottom right, rgba(255, 170, 92, 0.16), transparent 34%), linear-gradient(180deg, #08101f 0%, #121d34 46%, #07111c 100%)",
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
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(110, 192, 255, 0.18)", color: "#dceaff" }}>Local-only</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(255, 170, 92, 0.18)", color: "#ffe4bf" }}>Review required</span>
            <span style={{ padding: "0.35rem 0.7rem", borderRadius: 999, background: "rgba(120, 225, 190, 0.16)", color: "#c7f4e4" }}>Hash-bound exports</span>
          </div>
          <h1 id="hearing-media-workbench-title" style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3.5rem)", lineHeight: 1.03 }}>
            Hearing Media and Record Review
          </h1>
          <p style={{ maxWidth: 980, marginTop: "0.9rem", lineHeight: 1.7, color: "#cad5f2" }}>
            Work with local audio and video records, derived transcripts, speaker labels, hearing timelines, exhibit references, appellate record completeness, citations, privacy redaction, and export receipts in one shipped desktop workflow.
          </p>
          <p style={{ margin: 0, color: "#aebfdf" }}>
            No cloud transcription, no automatic speech-model download, no biometric identity inference, no emotion analysis, and no deception conclusion appear anywhere in this workflow.
          </p>
        </header>

        <section aria-label="Workspace promise" data-hearing-media-workbench="visible" data-blocked-export-explanation="visible" style={{ display: "grid", gap: "0.75rem" }}>
          <h2 style={{ margin: 0 }}>Workspace promise</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.9rem" }}>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Original stays original</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>The source audio or video file remains immutable while the transcript, redaction, and export artifacts are written separately.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Exact spans stay visible</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>Every timeline entry, exhibit reference, and citation carries a precise transcript span or timestamp rather than a hidden summary.</p>
            </article>
            <article style={{ padding: "1rem 1.05rem", borderRadius: 22, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
              <strong>Human review stays explicit</strong>
              <p style={{ marginBottom: 0, color: "#d3ddf4", lineHeight: 1.6 }}>Speaker labels, citation resolution, privacy review, and exports remain review-required instead of silently auto-accepting changes.</p>
            </article>
          </div>
        </section>

        <section aria-label="Transcription controls" data-media-inventory="visible" data-transcript-viewer="visible" data-speaker-review="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Transcription controls</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Imported audio and video rows show the media hash, duplicate group, and transcription status. The transcript viewer shows a derived transcript only after a local review step, and speaker labels are applied manually without biometric identity inference.
            </p>
            <p style={{ marginBottom: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Cancellation is visible, and the shipped UI keeps status text independent of color so the workflow remains accessible and review-friendly.
            </p>
          </article>
        </section>

        <section aria-label="Record analysis" data-hearing-timeline="visible" data-transcript-comparison="visible" data-exhibit-references="visible" style={{ display: "grid", gap: "1rem" }}>
          <h2 style={{ margin: 0 }}>Record analysis</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
            <p style={{ marginTop: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Hearing timeline rows preserve the exact timestamps from the transcript. Comparison with an official transcript keeps matches and differences separate, and exhibit references stay marked as mentions rather than admissions.
            </p>
            <p style={{ marginBottom: 0, color: "#d7e1fa", lineHeight: 1.6 }}>
              Missing exhibits, unresolved citations, and ambiguous references remain visible so the appellate record checklist can block an overconfident export.
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

        <section aria-label="Export receipt" data-appellate-record-completeness="visible" data-record-citations="visible" data-privacy-redaction="visible" data-review-history="visible" data-export-receipt="visible" style={{ display: "grid", gap: "0.9rem" }}>
          <h2 style={{ margin: 0 }}>Export receipt</h2>
          <article style={{ padding: "1.1rem", borderRadius: 24, border: "1px solid rgba(255,255,255,0.1)", background: "rgba(255,255,255,0.04)" }}>
            <p style={{ marginTop: 0, color: "#d0d9f0", lineHeight: 1.65 }}>
              The appellate completeness checklist, citation audit, privacy scan, redacted copy, and export receipt all stay hash-bound to the exact transcript revision that produced them.
            </p>
            <p style={{ marginBottom: 0, color: "#aac0ef" }}>
              The workbench keeps the original media read-only, the transcript derivative separate, and the redacted derivative separately reviewable before any sharing step.
            </p>
          </article>
        </section>
      </div>
    </main>
  );
}

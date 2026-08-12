# Maine Family Law LLM v5.13.0 — Release and Pilot Hardening

v5.13.0 adds a fail-closed local control plane for release evidence and attorney-sandbox operations.

## Supply-chain and MSIX evidence

- Audits external CycloneDX and SPDX SBOMs.
- Audits Grype, pip-audit, and Semgrep JSON reports.
- Requires a signed and verified x64 MSIX for Store qualification.
- Requires install, launch, API health, UI load, uninstall, and reinstall evidence.
- Requires a passing Windows App Certification Kit result.
- Keeps legal GA blocked after package qualification until genuine pilot and signoff evidence exists.

## Privacy-safe local observability

- Accepts only allowlisted event names, enum labels, and numeric measurements.
- Refuses paths, email addresses, SSNs, arbitrary labels, question text, document text, and source excerpts.
- Stores bounded, local, hash-chained metrics.
- Keeps remote exporters disabled.

An optional OpenTelemetry SDK bridge emits only allowlisted numeric metrics and sanitized labels to an in-memory reader. It configures no remote exporter, and the durable hash-chained local log remains authoritative when OpenTelemetry is absent.

## Backup and restore rehearsal

- Creates a content-addressed matter backup outside the source repository and active matter.
- Rejects symlinks, unsafe ZIP names, duplicate entries, excessive file counts, and excessive bytes.
- Verifies every size and SHA-256.
- Restores into an isolated temporary directory, verifies restored hashes, deletes the rehearsal copy, and never mutates the active matter.
- Can write a verified `backup-restore.json` into the external release-evidence root.

## Attorney-only sandbox

- Accepts synthetic or public-authority data only.
- Requires operator-recorded bar-verification evidence, accepted terms, and all training modules before a session begins.
- Refuses private-matter sessions.
- Keeps feedback append-only and hash-chained.
- Feedback may become an evaluation candidate but never attorney gold automatically.
- The application does not independently verify licensing, and workbench records do not count as GA pilot evidence without external audit.

## Developer and operator assets

- Project-specific Semgrep policy.
- PowerShell supply-chain evidence runner.
- Release-evidence audit CLI.
- Backup/restore rehearsal CLI.
- Main-workbench release and pilot modal.

Product version: **5.13.0**. Microsoft Store package target: **5.13.0.0**. UI build: **40**.

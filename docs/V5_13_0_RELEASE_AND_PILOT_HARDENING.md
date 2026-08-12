# v5.13.0 Release and Pilot Hardening

v5.13.0 adds a local control plane for supply-chain evidence, signed-MSIX qualification, privacy-safe metrics, matter backup/restore rehearsals, and attorney-only sandbox operations.

## Evidence, not assertions

The workbench audits external evidence files. It does not create a pass merely because a feature exists. Missing Syft, Grype, pip-audit, Semgrep, signing, install, WACK, backup, or pilot evidence remains a visible blocker.

## Privacy-safe observability

Only allowlisted event names, small enum labels, and numeric measurements are accepted. Questions, document text, filenames, source excerpts, party names, credentials, and paths are refused. Records are local, bounded, and hash-chained; remote exporters are disabled.

An optional OpenTelemetry SDK bridge emits only allowlisted numeric metrics and sanitized labels to an in-memory reader. It configures no remote exporter, and the durable hash-chained local log remains authoritative when OpenTelemetry is absent.

## Backup/restore rehearsal

A drill creates a content-addressed backup outside both the source repository and active matter. It rejects symlinks and unsafe paths, verifies every entry, restores into a temporary isolated directory, verifies restored hashes, deletes the temporary copy, and never mutates the active matter.

## Attorney sandbox

The sandbox accepts only synthetic or public-authority data. Participants need an operator-recorded verification hash, accepted terms, and all training modules before a session can begin. Feedback is append-only and may become an eval candidate, but never attorney gold automatically. The application does not independently verify licensing, and source-workbench records do not count as GA pilot evidence without an external audit.

## Store qualification

Store readiness requires external evidence showing a signed and verified x64 MSIX, successful install/launch/API/UI/uninstall/reinstall checks, passing WACK results, clean vulnerability audits, and a passing backup/restore drill. Legal GA still requires attorney pilot, real-matter pilot, legal, product, security, and operations signoff.

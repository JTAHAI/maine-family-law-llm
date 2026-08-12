# Security & Privacy Fortress

This slice keeps the matter workspace fail-closed around:

- matter metadata and document encryption at rest
- role-separated access checks
- prompt, document, and tool-injection defense
- hash-chained audit and incident records
- encrypted backup and restore rehearsal
- redacted diagnostics
- retention-aware handling and deletion review

Operational notes:

1. Matter metadata is stored as an encrypted envelope, not plaintext.
2. Backup runs are approved, hashed, and verified before restore rehearsal.
3. Restore remains rehearsal-only unless a reviewer explicitly approves the recovery path.
4. Diagnostics are sanitized before they are surfaced in the UI or API.
5. Incidents are logged with tamper-evident records so rollback decisions stay auditable.

Use the `Security & Privacy Fortress` UI for a redacted summary of encryption, audit integrity, backup/restore, retention, and incident state.

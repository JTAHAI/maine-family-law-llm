# Incident and Rollback Runbook

Trigger incident response for data leakage, plaintext matter artifact discovery, unsupported filing-ready export, verifier bypass, security-control failure, stale-law release, source corruption, model regression, prompt injection bypass, or tenant-isolation failure.

Initial response:
1. Freeze exports and pause restore actions.
2. Preserve audit logs, incident logs, and backup manifests.
3. Disable the affected model/source/index/version or matter workspace.
4. Rotate or revoke any credential that touched the incident path.
5. Re-run the security/privacy dashboard, backup verification, and red-team checks.

Rollback steps:
1. Restore only from the last verified archive or signed release package.
2. Verify the hash chain on audit and incident ledgers before resuming service.
3. Confirm that the restored workspace is isolated, encrypted, and review-required.
4. Notify affected tenants with a redacted incident summary.
5. Document root cause, remediation, and re-enable criteria before recovery is declared complete.

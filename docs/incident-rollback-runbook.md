# Incident and Rollback Runbook

Trigger incident response for data leakage, unsupported filing-ready export, verifier bypass, security-control failure, stale-law release, source corruption, model regression, or tenant-isolation failure.

Rollback steps: freeze exports, preserve audit logs, disable affected model/source/index version, restore the last signed release package, rerun release metrics and red-team suites, notify affected tenants, and document root cause before re-enable.

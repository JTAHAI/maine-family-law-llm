# Source Update Runbook

Run official-source ingestion into an external data root, build parsed authority stores, generate freshness and diff reports, rebuild retrieval indexes, rerun evals, and block current-law language for stale or unknown source classes.

No source update is promoted until manifests include source IDs, class, jurisdiction, URL/path, snapshot path, hash, retrieved timestamp, parser audit, parser status, and freshness status.

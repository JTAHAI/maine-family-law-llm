# v5.15.0 Authority Change Impact and Matter Revalidation

v5.15.0 compares two verified immutable external authority generations and maps changed official-source IDs to a saved document and its most recent review packet.

The workbench reports added, removed, content-hash-changed, and lifecycle-metadata-changed sources. A direct overlap with a reviewed source invalidates prior approval for the target generation and creates an explicit revalidation blocker. Court-form source changes and stale or unknown target freshness also remain visible blockers.

A source hash change is a review signal only. The system does not determine legal materiality, negative treatment, or the effect of a change on current Maine law.

Authority-impact packets are deterministic, content-addressed, bound to the exact document revision, and protected by an artifact manifest. Editing the document makes the packet stale and prevents artifact download.

External authority generations remain outside the repository. The feature does not bundle authority data, private matter records, or attorney revalidation evidence.

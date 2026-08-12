# v5.14.0 Reviewed Filing Packet and Incremental Re-Review

v5.14.0 adds a revision-diff workbench that maps changed text to prior legal claims, fact-review units, citations, court forms, and procedure assumptions. Prior decisions remain immutable historical references, but no approval is carried forward to a changed revision.

## Reviewer assignments

Assignments are matter-local and revision-bound. Reviewer labels and roles are user-entered metadata; the application does not verify identity or professional licensure. Exclusive assignment collisions fail closed.

## Reviewed filing packet

The deterministic packet binds the exact document revision, review decision and hash chain, prior review packet, authority verification, fact-to-evidence report, procedure and form reports, findings review, claim annotations, source lifecycle checks, assignments, blockers, and incremental diff.

Exports are JSON, HTML, and a receipt with an immutable manifest. They are review work product, not proof of facts or a guarantee that a document is ready to file.

## Lifecycle blockers

A changed revision, stale or superseded authority, unknown form lifecycle, missing source hashes, missing reviewer assignment, unverified review ledger, non-approval decision, or failed filing gate remains a visible packet blocker.

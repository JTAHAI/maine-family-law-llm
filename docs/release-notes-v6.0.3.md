# Maine Family Law LLM v6.0.3 — Extended Hardening

v6.0.3 is a narrow security, concurrency, and durability release built on v6.0.2.

## Changes

- Added cross-process sidecar locks around Pass 48, 49, 50, and 51 ledger read/verify/append transactions.
- Added bounded descriptor-based file reads with symlink, non-regular-file, size, and file-identity checks.
- Added durable append and atomic write helpers that fsync files and parent directories where supported.
- Reworked local request-body enforcement to consume incrementally rather than allocate an unbounded body before checking the limit.
- Added `frame-ancestors` CSP and disabled cross-domain policy files.
- Added a random 256-bit local-service instance identifier and exact PID matching for reuse and shutdown.
- Prevented loopback health probes from following redirects.
- Replaced the compatibility package's dynamic `exec` loader with a normal canonical module import.

## Release identity

Product version: **6.0.3**
Microsoft Store package target: **6.0.3.0**
UI build: **50**
UI marker: **v6.0.3-extended-hardening**

## Qualification boundary

This is source hardening only. Signed-MSIX, WACK, Store, attorney, pilot, and shipment evidence remain external fail-closed gates.

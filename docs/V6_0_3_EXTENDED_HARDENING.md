# v6.0.3 Extended Hardening

v6.0.3 extends the completed seven-pass roadmap with a narrow security and durability pass. It does not add a new legal workflow or change the v6 visual design.

## Controls

- Pass 48–51 append-only ledgers use both in-process and cross-process locking.
- Evidence, policy, state, packet, and receipt reads use bounded regular-file descriptors and refuse symlinks.
- Durable writes flush the file and synchronize the containing directory where supported.
- Non-safe HTTP request bodies are consumed incrementally and refused once the local cap is exceeded.
- Local API reuse and shutdown require the exact per-launch service nonce and operating-system PID.
- Health probes do not follow redirects.
- Health responses disclose the nonce and PID only when a valid local service nonce is configured.
- The compatibility package shim imports the canonical version module without executing source text dynamically.

## Boundary

These controls strengthen local integrity and failure handling. They do not certify current Maine law, attorney review, a real-matter pilot, WACK, Microsoft Store approval, or GA shipment.

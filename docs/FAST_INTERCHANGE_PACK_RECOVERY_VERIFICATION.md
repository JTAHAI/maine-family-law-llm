# FAST INTERCHANGE offline-pack recovery — local verification

Date: 2026-08-28. This continues the signed-worker implementation, not the old
product-feature queue. Mainely Code remains proprietary and out of scope.

## Scope and evidence boundary

The implemented path is production source UI → canonical local API → encrypted
pack state → independently signed artifact inspection → explicit activation.
Real browser actions used a fictional matter and an 8,117-byte synthetic ZIP
with 498 bytes of structural artifacts. Its two development test entries have
no legal knowledge, no redistribution grant, and no production admission.

The browser now proves file selection, import, separate approval, cancellation
before activation, same-file resume from a new browser session, recoverable
removal, restore, and activation. This supersedes the earlier **native
file-picker unavailable** finding for this connection. It does not supersede
the real-model, hardware, frozen-app, or installed-package gates.

Evidence lives in `dist/ga_today/evidence/fast_interchange_pack_recovery/`.
`browser-evidence.json` records each actual journey and its limitations. The
source hashes and final machine-readable report distinguish the earlier test
iterations from the final source regression. Earlier failed/interrupted runs
remain available; none are presented as passing full regressions.

## Implemented safeguards

- Chunk offsets are fixed and bounded to 1 MiB. Repeating the last identical
  chunk after a lost response does not append duplicate bytes.
- Resume requires explicit local-admin consent in the same tenant and matter.
  The browser rehashes the selected original's committed prefix in bounded
  chunks; the service independently rehashes staging. A new session takes over
  only after this agreement. Ordinary status/chunk/cancel access remains
  session-bound. The old session loses access after rebind.
- A torn, uncommitted staging tail can be truncated only after prefix validation
  and a recorded recovery authorization. The original ZIP is never altered.
- An OS-level verification lease prevents another process from taking over a
  live verification. Persisted cancellation is observed across service
  instances. Interrupted verification starts a fresh extraction directory.
- Activation journals an encrypted intent before changing admission high-water
  state or the active pointer. The worker loader refuses a pending transaction
  or a pointer/state mismatch. Recovery is explicit, identity-bound, audited,
  and repeats current signature, revocation, sequence, and artifact checks.
- High-water state is never lowered. A previous version that is revoked,
  expired, or below the admitted catalog sequence cannot be reactivated. A
  newly signed reauthorization is required; “rollback” is not a bypass.
- If interrupted activation is no longer admissible, an explicit recovery can
  leave **no active pack** while retaining installed files and high-water state.
- Inactive whole-pack removal is a recoverable move, not a deletion. Configured
  active/previous versions and pending-review dependencies are protected.
  Recovery storage does **not** reclaim disk space. Restore is inactive and
  requires current admission; activation still needs separate approval.
- Storage moves are journaled. An interrupted remove/restore can finish, or be
  explicitly reversed to its original storage state without loading a model.
  A later revocation cannot force a storage-only recovery to weaken admission.
- No worker starts, stops, or switches automatically. Operators must coordinate
  separately running workers and restart/rebuild their exact-source preview.
  These local role/session controls are not enterprise identity federation.

## Canonical API

Existing import routes remain unchanged. New routes are:

| Method and route | Protection and action |
| --- | --- |
| `POST /api/model-packs/imports/{job_id}/resume` | Explicit consent; same tenant/matter/admin; matching committed byte count and prefix chain |
| `POST /api/model-packs/recovery` | Exact transaction ID; owner scope; explicit finish, deactivate, or storage-reversal intent |
| `POST /api/model-packs/installed/{pack_id}/activate` | Explicit consent; expected current active ID; freshly verified admission and bytes |
| `POST /api/model-packs/installed/{pack_id}/remove` | Explicit consent; owner scope; reference guards; recoverable whole-pack move |
| `POST /api/model-packs/removed/{pack_id}/restore` | Explicit consent; owner scope; current admission; inactive restore |

The inventory exposes only the current session's jobs and, to a matching local
admin, explicitly recoverable jobs/versions. Recovery does not accept a URL,
filesystem path, trust key, executable, or worker credential from the browser.

## Production UI and accessibility

Both shipped source mirrors are synchronized. Imports and installed versions
have explicit selectors; status updates cannot leave “New import” selected
while displaying a different active job. Exact signed details remain available.

Pack changes use a nonblocking in-app confirmation dialog instead of
`window.confirm`. It names the exact identity, defaults to keeping current
state, traps Tab/Shift+Tab between its two actions, handles Escape explicitly,
and returns focus to the initiating control without closing the source dialog.
The actual browser check at 640×720 found no horizontal dialog overflow. This
is a compact CSS-viewport check, not a full assistive-technology certification
or an OS-level 200% zoom claim. Disabled model-run text also has readable colors.

## Tests and remaining gates

The expanded FAST INTERCHANGE run passed **209 tests, zero failures/skips** in
468.257 seconds. The final confirmation and canonical HTTP recovery checks
passed **20 tests** separately (17 UI interactions and three positive HTTP
fault-recovery journeys). These overlapping counts must not be added.
The three HTTP cases were added after full-suite collection and executed
separately. A later cancellation-label race was corrected in the production
JavaScript: a completed prefix-hash chunk must not overwrite the canceled
state, and a canceled local check must restore the prior import controls. Its
new-session cancellation case and the complete pack/local-agent UI and HTTP
tests were rerun separately. The evidence records that narrow post-start change
explicitly; the full-suite report is not an exact-source release freeze of the
later JavaScript. Perform the exact-source release freeze before packaging.
The final full-suite result is recorded in `verification.json` and its JUnit
report, not inferred from focused tests. Compilation, production JavaScript
syntax checks, and test collection were also executed.

Final results: the full run completed **1,988 passed, 22 skipped, zero failures
or errors** (1,288.562 seconds in JUnit). After the cancellation-label correction,
the pack UI, local-agent UI, and canonical HTTP recovery run passed **28/28**
(58.869 seconds). Their union covers all **2,014 currently collected cases**:
1,992 passes and 22 skips, without double-counting overlap. This is not a
single exact-source release-freeze run. The final source privacy audit checked
2,093 files with no findings; it is not an audit of an exact MSIX.

The skips are six absent archived authority/GA evidence cases (release
blockers), fourteen unavailable Windows symlink-privilege cases, one unsupported
POSIX executable-bit case on Windows, and one absent native Whisper audio
fixture. None are promoted to passes. Raw reasons are in `verification.json`.

Fault tests cover interruption after trust/pointer writes, failed completion
audit/state commit, cross-session and cross-matter access, changed prefixes,
torn writes, live verification takeover, cross-instance cancellation,
revocation during recovery, blocked downgrades, dependency protection, and
recoverable storage moves. Browser confirmation defects were repaired and
retested; the earlier stalled OS-confirmation tab is not passing evidence.

Still required for a fully operational release:

1. Rights-cleared base/tokenizer and seven genuinely trained adapters; approved
   corpus, evaluation, independent admission and production trust provisioning.
2. A separately approved distribution/download source and its integrity,
   interruption, quota, and update lifecycle. This slice is **offline import**,
   not a downloader, training system, or model hosting service.
3. Actual legal-quality and human evaluation. Tiny generated tensors and
   structural test packs are not attorney review or a pilot.
4. Measured supported modest-hardware profiles. Single-safetensors CPU fp32 is
   not proof of useful 8/16 GB performance, GGUF/NF4, or GPU compatibility.
5. A new frozen build and exact MSIX audits/isolated installation/offline tests.
   The existing package does not contain these changes. No new MSIX, Store
   certification, enterprise sign-off, GitHub push, or publication occurred.

Older state without the new durable owner/prefix metadata is not silently
claimed by a new session. Preserve it and use its original authorized session
or an operator-reviewed recovery procedure; never guess ownership or clear
trust counters to unblock it.

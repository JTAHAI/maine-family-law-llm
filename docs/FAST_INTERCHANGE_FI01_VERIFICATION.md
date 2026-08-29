# FAST INTERCHANGE: protected source and approval verification

Recorded 2026-08-28 UTC. This is a bounded source-code verification report, not
a real-model, frozen-app, installed-package, Store, or Enterprise certificate.

## Implemented

- The canonical `/api/local-agent/preview` and `/api/local-agent/run` routes
  accept closed, hash-bound source references instead of trusting posted text
  or caller-supplied authority labels.
- Private text is reparsed from the capability-authorized, hash-verified
  original in the active matter. Mutable index prose cannot replace it.
  Authority text comes from a selected verified immutable build; the bytes
  actually parsed are hashed before the context service returns them.
- Preview approval is single-use, expires after five minutes, and binds local
  role/session/tenant/matter, question, task, source references, provider,
  endpoint, model, and run. A delayed human approval retains the original
  manifest timestamp. Restart invalidates outstanding approvals.
- Live source authorization is checked again before dispatch and after
  generation. Revoked or changed records and changed matters withhold output.
  Generic idempotency response replay is disabled for these two routes.
- Content-free preview/dispatch/result receipts are encrypted and hash-linked
  in the matter's runtime sidecar. Audit failure blocks dispatch or output.
  This chain is not independently anchored protection against journal rollback.
- Production UI mirrors show the full exact selected text, freshness, and
  review-required state. Changed model settings require another preview.
  Duplicate context cards stay aligned with manifest indexes; whitespace-only
  display normalization maps back to original text without fuzzy word matching.
- Closing an in-flight review discards late responses and prevents another
  request until the first settles. The label explicitly says closing does not
  cancel generation. Actual worker cancellation is still a separate open gate.
- Release preflight now includes late WACK hash/path blockers in readiness,
  rejects inconsistent success reports, and requires explicit passed-test
  evidence. The parser no longer accepts empty/unknown reports or recertifies
  a previous JSON summary. Unrecognized or ambiguous native XML fails closed;
  compatibility with an actual WACK run still requires that run.
- The isolated QA installation script rejects unknown arguments, real Store
  identities, reused work roots, and existing evidence; it no longer uninstalls
  an existing QA identity. Its default repository path works with Windows
  PowerShell advanced parameter binding. No real installation was attempted.

## Exact verification

| Level | Result | Boundary |
| --- | --- | --- |
| Final focused Python/JavaScript-unit suite | 153 passed, 1 skipped, 0 failed/errors; 47.67 seconds | Synthetic worker/library doubles where applicable |
| Skip | `test_authority_generation_rejects_symlinked_snapshot`: symlinks unavailable | Not a passed symlink test |
| Collection | 1,873 tests collected, exit 0 | Collection is not full-suite execution |
| Compilation | `python -m compileall -q legal app src maine_family_law_llm scripts tests`: exit 0 | Source tree |
| JavaScript syntax | Both shipped workbench JS mirrors: exit 0 | No package rebuild |
| Focused lint | New context service, UI fixture harness, and three new test modules: pass | Not whole-repo lint |
| Actual browser | Production source UI, canonical HTTP API, real parser/index, fictional record | In-process synthetic generation client, not the FAST INTERCHANGE worker transport |
| Frozen/installed package | Not executed for this code | Previous MSIX predates these changes |

The final browser run used a new temporary fictional profile on loopback port
53682. It searched a missing-attachment record, opened the exact-text approval
dialog, rejected changed model settings, rebuilt approval, returned an
explicitly synthetic review-required answer with a provenance receipt, and
opened its original record in the hash-verified inspector. The QA server and
its browser tab were stopped afterward. No real matter data was used.
The browser supplied JPEG captures; original `.capture.jpg` files are retained
alongside correctly re-encoded PNGs (1265 x 712). These are QA evidence, not
Store listing assets or proof of Store screenshot requirements.

Evidence:

- `dist/ga_today/evidence/fast_interchange_operational_final_verified_junit.xml`
- `dist/ga_today/evidence/fast_interchange_operational_ui/final-*.png`
- `dist/ga_today/evidence/fast_interchange_operational_ui/final-*.dom.txt`
- `dist/ga_today/evidence/fast_interchange_operational/20260828-fi01-source-approval/verification.json`
- `dist/ga_today/evidence/fast_interchange_operational/20260828-fi01-source-approval/artifact-manifest.json`

Earlier intermediate reports are retained and overlap; do not add their counts
together or represent them as independent full-suite passes. One upstream
Starlette/httpx deprecation warning remains.

## Remaining work, in order

1. Finish immutable admission trust: operator-approved signing anchor, closed
   release schema, exhaustive loader-file coverage, revocation, and a verified
   immutable model-loading strategy. Verify authority manifest capture and
   validation as one immutable operation, not only parsed-artifact bytes.
2. Complete bounded worker requests/queueing, actual backend cancellation,
   cleanup under failure, and task-to-admitted-capability routing. Bind the
   exact admitted release identity, not merely the requested model string.
3. Implement the explicit-consent signed model-pack manager and offline import.
   Hugging Face/GitHub/R2 remain distribution proposals: no host was configured,
   no upload/download occurred, and strict Local-only policy was not loosened.
4. Supply rights-cleared base/tokenizer, seven real compatible adapters, permitted
   training/evaluation data, independent admission, and required human review.
   **No new generative model weights were added by this pass.**
5. Test real inference/switching/cancellation on declared modest hardware,
   perform full regression, then rebuild and qualify the exact installed MSIX
   with offline workflows, privacy inspection, and WACK. Do not advertise the
   source-only results as installed or Store-ready.

Current role enforcement reuses the application's explicit local desktop
role/session headers and record capabilities; it is not independent enterprise
identity authentication. OCR-only records without verified parsed text remain
unavailable to this model lane until their OCR derivative is immutably bound.
Those limitations must remain visible in any broader acceptance decision.

No version change, commit, push, website update, publication, model training,
model download, or new MSIX was performed. Mainely Code remains out of scope.

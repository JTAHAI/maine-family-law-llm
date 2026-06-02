# v1.91 public-source pre-push gate

This pass adds a source-tree gate that answers one practical release question before every public GitHub push: is this repository clean enough to push without claiming the legal product is GA shipped?

The gate is intentionally narrower than true GA. It checks source hygiene, public-release readiness, package-version consistency, CI guardrails, and that Passes 48-51 remain fail-closed when external launch evidence is missing.

## Commands

```bash
python scripts/run-public-source-preflight.py --repo-root . --require-ready
```

Windows convenience push wrapper:

```powershell
.\PUSH_SAFE.ps1 -Message "Run public-source pre-push gate"
```

Cross-platform wrappers are also available at:

- `scripts/git-safe-push.ps1`
- `scripts/git-safe-push.sh`

## What this can certify

- Public source hygiene is clean.
- Required GitHub workflow and issue/PR templates are present.
- Package metadata and pass logs agree on the release version.
- The remaining launch/GA gate still blocks missing external evidence.
- The source tree is safe to stage for GitHub from an artifact-boundary perspective.

## What this cannot certify

- It does not certify attorney review.
- It does not certify a limited real-matter pilot.
- It does not certify release-candidate signoff.
- It does not certify GA shipment.
- It does not make any answer filing-ready or legal advice.

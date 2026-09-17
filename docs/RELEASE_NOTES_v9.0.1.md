# Maine Family Law LLM 9.0.1

## What's new in this version

Set up optional local AI directly in chat—no terminal commands required. The app
checks available memory and disk space, explains the 4B and 8B choices, and asks
before downloading anything. Existing Ollama installations and matching models
are reused; only missing components are downloaded. Follow progress in chat,
stop safely, retry, and choose Use in chat after a fictional source-review test.

Evidence review and drafting retain exact-source approval, source links,
quotation checks and visible review-required status. The models are
general-purpose assistance, not certified legal specialists; drafting produces
source-attributed working material, not a filing-ready legal document.

## Distribution and privacy

Product 9.0.1, package 9.0.1.0, build 57. The existing Store identity/publisher
and x64/en-us manifest remain unchanged. The MSIX contains the app and essential
offline engines, not Ollama or Qwen weights. Explicit setup consent permits
downloads from official GitHub/Ollama sources. No matter text is part of setup.
Ollama is separate software and can maintain its own background updates.

Existing models with a different pinned manifest are not silently overwritten.
Missing components require internet access and sufficient disk space. Hardware
checks measure current headroom, not guaranteed speed on every computer.

## Verification and remaining qualification

- 214 distinct focused setup, provider, UI, version and packaging tests passed
  across two suites (136 + 78); no full-repository 9.0.1 regression is claimed.
- Both installed models passed live component-reuse tests without downloading.
- Final frozen API exercised setup plus evidence review and drafting with both
  4B and 8B. The production chat setup and source-review controls were exercised.
- Package privacy, engine inventory, sealed payload and manifest checks passed.
- Missing-component installation has deterministic fixture coverage. A real
  clean-Windows download/install, installed-MSIX upgrade and WACK were not run.
- No legal-quality, attorney, pilot or Enterprise certification is claimed.

Evidence: `dist/release/v9.0.1/RELEASE_VERIFICATION.json`. The unsigned MSIX is
intended for Microsoft Store signing, not represented as a locally signed app.
Back up matters through the app before any upgrade; no matter schema migration
or model training on personal data is introduced by this patch.

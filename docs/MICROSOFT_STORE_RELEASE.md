# Microsoft Store Release

This repository includes a Microsoft Store packaging path for a self-contained x64 MSIX build of Maine Family Law LLM.

## Distribution truth

- The open-source repository and the Microsoft Store package are two distribution paths for the same project.
- The Store package does not bundle private matter corpora, authority snapshots, embeddings, vector stores, OCR caches, runtime databases, uploads, or model weights.
- The Store package remains local-first, review-required, and not legal advice.

## Build flow

1. Build the frozen desktop runtime:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\build-store-runtime.ps1`
2. Run the fictional sample smoke workflow:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\test-store-runtime.ps1`
3. Build the MSIX:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\build-msix.ps1 -IdentityConfigPath .\store\msix\identity.example.json`
4. Install the test MSIX:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\install-test-msix.ps1`
5. Launch the Start-menu entry and verify:
   - local AI chat launches
   - About/Help opens
   - GitHub and fork guide links work
   - fictional sample workflow remains local-only
6. Uninstall:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\uninstall-test-msix.ps1`

## Partner Center inputs still required

For a real Store submission, provide:

- Identity Name
- Publisher
- Publisher Display Name
- Package Display Name
- four-part package version

Use `store/msix/identity.example.json` as the template for the reserved store identity in this repository. If you are preparing a different store account, copy it to `store/msix/identity.local.json` and keep that file untracked.

## Signed update metadata

`scripts/verify-store-update-metadata.py` verifies a release-ceremony-signed,
hash-bound metadata document against one exact MSIX and its frozen release
scope. It does not download, install, configure, or publish an update. Windows
and Partner Center remain the delivery authorities. Production public keys are
added to the trusted-key configuration only during the release ceremony;
private keys and update credentials must remain outside the repository.

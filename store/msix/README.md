# MSIX packaging files

This directory contains the source-controlled Microsoft Store packaging materials for Maine Family Law LLM.

## Files

- `AppxManifest.xml.in`: manifest template with explicit placeholders
- `identity.example.json`: example identity configuration
- `assets/`: generated MSIX image set and inventory

## Local build flow

1. Build the frozen runtime:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\build-store-runtime.ps1`
2. Build the MSIX:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\build-msix.ps1 -IdentityConfigPath .\store\msix\identity.example.json`
3. Install the test MSIX:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\install-test-msix.ps1`

## Identity handling

Do not commit real signing materials. If you need to target a different Partner Center account, copy `identity.example.json` to `identity.local.json`, update the values for that account, and keep the local file untracked.

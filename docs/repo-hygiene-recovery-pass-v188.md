# v1.88.0 repo hygiene recovery

This pass repairs the v1.87 packaging problem observed during local application: required public repository files were absent from the ZIP, so `robocopy /MIR` deleted `.github` and `.gitignore`, while generated local runtime artifacts remained in the destination and were committed.

## Fixes

- Package `.gitignore`.
- Package `.github/PULL_REQUEST_TEMPLATE.md`.
- Package `.github/ISSUE_TEMPLATE/bug_report.yml`.
- Package `.github/ISSUE_TEMPLATE/config.yml`.
- Package `.github/workflows/ci.yml`.
- Restore missing enterprise test model modules.
- Keep `.mfl_work`, caches, pycache, venvs, model weights, corpora, indexes, and runtime stores excluded from source release artifacts.

## Required local recovery after v1.87 contaminated commit

Run cleanup commands before committing v1.88 so Git removes already-tracked runtime files from the index and restores required public repo files from the new ZIP.

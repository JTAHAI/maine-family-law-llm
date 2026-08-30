# Repository-only work and artifact limits

These restrictions reflect the owner's explicit disk-space and cleanup instructions.

- Work only in this checkout. Never create scratch directories beside it, at a
  drive root, or in another project. Explicitly supplied model inputs may be
  read, but not modified or duplicated into a new external workspace.
- Keep test fixtures, runtime profiles, caches, temporary model snapshots, and
  build intermediates inside this repository's `dist` tree. Set subprocess
  temporary/cache paths explicitly; do not rely on the machine's defaults.
- Do not copy a frozen runtime or model pack for every attempt. Use one owned
  temporary workspace at a time and close it in `finally`. After interruption,
  inspect existing owned artifacts before creating another copy.
- Before a large build/copy, measure available space and the required footprint.
  If insufficient, stop; never fill another drive as a workaround.
- Preserve source changes, actual model weights, private data, current release
  packages and compact evidence. Delete only identified generated artifacts
  within the authorized scope, after checking exact paths and active processes.
  Never bypass a denied deletion operation with another shell or tool.
- Do not rerun historical external `mfl-qa-*` commands. Use an explicit
  repository-local pytest `--basetemp`. Authority fixtures must use synthetic
  repository identities; do not weaken production authority-store isolation.
- No new builds or inference runs while an explicit cleanup/pause request is
  active. Report cleanup failures honestly; do not claim reclaimed space unless
  removal has actually been verified.

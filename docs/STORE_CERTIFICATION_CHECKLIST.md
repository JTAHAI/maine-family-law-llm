# Store Certification Checklist

Use this checklist before calling the Microsoft Store package ready:

- [ ] PyInstaller runtime built successfully.
- [ ] Runtime smoke workflow passed from the frozen executable.
- [ ] MSIX built successfully.
- [ ] MSIX installed successfully for the current user.
- [ ] Start-menu launch succeeded.
- [ ] Local AI chat opened.
- [ ] About/Help showed source-code, fork guide, privacy, and disclaimer text.
- [ ] GitHub link worked.
- [ ] Fork-for-your-state guide worked.
- [ ] Privacy policy link worked.
- [ ] Local service stayed on loopback only.
- [ ] No package contents included private matter data or runtime state.
- [ ] Evidence files were written under `dist/store/evidence/`.
- [ ] WACK ran and passed, or a truthful reason it could not run was recorded.
- [ ] Uninstall left user-created external case folders intact.

## Manual Partner Center inputs

- Identity Name
- Publisher
- Publisher Display Name
- Package Display Name
- final Store version
- Store screenshots and listing copy review

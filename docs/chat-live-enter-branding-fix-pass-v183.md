# v1.83 chat live UI Enter-submit and FOCAF branding fix

This pass fixes the browser behavior reported after v1.82: the visible page could remain unbranded and the Enter key did not submit chat input.

Root cause: the inline browser script contained Python-interpolated newline escapes inside JavaScript string literals. That made the browser stop parsing the script before event handlers attached, including the Enter-to-submit handler.

Changes:

- Added an explicit `focaf-brand-shell` header marker and visible `UI v1.83 live Enter/branding fix` footer marker.
- Escaped JavaScript transcript newline literals so the inline script parses in the browser.
- Kept Enter-to-submit on the question textarea and `Shift+Enter` for multiline input.
- Added v1.83 regression tests that assert the live marker, FOCAF branding shell, Enter handler, and no broken newline literals.
- Restored required public repo files under `.github/` and `.gitignore` so the local doctor can pass after overlay.

Evidence:

- `tests/test_local_workbench_live_ui_v183.py`
- `docs/external-evidence/chat_library_workbench_evidence_v183.json`
- `scripts/run-chat-library-evidence.py --require-ready`

No attorney review, legal signoff, real-matter pilot, or production GA is claimed by this pass.

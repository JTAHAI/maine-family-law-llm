# v4.4.0 Three-Pass Windows OCR and Corpus UX Upgrade

## Pass 4.2 — Windows startup and OCR prerequisite setup

- Fixed the checked-in and generated Windows launchers so a repository path ending in `\` cannot escape the closing quote passed to PowerShell and trigger `.NET GetFullPath()` with illegal characters.
- Normalized explicit launcher paths by trimming whitespace and surrounding quote characters, expanding environment variables, and rejecting null/newline control characters before resolving the path.
- Added an explicit, allowlisted one-click Tesseract installer through Windows Package Manager.
- The installer is invoked only after affirmative consent and never accepts a user-supplied package ID or command argument.
- Added a manual Tesseract install page and a local recheck action when one-click installation is unavailable or needs a new app session.
- Matter files are not read, transmitted, or uploaded by prerequisite installation.

## Pass 4.3 — Indexed-corpus command routing

- Added a dedicated `corpus_inventory` intake task for commands such as `list what is in my indexed corpus`, `show indexed files`, and `list indexed PDFs`.
- Added direct PDF-filtered record-search parsing for commands such as `find PDF re: contempt`.
- Corpus inventory commands bypass the Maine-law lane and return actual selected-matter counts, parser status, source types, OCR readiness, and record source cards.
- PDF-filtered searches exclude non-PDF text records even when those records contain the same search term.
- Private-record matches remain evidence/search results only and are not presented as legal conclusions or Maine authority.

## Pass 4.4 — Local scanned-PDF OCR and visible UI controls

- Added `pypdfium2` to the source and Store runtimes as the bundled PDF page renderer.
- Scanned-PDF OCR no longer requires a separate Poppler or MuPDF executable; Tesseract remains the OCR engine.
- Added visible **Install OCR prerequisites**, **Open manual install page**, and **Recheck local OCR** controls to the consent dialog.
- Added installer progress polling and clear disclosures about the network boundary and local-only record handling.
- Added a dedicated browser rendering path for corpus inventories instead of forcing them through the generic legal-answer template.

## Safety and release boundaries

- OCR remains opt-in and local-only.
- The original evidence files are not modified.
- OCR-derived text remains labeled as OCR-derived and review-required.
- Private records remain separate from Maine-law authority.
- This source pass does not certify current law, attorney review, WACK, a signed MSIX, or production legal GA.

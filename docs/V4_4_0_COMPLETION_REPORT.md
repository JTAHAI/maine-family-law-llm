# Maine Family Law LLM v4.4.0 Completion Report

v4.4.0 completes three linked production fixes prompted by observed Windows and chat behavior.

First, the Windows startup failure was corrected in both the checked-in launcher and the launcher generator. The trailing backslash from `%~dp0` can no longer escape the closing quote and reach `.NET GetFullPath()` as an illegal path. The bootstrap script also normalizes explicit paths defensively.

Second, local OCR setup is no longer a dead end. The OCR consent dialog now offers an explicit one-click Tesseract installation through Windows Package Manager when available, a manual install page otherwise, and a local recheck action. The app bundles a Python PDF renderer so scanned-PDF OCR does not require a separate Poppler or MuPDF installation. OCR remains opt-in, local-only, and review-required.

Third, corpus commands now behave as corpus commands. `find PDF re: contempt` performs a PDF-filtered private-record search, while `list what is in my indexed corpus` returns the actual selected-matter inventory, searchable/OCR counts, parser status, source types, and record cards. Neither command is replaced with generic Maine-law boilerplate.

Validation accounted for all 693 collected tests: 692 passed, one existing Linux-only PowerShell-parser skip, and zero failures. Repository, package, public-source, JavaScript, Python, and bundled FOCAF resource audits passed.

The source is configured for product version `4.4.0` and Store package version `4.4.0.0`. A signed Windows MSIX and WACK run remain Windows release steps. Live official-source freshness certification, attorney-reviewed evaluation, institutional security/pilot evidence, and formal signoffs remain outside this source-level pass.

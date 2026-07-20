# Maine Family Law LLM v3.1.2 hotfix report

## Root cause: FOCAF `printable_not_found`

The supplied v3.1.1 MSIX already contains all 103 FOCAF PDFs. The defect was resource selection, not missing package bytes.

The frozen runtime contains two directories:

- `_internal/maine_family_law_llm/resources/focaf` — inventory and PDFs
- `_internal/src/maine_family_law_llm/resources/focaf` — inventory only

`resource_root()` returned the source-tree directory first because it merely checked `is_dir()`. `get_printable()` therefore succeeded, while `printable_pdf_path()` looked for the PDF in the incomplete directory and returned `None`.

The fix prefers the complete frozen data directory, searches all valid resource roots, validates safe filenames and SHA-256 hashes, and distinguishes unknown IDs from missing or modified packaged assets.

## Explicit local OCR

The prior implementation computed `ocr_choice_required` but exposed no OCR API or visible action. It also only returned an `unavailable` placeholder.

The hotfix adds:

- visible `OCR N scanned pages locally` action beside My Records inventory status;
- separate accessible consent dialog with the exact local-only disclosure;
- decline and cancel paths that do not grant consent;
- local Tesseract discovery and local PDF renderer discovery;
- OCR of image files and image-only PDFs;
- page-level confidence and provenance metadata;
- cancelable background OCR job API;
- local-only FTS5 rebuild after OCR;
- original-file hash preservation;
- no-network execution boundary;
- explicit `not installed` state rather than silent failure.

## Source-card continuity

Natural follow-ups such as `give me the source cards`, `show the matches`, and `where did you find that` now reopen the previous local result set in the Evidence drawer without issuing a new corpus query.

## Local validation performed here

- Python compilation: passed
- JavaScript syntax: passed
- Focused hotfix tests: 6 passed
- FOCAF asset audit against supplied frozen runtime: 103/103 passed
- Exact previously failing printable: resolved, PDF header valid, SHA-256 matched
- Synthetic image-only PDF OCR: completed locally
- OCR-derived `contempt` content: retrieved through FTS5
- Original synthetic source hash: unchanged
- Network usage reported by OCR smoke: false

## Windows-only gates delegated to the included rebuild script

- PyInstaller frozen runtime rebuild
- Store runtime smoke
- MakePri / MakeAppx
- SignTool signing
- AppxManifest identity/version verification
- final MSIX SHA-256
- optional GitHub main push
- WACK remains a separate elevated check

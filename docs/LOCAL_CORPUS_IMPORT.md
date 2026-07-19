# Local Corpus Import

Use the desktop launcher for corpus intake. Choose **Create New Case Corpus** for a new matter or **Reopen Intake / Add More Evidence** to add material later. The chat remains usable without creating a corpus.

The picker accepts individual files, folders, and ZIP archives. Common supported sources include PDFs, DOCX, TXT, Markdown, HTML, RTF, EML email exports, CSV, XLSX, PPTX, screenshots, and audio/video inventory. Embedded PDF text is extracted first. OCR and transcription are optional local follow-up steps and are never reported as completed unless local tools actually completed them.

Every input is SHA-256 hashed before and after parsing. The builder creates derived inventory and search data under the selected case workspace, not in this repository. It does not modify the originals, upload them, or include them in an MSIX package.

The active-matter chat searches a private SQLite FTS5 content index when available. Source cards show a filename or archive/member locator, parser state, and record ID without exposing an absolute local path in the browser UI.

## Optional family resources

[FOCAF family resources](https://focaf.jtforme.com/) and the [FOCAF download library](https://focaf.jtforme.com/download-library/) are optional links that open separately in the default browser. They are not legal authority. Opening them does not send a matter name, local path, question, or search query from this application.

## Local inventory consent and optional OCR

When you create a case or add records, the desktop launcher first asks for permission to scan and inventory only the source files you selected. Choosing **Cancel** reads nothing. The local workbench shows the derived-index status beside the active matter and can review, rebuild, or delete that index without changing original documents.

If a file has no usable native text, the launcher separately offers local OCR. OCR is never automatic. You can keep scanned pages unsearchable, cancel, or use a separately installed local OCR engine. Neither workflow uploads selected files, extracted text, filenames, hashes, or search terms.

The bundled FOCAF printable library is a separate public resource lane. It can be searched by extracted PDF page text and opened or printed locally, but it is not private matter evidence, legal authority, an official court form, or proof of a disputed fact.

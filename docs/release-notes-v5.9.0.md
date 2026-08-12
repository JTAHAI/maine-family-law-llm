# Maine Family Law LLM v5.9.0 — Local Document Intelligence

v5.9.0 adds bounded, local-only document intelligence directly to the large verified-source inspector.

## New capabilities

- Deterministic structured blocks for PDFs, DOCX files, tables, headings, numbered paragraphs, and signatures.
- Optional Docling layout extraction when separately installed.
- Deterministic privacy-span detection with an optional Presidio comparison.
- Privacy reports retain spans and hashes rather than the matched sensitive value.
- Explicitly approved OCRmyPDF searchable preservation copies.
- Immutable, content-addressed derived PDFs, sidecars, reports, and receipts.
- Short-lived matter-scoped download capabilities with no absolute paths.
- Python-level network denial and offline environment controls for optional parser workers.
- Fallback behavior when optional components are missing or fail.

## Release boundary

The default source package does not bundle Docling, Docling models, Presidio, OCRmyPDF, Tesseract, Ghostscript, external authority data, private matter records, model weights, or runtime indexes. These components remain optional and must pass license, SBOM, vulnerability, Windows, and MSIX qualification before bundling.

Product version: **5.9.0**. Microsoft Store package target: **5.9.0.0**. UI build: **36**.

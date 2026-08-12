# Runtime Feature / Dependency Matrix

This matrix covers the user-facing runtime features currently advertised by the desktop workbench and the Windows store build. It is the source-side packaging target for the self-contained MSIX release.

If a listed engine, model, binary, or asset is missing from the frozen runtime, the release must fail closed instead of falling back to a machine-global installation.

## Matrix

| Feature | UI / API surface | Required runtime packages | Required bundled assets | Offline validation target | Bundling rule |
| --- | --- | --- | --- | --- | --- |
| Deterministic document parsing | Document intelligence fallback, corpus intake, searchable record views | `pypdf`, `pypdfium2` | None | Parse PDF, DOCX, HTML, TXT, CSV, JSON without network access | Must remain built-in and local-first |
| Presidio privacy detection | Document intelligence "Compare with Presidio" | `presidio-analyzer`, `spacy` | Bundled spaCy model package used by Presidio, plus any rule data the package requires | Run a local analysis pass on text without model download or network calls | Detection uses `presidio-analyzer`; redacted working copies use the app's deterministic local redaction path. `presidio-anonymizer` is intentionally excluded because it is unused and conflicts with the hardened cryptography floor. |
| Docling document parsing | Document intelligence "Use Docling" | `docling`, `torch`, `transformers` and Docling transitive dependencies | Docling pre-fetched model artifacts | Convert a local sample document offline with no first-run model fetch | Must be bundled when the UI exposes Docling |
| OCRmyPDF searchable-copy generation | OCR choice / OCR start workflow | `ocrmypdf`, `pikepdf`, `fpdf2`, `uharfbuzz`, `pypdfium2` | Tesseract x64 binary, English tessdata, required fonts | Produce a searchable copy from a local PDF while the network is disabled | Must be bundled when OCR is advertised |
| Local OCR prerequisite status | OCR setup / recheck UI | `ocrmypdf` stack plus Tesseract discovery logic | Same as OCRmyPDF row | Report local OCR readiness without downloading at runtime | Must refuse PATH/global fallback in MSIX mode |
| SQLite vector retrieval | Retrieval workbench status and search | `sqlite-vec` | Native `sqlite-vec` x64 binary extension | Build a local index and search it offline | Must be bundled when the retrieval UI exposes sqlite-vec |
| Qdrant loopback retrieval client | Retrieval workbench optional backend | `qdrant-client` only | None; no Qdrant server is bundled | Import client and refuse any non-loopback URL | Bundle client only if the runtime imports it; never bundle a server |
| Release hardening controls | GA / pilot / evidence APIs and UI | `opentelemetry-api`, `opentelemetry-sdk` when the hardening path is enabled | None | Run the local hardening audit without network access | Bundle only the code path already imported by the runtime |

## Fail-closed packaging rules

1. The build must fail if any advertised engine is absent from the frozen runtime inventory.
2. The build must fail if an advertised model tries to download during build or first launch.
3. The build must fail if an executable resolves from `Program Files`, `%PATH%`, a user Python installation, or another machine-global location when the MSIX is supposed to use the bundled copy.
4. The build must fail if the runtime UI reports that an advanced engine ran, but the bundled inventory cannot prove it.
5. The installed MSIX must remain usable offline after first install.

## Evidence target

The build is expected to emit the bundled runtime inventory to:

`dist/store/evidence/bundled-engine-inventory.json`

That inventory should include, for each bundled engine or model:

* package name
* version
* license
* included binary/model files
* SHA-256
* runtime import check
* offline smoke result
* startup cost
* package-size contribution

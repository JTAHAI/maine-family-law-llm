# Architecture

The v1 local workbench has a small deterministic pipeline:

1. `source_manifest.py` validates official-source metadata.
2. `fetch.py` reads offline fixtures or optionally fetches public official URLs.
3. `normalize.py` converts HTML/text into citation-friendly markdown text.
4. `chunk.py` creates citation-aware chunks with stable IDs.
5. `retrieve.py` performs dependency-free keyword retrieval with official-source preference.
6. `safety.py` classifies prompts.
7. `answer.py` and `draft.py` compose source-grounded responses.
8. `cli.py` and `api.py` expose local command-line and FastAPI surfaces.

The repo intentionally avoids cloud deployment, remote secrets, private-client storage, model weights, vector databases, and raw corpora in the source package.

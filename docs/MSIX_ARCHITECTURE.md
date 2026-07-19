# MSIX Architecture

## Runtime structure

The Microsoft Store package uses a PyInstaller `onedir` frozen runtime. The primary executable is:

- `MaineFamilyLawLLM.exe`

The frozen runtime includes:

- Python runtime
- Tkinter desktop launcher
- local FastAPI workbench
- local Uvicorn server
- HTTP client dependencies used by local smoke paths
- pypdf and corpus-processing modules
- project Python packages under `app/`, `legal/`, and `src/maine_family_law_llm/`
- brand assets
- local HTML help documents
- fictional sample fixtures and question bank

## Mutable versus immutable paths

- The installed MSIX package directory is treated as read-only.
- Runtime state is stored under `%LOCALAPPDATA%\MaineFamilyLawLLM`.
- Case and corpus builds stay in a user-selected external folder.

## Local service model

- The desktop launcher starts the local web service only on loopback.
- The packaged service binds to `127.0.0.1` only.
- Duplicate background services are avoided through a local state file under LocalAppData.

## First-run experience

The launcher starts without forcing the intake wizard. Users can:

- open the local AI chat immediately
- create a new corpus
- reopen intake later
- switch between multiple installed family/client corpora

## Data exclusions

The MSIX package must not contain:

- private matter data
- authority stores
- embeddings
- vector databases
- OCR caches
- uploads
- runtime logs
- secrets
- certificates or private keys

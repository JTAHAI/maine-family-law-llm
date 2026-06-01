# Local chat workbench

The local chat workbench is the non-technical browser entry point for this source release.
It runs against the same local `/ask` endpoint used by the CLI and returns source cards for the retrieved fixture or external authority snippets.

## Start on Windows

```powershell
cd D:\dev\ME_FM_LLM
.\START_LOCAL_CHAT.ps1
```

Open:

```text
http://127.0.0.1:8000/
```

Stop it:

```powershell
.\STOP_LOCAL_TEST.ps1
```

## Start manually

```powershell
python -m pip install -e ".[dev,api]"
$env:PYTHONPATH = "$PWD\src;$PWD"
python -m uvicorn maine_family_law_llm.api:app --host 127.0.0.1 --port 8000
```

## UI behavior

The page includes:

- a large question box;
- sample Maine family-law prompts;
- a one-click Ask button;
- source-card display for citations/retrieved snippets;
- health indicator;
- links to `/docs`, `/sources`, and `/api/health`.

The workbench is legal-information-only. It does not certify filings, create an attorney-client relationship, or replace source review.

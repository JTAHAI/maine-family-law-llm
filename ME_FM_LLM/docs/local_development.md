# Local Development

Recommended local startup:

```powershell
cd D:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\START_LOCAL_TEST.ps1 -SkipTests
```

The script creates a repo-local `.venv`, installs the package in editable mode with API extras, runs the local repair/doctor check, and starts FastAPI at `http://127.0.0.1:8000/docs`.

Useful commands:

```powershell
python -m pytest -q
python -m compileall -q src
python -m maine_family_law_llm.cli sources validate
python -m maine_family_law_llm.cli index build --fixtures
python -m maine_family_law_llm.cli ask "How do I start a family matter?"
```

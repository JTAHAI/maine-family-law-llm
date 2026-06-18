@echo off
setlocal
cd /d %~dp0
python -c "import maine_family_law_llm.case_corpus_builder, app.launcher" >nul 2>nul
if errorlevel 1 (echo INSTALLATION_IMPORT_FAILED & exit /b 1) else (echo INSTALLATION_OK & exit /b 0)

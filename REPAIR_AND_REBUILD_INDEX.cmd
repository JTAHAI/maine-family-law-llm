@echo off
setlocal
cd /d %~dp0
python -m maine_family_law_llm.case_corpus_builder --bootstrap --repo-root .

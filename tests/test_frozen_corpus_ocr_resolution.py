from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from maine_family_law_llm import local_corpus_index as corpus


@pytest.mark.parametrize("module_root", ["_internal/src", "_internal"])
def test_frozen_corpus_ocr_resolves_beside_executable(monkeypatch, tmp_path, module_root):
    runtime = tmp_path / "fictional-runtime"
    engine = runtime / "store" / "tesseract" / "tesseract.exe"
    engine.parent.mkdir(parents=True)
    engine.write_bytes(b"fictional-marker-not-executable")
    monkeypatch.setattr(corpus.sys, "frozen", True, raising=False)
    monkeypatch.setattr(corpus.sys, "executable", str(runtime / "MaineFamilyLawLLM.exe"))
    monkeypatch.setattr(
        corpus,
        "__file__",
        str(runtime / module_root / "maine_family_law_llm/local_corpus_index.py"),
    )
    monkeypatch.delenv("MFL_LOCAL_TESSERACT", raising=False)
    monkeypatch.delenv("MFL_LOCAL_PDFTOPPM", raising=False)
    monkeypatch.delenv("MFL_LOCAL_MUTOOL", raising=False)
    monkeypatch.setattr(corpus, "_pdfium_available", lambda: True)
    calls = []

    def version_only(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 15
        return subprocess.CompletedProcess(command, 0, "tesseract fixture\n", "")

    monkeypatch.setattr(corpus.subprocess, "run", version_only)
    status = corpus.local_ocr_engine_status()
    assert status["tesseract"] == str(engine)
    assert status["pdf_ocr_available"] is True
    assert status["image_ocr_available"] is True
    assert status["network_used"] is False
    assert calls == [[str(engine), "--version"]]


def test_frozen_corpus_does_not_discover_ambient_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus.sys, "frozen", True, raising=False)
    monkeypatch.setattr(corpus.sys, "executable", str(tmp_path / "MaineFamilyLawLLM.exe"))
    for name in ("MFL_LOCAL_TESSERACT", "MFL_LOCAL_PDFTOPPM", "MFL_LOCAL_MUTOOL"):
        monkeypatch.delenv(name, raising=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Frozen OCR must not search ambient paths or launch an installer")

    monkeypatch.setattr(corpus.shutil, "which", forbidden)
    monkeypatch.setattr(corpus, "_windows_tesseract_candidates", forbidden)
    monkeypatch.setattr(corpus.subprocess, "run", forbidden)
    monkeypatch.setattr(corpus, "_pdfium_available", lambda: True)
    assert corpus.local_ocr_engine_status()["available"] is False


def test_source_corpus_engine_path_keeps_repository_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus.sys, "frozen", False, raising=False)
    monkeypatch.setattr(
        corpus, "__file__", str(tmp_path / "src/maine_family_law_llm/local_corpus_index.py")
    )
    assert corpus._bundled_tesseract_candidates()[0] == (tmp_path / "store/tesseract/tesseract.exe")


def test_store_build_gate_requires_resolved_ocr():
    root = Path(__file__).resolve().parents[1]
    source = (root / "scripts/test-store-runtime.ps1").read_text(encoding="utf-8")
    assert "if ($payload.bundled_ocr_available -ne $true)" in source
    assert "Do not package this runtime" in source

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from legal.document_intelligence import service

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ("Occulta.ttf", "NotoSans-Regular.ttf", "sRGB.icc")


def inventory_module():
    spec = importlib.util.spec_from_file_location("ocr_resource_inventory_test", ROOT / "scripts/generate_bundled_engine_inventory.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_full_spec_collects_ocr_resources_and_license_notices():
    tree = ast.parse((ROOT / "store/pyinstaller/maine_family_law_llm.spec").read_text())
    collection_loops = [node for node in ast.walk(tree) if isinstance(node, ast.For)
                        and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                                and call.func.id == "collect_data_files" for call in ast.walk(node))]
    assert any("ocrmypdf" in ast.literal_eval(node.iter) for node in collection_loops)
    source = (ROOT / "store/pyinstaller/maine_family_law_llm.spec").read_text()
    for filename in ("NotoSans-OFL-1.1.md", "OCRmyPDF-sRGB-Zlib.md"):
        assert filename in source
        assert (ROOT / "licenses" / filename).stat().st_size > 500


@pytest.mark.parametrize("missing", RESOURCES)
def test_inventory_rejects_absent_searchable_pdf_resource(tmp_path, missing):
    module = inventory_module()
    definition = next(row for row in module.ENGINE_DEFINITIONS if row.package_name == "ocrmypdf")
    (tmp_path / "store/tesseract").mkdir(parents=True)
    for name in RESOURCES:
        path = tmp_path / "_internal/ocrmypdf/data" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name != missing:
            path.write_bytes(b"fictional inventory-test bytes, not an actual font")
    with pytest.raises(RuntimeError, match=missing.replace(".", r"\.")):
        module._ensure_required_paths(tmp_path, definition.required_paths)


def test_ocr_error_does_not_disclose_private_path_and_uses_frozen_safe_threads(monkeypatch, tmp_path):
    source = tmp_path / "fictional.pdf"
    source.write_bytes(b"%PDF-1.4\nfictional failure injection")
    monkeypatch.setattr(service, "_module_available", lambda _: True)
    monkeypatch.setattr(service, "local_ocr_engine_status", lambda: {"available": True, "pdf_ocr_available": True})
    module = types.ModuleType("ocrmypdf.api")

    def failed(*args, **kwargs):
        assert kwargs["use_threads"] is True
        assert kwargs["jobs"] == 1
        raise FileNotFoundError(r"C:\PRIVATE-FICTIONAL-PATH\sensitive.pdf")

    module.ocr = failed
    monkeypatch.setitem(sys.modules, "ocrmypdf.api", module)
    result = service.create_ocr_preservation_copy(case_root=tmp_path, source_path=source, approved=True)
    assert result["status"] == "blocked"
    assert result["error_summary"] == "ocr_preservation_failed:FileNotFoundError"
    assert "PRIVATE-FICTIONAL-PATH" not in str(result)

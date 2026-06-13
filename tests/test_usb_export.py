from __future__ import annotations

from corpus_builder_support import build_fixture_case, relative_links_from_html
from maine_family_law_llm.case_corpus_builder import export_to_usb


def test_usb_export_uses_relative_links_and_writes_manifest(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    export = export_to_usb(built["case_root"], tmp_path / "usb_export")
    export_root = export["export_root"]
    assert (export_root / "USB_COPY_MANIFEST_SHA256.txt").exists()
    assert (export_root / "VERIFY_USB.cmd").exists()
    start_here = export_root / "START_HERE_USB.html"
    assert start_here.exists()
    assert relative_links_from_html(start_here) == []

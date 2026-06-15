from __future__ import annotations

from corpus_builder_support import build_fixture_case


def test_role_packages_are_built_with_required_indexes(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    role_root = built["case_root"] / "03_ROLE_PACKAGES"
    assert (role_root / "01_GAL_REVIEW_USB" / "child_focused_index.html").exists()
    assert (role_root / "02_COURT_REVIEW_USB" / "docket_filing_service_index.html").exists()
    assert (role_root / "03_LAWYER_INTAKE_USB" / "10_minute_case_overview.html").exists()
    assert (role_root / "04_ADA_PROSECUTOR_CONTEXT_USB" / "context_and_verification.html").exists()
    assert (role_root / "06_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY_USB" / "INTERNAL_ONLY_WARNING.txt").exists()
    gal_index = (role_root / "01_GAL_REVIEW_USB" / "index.html").read_text(encoding="utf-8")
    assert "Open search portal" in gal_index
    assert "open file" in gal_index

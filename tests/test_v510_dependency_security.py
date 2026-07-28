from legal.security.dependency_floor import audit_dependency_floors, version_at_least


def test_version_comparison_handles_stable_and_prerelease():
    assert version_at_least("6.14.2", "6.14.2")
    assert version_at_least("6.14.3", "6.14.2")
    assert not version_at_least("6.1.3", "6.14.2")
    assert not version_at_least("1.3.1rc1", "1.3.1")


def test_safe_core_and_api_versions_pass():
    report = audit_dependency_floors(
        {
            "pypdf": "6.14.2",
            "pypdfium2": "5.12.1",
            "python-docx": "1.2.0",
            "defusedxml": "0.7.1",
            "docx-editor": "0.7.1",
            "fastapi": "0.139.2",
            "starlette": "1.3.1",
            "uvicorn": "0.51.0",
            "httpx": "0.28.1",
        },
        include_api=True,
    )
    assert report.status == "pass"
    assert report.blocked == 0


def test_known_vulnerable_pdf_and_api_versions_are_blocked():
    report = audit_dependency_floors(
        {
            "pypdf": "5.9.0",
            "pypdfium2": "5.12.1",
            "python-docx": "1.1.0",
            "defusedxml": "0.7.1",
            "docx-editor": "0.6.0",
            "fastapi": "0.128.2",
            "starlette": "0.50.0",
            "uvicorn": "0.48.0",
            "httpx": "0.28.1",
        },
        include_api=True,
    )
    assert report.status == "fail"
    findings = {item.distribution: item for item in report.findings}
    assert findings["pypdf"].status == "blocked"
    assert "GHSA-jfx9-29x2-rv3j" in findings["pypdf"].advisory_ids
    assert findings["starlette"].status == "blocked"
    assert "CVE-2026-48710" in findings["starlette"].advisory_ids
    assert findings["python-docx"].status == "blocked"
    assert findings["docx-editor"].status == "blocked"


def test_optional_build_packages_can_be_strictly_checked():
    versions = {
        "pypdf": "6.14.2",
        "pypdfium2": "5.12.1",
        "python-docx": "1.2.0",
        "defusedxml": "0.7.1",
        "docx-editor": "0.7.1",
        "Pillow": "12.3.0",
        "PyInstaller": "6.21.0",
        "pyinstaller-hooks-contrib": "2026.6",
    }
    report = audit_dependency_floors(
        versions,
        include_api=False,
        include_build=True,
        strict_optional=True,
    )
    assert report.status == "pass"

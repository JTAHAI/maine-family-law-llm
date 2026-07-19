from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_store_packaging_files_exist() -> None:
    required = [
        REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec",
        REPO_ROOT / "store" / "pyinstaller" / "requirements-store-build.txt",
        REPO_ROOT / "store" / "msix" / "AppxManifest.xml.in",
        REPO_ROOT / "store" / "msix" / "README.md",
        REPO_ROOT / "store" / "msix" / "identity.example.json",
        REPO_ROOT / "store" / "listing" / "en-US.md",
        REPO_ROOT / "docs" / "FORK_FOR_YOUR_STATE.md",
        REPO_ROOT / "docs" / "PRIVACY_POLICY_MICROSOFT_STORE.html",
        REPO_ROOT / "docs" / "MICROSOFT_STORE_RELEASE.md",
        REPO_ROOT / "docs" / "MSIX_ARCHITECTURE.md",
        REPO_ROOT / "docs" / "MSIX_PRIVACY_BOUNDARIES.md",
        REPO_ROOT / "docs" / "STORE_CERTIFICATION_CHECKLIST.md",
        REPO_ROOT / "scripts" / "build-store-runtime.ps1",
        REPO_ROOT / "scripts" / "test-store-runtime.ps1",
        REPO_ROOT / "scripts" / "build-msix.ps1",
        REPO_ROOT / "scripts" / "install-test-msix.ps1",
        REPO_ROOT / "scripts" / "uninstall-test-msix.ps1",
        REPO_ROOT / "scripts" / "run-wack.ps1",
        REPO_ROOT / ".github" / "workflows" / "build-msix.yml",
    ]
    for path in required:
        assert path.exists(), path


def test_store_runtime_redirects_mutable_state_to_localappdata(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from app.runtime_support import build_runtime_context, configure_runtime_environment

    context = configure_runtime_environment(build_runtime_context(mode="store"))
    assert context.is_store_runtime is True
    assert context.writable_root == tmp_path / "localappdata" / "MaineFamilyLawLLM"
    assert context.writable_root != context.bundle_root
    assert context.allows_repo_bootstrap_writes is False
    assert context.case_library_path.parent == context.writable_root
    assert context.api_state_path.parent == context.writable_root / "state"
    assert context.logs_root == context.writable_root / "logs"


def test_store_launch_path_does_not_download_or_install_prerequisites() -> None:
    launcher_source = (REPO_ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    store_entry_source = (REPO_ROOT / "app" / "store_entrypoint.py").read_text(encoding="utf-8")
    local_service_source = (REPO_ROOT / "app" / "local_api_service.py").read_text(encoding="utf-8")
    combined = "\n".join([launcher_source, store_entry_source, local_service_source]).lower()
    assert "winget" not in combined
    assert "pip install" not in combined
    assert "-m venv" not in combined
    assert "virtualenv" not in combined


def test_store_help_surface_and_listing_link_to_repo_and_fork_guide() -> None:
    from maine_family_law_llm.version import GITHUB_REPOSITORY_URL

    launcher_source = (REPO_ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    listing = (REPO_ROOT / "store" / "listing" / "en-US.md").read_text(encoding="utf-8")
    support = (REPO_ROOT / "store" / "listing" / "support-information.md").read_text(encoding="utf-8")
    assert "GITHUB_REPOSITORY_URL" in launcher_source
    assert "Fork for your state" in launcher_source
    assert "Troubleshooting" in launcher_source
    assert "not affiliated with the Maine Judicial Branch" in launcher_source
    assert GITHUB_REPOSITORY_URL in listing
    assert "Build one for your state" in listing
    assert "Maine authority must not be reused as authority for another jurisdiction." in listing
    assert GITHUB_REPOSITORY_URL in support


def test_store_privacy_policy_and_state_fork_guide_cover_required_boundaries() -> None:
    privacy = (REPO_ROOT / "docs" / "PRIVACY_POLICY_MICROSOFT_STORE.html").read_text(encoding="utf-8")
    fork = (REPO_ROOT / "docs" / "FORK_FOR_YOUR_STATE.md").read_text(encoding="utf-8")
    assert "%LOCALAPPDATA%\\MaineFamilyLawLLM" in privacy
    assert "does not send user matter data to a remote service" in privacy
    assert "Private matter files are not used for shared-model training by default" in privacy
    assert "delete any user-created external matter or corpus folders separately" in privacy.lower()
    assert "official statute connectors" in fork
    assert "attorney review" in fork
    assert "privacy-law review" in fork
    assert "Maine authority as if it applies in another state" in fork


def test_manifest_template_is_valid_xml_after_placeholder_substitution() -> None:
    template = (REPO_ROOT / "store" / "msix" / "AppxManifest.xml.in").read_text(encoding="utf-8")
    rendered = (
        template.replace("__IDENTITY_NAME__", "TAHAIWebServices.MaineFamilyLawLLM")
        .replace("__PUBLISHER__", "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868")
        .replace("__PACKAGE_VERSION__", "2.9.0.0")
        .replace("__PACKAGE_DISPLAY_NAME__", "Maine Family Law LLM")
        .replace("__PUBLISHER_DISPLAY_NAME__", "TAHAI Web Services")
    )
    root = ElementTree.fromstring(rendered)
    assert root.tag.endswith("Package")
    assert "Windows.FullTrustApplication" in rendered
    assert "runFullTrust" in rendered
    assert "MaineFamilyLawLLM.exe" in rendered


def test_store_identity_example_matches_reserved_partner_center_values() -> None:
    identity = json.loads((REPO_ROOT / "store" / "msix" / "identity.example.json").read_text(encoding="utf-8"))
    assert identity["identity_name"] == "TAHAIWebServices.MaineFamilyLawLLM"
    assert identity["publisher"] == "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
    assert identity["publisher_display_name"] == "TAHAI Web Services"
    assert identity["package_display_name"] == "Maine Family Law LLM"


def test_asset_generator_builds_required_pngs(tmp_path) -> None:
    from scripts.generate_msix_assets import build_assets

    brand_root = REPO_ROOT / "assets" / "brand" / "focaf_family_law_llm_brand_kit"
    output_dir = tmp_path / "assets"
    inventory = build_assets(brand_root, output_dir)
    filenames = {row["filename"] for row in inventory}
    assert "Square44x44Logo.png" in filenames
    assert "Square150x150Logo.png" in filenames
    assert "Wide310x150Logo.png" in filenames
    assert "SplashScreen.png" in filenames
    for row in inventory:
        assert (output_dir / str(row["filename"])).is_file()


def test_store_smoke_workflow_runs_and_stays_outside_bundle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from app.store_entrypoint import _run_smoke_workflow

    payload = _run_smoke_workflow(tmp_path / "store-build-smoke.json")
    assert payload["launch_result"] == "pass"
    assert payload["api_health_result"] is True
    assert payload["fictional_sample_workflow_result"] is True
    assert payload["external_data_boundary_verification"] is True


def test_uninstall_script_does_not_delete_user_external_case_folders() -> None:
    script = (REPO_ROOT / "scripts" / "uninstall-test-msix.ps1").read_text(encoding="utf-8")
    assert "Remove-AppxPackage" in script
    assert "Remove-Item" not in script
    assert "default_case_build_root" not in script


def test_no_private_signing_materials_are_committed() -> None:
    forbidden: list[Path] = []
    for suffix in ("*.pfx", "*.pvk", "*.snk"):
        for path in REPO_ROOT.rglob(suffix):
            relative = path.relative_to(REPO_ROOT)
            if relative.parts and relative.parts[0] == "dist":
                continue
            forbidden.append(path)
    assert not forbidden, [str(path) for path in forbidden]


def test_build_msix_script_accepts_identity_inputs_and_writes_evidence() -> None:
    script = (REPO_ROOT / "scripts" / "build-msix.ps1").read_text(encoding="utf-8")
    assert "IdentityConfigPath" in script
    assert "IdentityName" in script
    assert "PublisherDisplayName" in script
    assert "PackageDisplayName" in script
    assert "package-file-manifest.json" in script
    assert "package-sha256.txt" in script
    assert "private-data-audit.json" in script
    assert "store-build-smoke.json" in script


def test_install_msix_script_imports_dev_certificate_into_trusted_stores() -> None:
    script = (REPO_ROOT / "scripts" / "install-test-msix.ps1").read_text(encoding="utf-8")
    assert "X509Certificate2" in script
    assert "Test-IsAdministrator" in script
    assert 'Location = "LocalMachine"' in script
    assert 'Location = "CurrentUser"' in script
    assert "$store.Add($certificate)" in script


def test_store_pyinstaller_spec_collects_corpus_package_modules() -> None:
    spec = (REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    assert '"data"' in spec
    assert "collect_source_package_files" in spec
    assert "README_FOR_NONTECHNICAL_USERS.html" in spec
    assert '"sqlite3"' in spec
    assert '"_sqlite3"' in spec


def test_build_store_runtime_script_stops_existing_packaged_runtime_processes() -> None:
    script = (REPO_ROOT / "scripts" / "build-store-runtime.ps1").read_text(encoding="utf-8")
    assert "Stop-StoreRuntimeProcesses" in script
    assert 'StartsWith($normalizedRoot' in script
    assert "Stop-Process -Id $process.Id -Force" in script
    assert "MaineFamilyLawLLM\\build-venvs\\store" in script
    assert 'Join-Path $RepoRoot ".venv-store-build"' not in script


def test_store_package_audit_allows_bundled_certifi_ca_bundle() -> None:
    script = (REPO_ROOT / "scripts" / "audit_store_package.py").read_text(encoding="utf-8")
    assert "_internal/certifi/cacert.pem" in script


def test_build_msix_script_normalizes_package_versions_without_leading_zero_segments() -> None:
    script = (REPO_ROOT / "scripts" / "build-msix.ps1").read_text(encoding="utf-8")
    assert "Package version segments must be numeric." in script
    assert "$value = [int]$part" in script
    assert '$normalizedParts += $value.ToString()' in script
    assert '2.5.29.37={text}1.3.6.1.5.5.7.3.3' in script
    assert '2.5.29.19={text}' in script
    assert "TAHAIWebServices.MaineFamilyLawLLM" in script
    assert "D75EE668-B409-45ED-87E5-E37AA5FE3868" in script


def test_build_msix_script_rejects_nonzero_store_revision_numbers() -> None:
    script = (REPO_ROOT / "scripts" / "build-msix.ps1").read_text(encoding="utf-8")
    assert '$normalizedParts[3] -ne "0"' in script
    assert "Microsoft Store requires the MSIX revision component to be zero" in script

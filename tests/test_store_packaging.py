from __future__ import annotations

import json
import os
import importlib.util
import zipfile
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
        REPO_ROOT / "docs" / "RUNTIME_FEATURE_DEPENDENCY_MATRIX.md",
        REPO_ROOT / "docs" / "STORE_CERTIFICATION_CHECKLIST.md",
        REPO_ROOT / "scripts" / "build-store-runtime.ps1",
        REPO_ROOT / "scripts" / "test-store-runtime.ps1",
        REPO_ROOT / "scripts" / "prepare_msix_staging.py",
        REPO_ROOT / "scripts" / "store_payload_hygiene.py",
        REPO_ROOT / "scripts" / "audit_msix_staging.py",
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
    authority_root = tmp_path / "external-authority"
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(authority_root))
    monkeypatch.setenv("MFL_AUTHORITY_DATA_ROOT", str(authority_root))
    # configure_runtime_environment intentionally mutates the process for the
    # lifetime of a frozen app. Register every mutation with monkeypatch so a
    # Store-runtime test cannot leak Store mode into later source-mode tests.
    monkeypatch.setenv("MFL_RUNTIME_MODE", "source")
    monkeypatch.setenv("MFL_CASE_LIBRARY_PATH", str(tmp_path / "source-case-library.json"))
    monkeypatch.setenv("MFL_LOCAL_API_STATE_PATH", str(tmp_path / "source-api.json"))
    monkeypatch.setenv("MFL_RUNTIME_LOG_DIR", str(tmp_path / "source-logs"))
    from app.runtime_support import build_runtime_context, configure_runtime_environment

    context = configure_runtime_environment(build_runtime_context(mode="store"))
    assert context.is_store_runtime is True
    assert context.writable_root == tmp_path / "localappdata" / "MaineFamilyLawLLM"
    assert context.writable_root != context.bundle_root
    assert context.allows_repo_bootstrap_writes is False
    assert context.case_library_path.parent == context.writable_root
    assert context.api_state_path.parent == context.writable_root / "state"
    assert context.api_state_path.name == "local_api-store.json"
    assert context.logs_root == context.writable_root / "logs"
    assert os.environ["MAINE_FAMILY_LAW_DATA_ROOT"] == str(context.runtime_data_root)
    assert os.environ["MFL_AUTHORITY_DATA_ROOT"] == str(authority_root)


def test_authority_services_prefer_store_external_authority_boundary(monkeypatch, tmp_path) -> None:
    # Model a bundle and its external state as siblings inside the QA sandbox.
    # Do not require test data on another drive or weaken the production guard.
    bundle_root = tmp_path / "fictional-bundle"
    bundle_root.mkdir()
    monkeypatch.chdir(bundle_root)
    runtime_root = tmp_path / "runtime-data"
    authority_root = tmp_path / "external-authority"
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(runtime_root))
    monkeypatch.setenv("MFL_AUTHORITY_DATA_ROOT", str(authority_root))
    monkeypatch.setenv("MFL_RUNTIME_MODE", "store")

    from app.services import AuthorityLibraryService, AuthorityProductService

    assert AuthorityLibraryService().data_root == authority_root.resolve()
    assert AuthorityProductService().data_root == authority_root.resolve()


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


def test_runtime_feature_dependency_matrix_covers_advertised_advanced_engines() -> None:
    matrix = (REPO_ROOT / "docs" / "RUNTIME_FEATURE_DEPENDENCY_MATRIX.md").read_text(encoding="utf-8")
    for marker in (
        "Presidio privacy detection",
        "Docling document parsing",
        "OCRmyPDF searchable-copy generation",
        "SQLite vector retrieval",
        "Qdrant loopback retrieval client",
        "dist/store/evidence/bundled-engine-inventory.json",
    ):
        assert marker in matrix


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
    assert "<Resources>" in rendered
    assert 'Language="en-us"' in rendered
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


def test_store_smoke_workflow_reports_actual_bundle_boundary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    from app.store_entrypoint import _run_smoke_workflow

    payload = _run_smoke_workflow(tmp_path / "store-build-smoke.json")
    assert payload["launch_result"] == "pass"
    assert payload["api_health_result"] is True
    assert payload["fictional_sample_workflow_result"] is True
    # A repo-contained QA sandbox must be reported as inside the source bundle,
    # not mislabeled external. Normal CI temp paths exercise the outside case.
    expected_external = not Path(payload["sample_case_root"]).is_relative_to(
        Path(payload["bundle_root"])
    )
    assert payload["external_data_boundary_verification"] is expected_external


def test_uninstall_script_does_not_delete_user_external_case_folders() -> None:
    script = (REPO_ROOT / "scripts" / "uninstall-test-msix.ps1").read_text(encoding="utf-8")
    assert "Remove-AppxPackage" in script
    assert "Remove-Item" not in script
    assert "default_case_build_root" not in script


def test_no_private_signing_materials_are_committed() -> None:
    forbidden: list[Path] = []
    # Do not traverse gigabytes of intentionally excluded generated payloads
    # three times before discarding them. Preserve the same source audit scope.
    for parent, directories, files in os.walk(REPO_ROOT):
        if Path(parent) == REPO_ROOT:
            directories[:] = [name for name in directories if name != "dist"]
        for name in files:
            if Path(name).suffix.casefold() in {".pfx", ".pvk", ".snk"}:
                forbidden.append(Path(parent) / name)
    assert not forbidden, [str(path) for path in forbidden]


def test_build_msix_script_accepts_identity_inputs_and_writes_evidence() -> None:
    script = (REPO_ROOT / "scripts" / "build-msix.ps1").read_text(encoding="utf-8")
    assert "IdentityConfigPath" in script
    assert "PackagingRoot" in script
    assert "IdentityName" in script
    assert "PublisherDisplayName" in script
    assert "PackageDisplayName" in script
    assert "package-file-manifest.json" in script
    assert "sealed-msix-payload.json" in script
    assert "private-data-audit.json" in script
    assert "msix-staging-manifest.json" in script
    assert "msix-path-audit.json" in script
    assert "package-map.txt" in script
    assert "test-store-runtime.ps1" in script
    assert "bundled-engine-inventory.json" in script
    assert "Initialize-RepoBuildEnvironment" in script
    assert "bytecode-regeneration-trace.json" in script
    assert "final-runtime-cleanup.json" in script
    assert "final-staging-cleanup.json" in script
    assert "verify-archive" in script
    assert "Resolve-SafeMutableDirectory" in script
    assert "must name a dedicated directory, not a drive root" in script


def test_msix_staging_map_uses_staged_payload_paths() -> None:
    script = (REPO_ROOT / "scripts" / "audit_msix_staging.py").read_text(encoding="utf-8")
    assert "destination_path" in script
    assert 'f"\\"{entry[\'destination_path\']}\\" \\"{entry[\'package_relative_path\']}\\""' in script
    assert "\"{entry['source_path']}\"" not in script
    assert "package_relative_path" in script
    assert '"appxmanifest.xml"' in script


def test_msix_staging_skips_redundant_docx_template_tree() -> None:
    script = (REPO_ROOT / "scripts" / "prepare_msix_staging.py").read_text(encoding="utf-8")
    assert "default-docx-template" in script
    assert "python-docx loads its runtime default template from templates/default.docx" in script


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
    assert 'collect_source_package_files(ROOT / "legal", destination="src/legal")' in spec
    assert "filesystem walk is both deterministic and sufficient" in spec
    assert "collect_submodules(" not in spec
    assert "legal.ops.release_pilot_hardening" in spec
    assert "legal.pilot.real_matter_operations" in spec
    assert "legal.pilot.sandbox_operations" in spec
    assert "legal.release.release_candidate_operations" in spec


def test_store_pyinstaller_spec_includes_the_tracked_docx_runtime() -> None:
    spec = (REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "store" / "pyinstaller" / "requirements-store-build.txt").read_text(encoding="utf-8")
    assert '"docx-editor"' in spec and '"docx_editor"' in spec
    assert 'collect_installed_package_files("docx_editor", destination="docx_editor")' in spec
    assert "docx-editor>=0.7.1,<0.8" in requirements
    assert "python-docx>=1.2.0,<2" in requirements


def test_full_store_tier_bundles_fast_interchange_adapter_runtime() -> None:
    """An admitted external LoRA pack must not trigger a runtime installer."""

    spec = (REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    requirements = (REPO_ROOT / "store" / "pyinstaller" / "requirements-store-build.txt").read_text(encoding="utf-8")
    for package_name in ("peft", "accelerate", "safetensors"):
        assert f"{package_name}>=" in requirements
        assert f'"{package_name}"' in spec
    assert (
        'for package_name in ("peft", "accelerate", "safetensors"):\n'
        '        datas += collect_installed_package_files(package_name, destination=package_name)'
    ) in spec
    assert "legal weights, adapters, registries, and secrets remain external" in spec


def test_fast_interchange_package_runtime_audit_requires_importable_modules(tmp_path: Path) -> None:
    script_path = REPO_ROOT / "scripts" / "verify_fast_interchange_package_runtime.py"
    spec = importlib.util.spec_from_file_location("fast_interchange_package_runtime_audit", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    package = tmp_path / "fixture.msix"
    with zipfile.ZipFile(package, "w") as archive:
        for path in (
            "_internal/peft/__init__.py",
            "_internal/peft-0.20.0.dist-info/METADATA",
            "_internal/accelerate/__init__.py",
            "_internal/accelerate-1.14.0.dist-info/METADATA",
            "_internal/safetensors/__init__.py",
            "_internal/safetensors/_safetensors_rust.pyd",
            "_internal/safetensors-0.8.0.dist-info/METADATA",
        ):
            archive.writestr(path, "fixture")
    result = module.audit_package(package)
    assert result["status"] == "pass_runtime_dependencies_present"
    assert result["packages"]["peft"]["importable"] is True


def test_store_runtime_includes_multipart_support_for_record_upload_routes() -> None:
    requirements = (REPO_ROOT / "store" / "pyinstaller" / "requirements-store-build.txt").read_text(encoding="utf-8")
    spec = (REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")

    assert "python-multipart" in requirements
    assert '"python-multipart"' in spec
    assert '"multipart"' in spec
    assert '"multipart.multipart"' in spec


def test_build_store_runtime_script_stops_existing_packaged_runtime_processes() -> None:
    script = (REPO_ROOT / "scripts" / "build-store-runtime.ps1").read_text(encoding="utf-8")
    assert "Stop-StoreRuntimeProcesses" in script
    assert 'StartsWith($normalizedRoot' in script
    assert "Stop-Process -Id $process.Id -Force" in script
    assert "MaineFamilyLawLLM\\build-venvs\\store" in script
    assert 'Join-Path $RepoRoot ".venv-store-build"' not in script
    assert "Initialize-RepoBuildEnvironment" in script
    assert "-B -m PyInstaller" in script


def test_frozen_smoke_accepts_only_grounded_or_explicit_fail_closed_authority() -> None:
    script = (REPO_ROOT / "scripts" / "test-store-runtime.ps1").read_text(encoding="utf-8")
    assert "$answerGrounded" in script
    assert "$answerFailedClosed" in script
    assert '"official_authority_product_unavailable"' in script
    assert "(-not $answerGrounded -and -not $answerFailedClosed)" in script


def test_payload_hygiene_seals_and_rejects_bytecode_regeneration() -> None:
    script = (REPO_ROOT / "scripts" / "store_payload_hygiene.py").read_text(encoding="utf-8")
    assert "bytecode_regeneration_trace_v1" in script
    assert "sealed_msix_payload_v1" in script
    assert "__pycache__" in script
    assert "verify_archive" in script


def test_bundled_engine_inventory_script_covers_required_offline_stack() -> None:
    script = (REPO_ROOT / "scripts" / "generate_bundled_engine_inventory.py").read_text(encoding="utf-8")
    for marker in (
        "presidio-analyzer",
        "en-core-web-lg",
        "sqlite-vec",
        "docling",
        "ocrmypdf",
        "pypdfium2",
        "pikepdf",
        "fpdf2",
        "uharfbuzz",
        "qdrant-client",
        "bundled_engine_inventory_v1",
    ):
        assert marker in script
    assert '_internal/en_core_web_lg' in script
    assert "enable_load_extension(True)" in script
    assert "_run_frozen_document_worker" in script
    assert '"--document-intelligence-worker"' in script
    assert '"DOCLING_ARTIFACTS_PATH"' in script
    assert "use_threads=True" in script


def test_store_package_audit_allows_bundled_certifi_ca_bundle() -> None:
    script = (REPO_ROOT / "scripts" / "audit_store_package.py").read_text(encoding="utf-8")
    assert "_internal/certifi/cacert.pem" in script
    assert "_internal/grpc/_cython/_credentials/roots.pem" in script


def test_store_package_audit_allows_only_scoped_public_model_weights(tmp_path) -> None:
    from scripts.audit_store_package import audit_stage

    public_model = tmp_path / "store" / "docling" / "models" / "layout" / "model.safetensors"
    public_model.parent.mkdir(parents=True)
    public_model.write_bytes(b"public model fixture")
    assert audit_stage(tmp_path, [])["status"] == "pass"

    unscoped_model = tmp_path / "private-model.safetensors"
    unscoped_model.write_bytes(b"not an approved package path")
    audit = audit_stage(tmp_path, [])
    assert audit["status"] == "fail"
    assert "private-model.safetensors" in audit["blocked_files"]


def test_store_package_audit_returns_nonzero_when_audit_fails() -> None:
    script = (REPO_ROOT / "scripts" / "audit_store_package.py").read_text(encoding="utf-8")
    assert 'return 0 if audit["status"] == "pass" else 2' in script


def test_store_pyinstaller_spec_filters_package_test_submodules() -> None:
    spec = (REPO_ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    assert "collect_runtime_submodules" in spec
    assert "runtime shim" in spec
    assert 'collect_runtime_submodules("maine_family_law_llm")' not in spec
    assert '"app", "legal", "maine_family_law_llm", "fastapi"' not in spec
    assert "module_name.startswith(\"torch.testing._internal\")" in spec
    assert "part == \"tests\"" in spec
    assert '"presidio_analyzer", "tldextract", "docling"' in spec
    assert "presidio_anonymizer" not in spec
    assert "collect_data_files(package_name)" in spec
    assert '"python-docx"' in spec
    assert '"docling-slim", "docling-core", "docling-ibm-models"' in spec


def test_store_runtime_prefetches_real_docling_artifacts() -> None:
    script = (REPO_ROOT / "scripts" / "build-store-runtime.ps1").read_text(encoding="utf-8")
    assert "docling.utils.model_downloader" in script
    assert "docling-project--docling-layout-heron" in script
    assert "docling-project--docling-models" in script
    assert "with_code_formula=False" in script


def test_whisper_provisioning_uses_host_independent_hash_verification() -> None:
    script = (REPO_ROOT / "scripts" / "provision-whisper-engine.ps1").read_text(encoding="utf-8")
    assert "System.Security.Cryptography.SHA256" in script
    assert "(Get-FileHash" not in script


def test_build_msix_script_normalizes_package_versions_without_leading_zero_segments() -> None:
    script = (REPO_ROOT / "scripts" / "build-msix.ps1").read_text(encoding="utf-8")
    assert "Package version segments must be numeric." in script
    assert "$value = [int]$part" in script
    assert '$normalizedParts += $value.ToString()' in script
    assert '2.5.29.37={text}1.3.6.1.5.5.7.3.3' in script
    assert '2.5.29.19={text}' in script
    assert "TAHAIWebServices.MaineFamilyLawLLM" in script
    assert "D75EE668-B409-45ED-87E5-E37AA5FE3868" in script
    assert "Package version revision must be zero" in script


def test_windows_launchers_do_not_depend_on_a_developer_checkout_or_venv() -> None:
    start_test = (REPO_ROOT / "START_LOCAL_TEST.ps1").read_text(encoding="utf-8")
    start_chat = (REPO_ROOT / "START_LOCAL_CHAT.ps1").read_text(encoding="utf-8")
    local_api = (REPO_ROOT / "scripts" / "run-local-api.ps1").read_text(encoding="utf-8")
    local_smoke = (REPO_ROOT / "scripts" / "run-local-smoke.ps1").read_text(encoding="utf-8")
    spin_up = (REPO_ROOT / "scripts" / "local-test-spin-up.ps1").read_text(encoding="utf-8")
    for script in (start_test, start_chat, local_api, local_smoke):
        assert "D:\\dev\\ME_FM_LLM_venv" not in script
        assert '"C:\\dev\\ME_FM_LLM"' not in script
    assert 'Join-Path $repo ".venv"' in start_test
    assert "& $python .\\scripts\\doctor-local-repo.py" in spin_up


def test_cleaner_removes_named_audit_virtual_environments_only_when_requested(tmp_path) -> None:
    import importlib.util

    script = REPO_ROOT / "scripts" / "clean-local-artifacts.py"
    spec = importlib.util.spec_from_file_location("clean_local_artifacts", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clean = module.clean

    audit_venv = tmp_path / ".venv-audit"
    audit_venv.mkdir()
    assert ".venv-audit" not in clean(tmp_path)
    assert audit_venv.exists()
    assert ".venv-audit" in clean(tmp_path, include_venv=True)
    assert not audit_venv.exists()

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path

from corpus_builder_support import REPO_ROOT, assert_root_launchers_exist
from maine_family_law_llm.case_corpus_builder import bootstrap_repository


def test_root_launchers_and_portable_distribution_exist() -> None:
    assets = bootstrap_repository(REPO_ROOT)
    assert_root_launchers_exist(REPO_ROOT)
    portable_root = Path(assets["portable_root"])
    assert (portable_root / "START_MAINE_FAMILY_LAW_LLM.cmd").exists()
    assert (portable_root / "START_HERE.html").exists()
    assert (portable_root / "INSTALL_OR_RUN.html").exists()
    assert (REPO_ROOT / "scripts" / "bootstrap-windows-launcher.ps1").exists()
    assert (REPO_ROOT / "installer" / "install.ps1").exists()
    assert (REPO_ROOT / "installer" / "install.cmd").exists()
    assert (REPO_ROOT / "scripts" / "build-windows-installer.ps1").exists()
    assert (REPO_ROOT / ".github" / "workflows" / "windows-installer.yml").exists()


def test_first_run_wizards_import() -> None:
    from app import launcher, wizard_build_packages, wizard_import_corpus, wizard_new_case, wizard_usb_export, wizard_verify_release

    assert launcher.main is not None
    assert ("Open Review Portal", "open_review_portal") in launcher.ACTION_SPECS
    assert ("Reopen Intake / Add More Evidence", "import_more_evidence") in launcher.ACTION_SPECS
    assert ("Open External Legal-Matter Release", "open_external_release") in launcher.ACTION_SPECS
    assert ("Build Neutral Sample Corpus", "build_sample_case") in launcher.ACTION_SPECS
    assert all(method_name != "rebuild_index" for _, method_name in launcher.ACTION_SPECS)
    assert wizard_new_case.launch_new_case_wizard is not None
    assert wizard_import_corpus.import_additional_corpus is not None
    assert wizard_build_packages.build_role_packages_wizard is not None
    assert wizard_verify_release.verify_release is not None
    assert wizard_usb_export.export_case_to_usb is not None
    assert any(label == "Gmail / Workspace" for label, _ in launcher.SOURCE_GUIDE_SPECS)
    assert any(label == "Outlook / Hotmail" for label, _ in launcher.SOURCE_GUIDE_SPECS)
    assert any(label == "Phone / screenshots" for label, _ in launcher.SOURCE_GUIDE_SPECS)


def test_corpus_build_wizard_renders_nontechnical_source_guide_buttons() -> None:
    from app import launcher

    build_ui_source = inspect.getsource(launcher.CorpusBuildWizard._build_ui)
    assert "Need help getting records out?" in build_ui_source
    assert "These guides walk nontechnical users through Gmail, Outlook, Hotmail, Google Workspace, phone screenshots, attachments, and evidence staging." in build_ui_source
    assert "command=lambda current=guide_path: self._open_guide(current)" in build_ui_source


def test_nontechnical_docs_cover_common_email_and_phone_sources() -> None:
    bootstrap_repository(REPO_ROOT)
    doc_names = [
        "README_FOR_NONTECHNICAL_USERS.html",
        "HOW_TO_ADD_YOUR_CORPUS.html",
        "HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html",
        "HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html",
        "HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html",
        "SYSTEM_REQUIREMENTS.html",
    ]
    for name in doc_names:
        assert (REPO_ROOT / "docs" / name).exists(), name
    readme_html = (REPO_ROOT / "docs" / "README_FOR_NONTECHNICAL_USERS.html").read_text(encoding="utf-8")
    assert "Open Existing Case Corpus" in readme_html
    assert "Reopen Intake / Add More Evidence" in readme_html
    corpus_html = (REPO_ROOT / "docs" / "HOW_TO_ADD_YOUR_CORPUS.html").read_text(encoding="utf-8")
    assert ".eml" in corpus_html
    assert "Do not rely on raw PST/OST/MBOX archives as your only format" in corpus_html
    assert "Documents" in corpus_html
    assert "Downloads" in corpus_html
    gmail_html = (REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html").read_text(encoding="utf-8")
    assert "Google Workspace" in gmail_html
    assert "Google Takeout" in gmail_html
    outlook_html = (REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html").read_text(encoding="utf-8")
    assert "Hotmail" in outlook_html
    assert "Outlook on the web" in outlook_html
    phone_html = (REPO_ROOT / "docs" / "HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html").read_text(encoding="utf-8")
    assert "iPhone" in phone_html
    assert "Android" in phone_html
    requirements_html = (REPO_ROOT / "docs" / "SYSTEM_REQUIREMENTS.html").read_text(encoding="utf-8")
    assert "16 GB RAM" in requirements_html
    assert "Intel i7 or Ryzen 7" in requirements_html


def test_bootstrap_script_reuses_or_installs_prerequisites() -> None:
    script_text = (REPO_ROOT / "scripts" / "bootstrap-windows-launcher.ps1").read_text(encoding="utf-8")
    assert "Python 3.11+" in script_text
    assert "winget" in script_text
    assert "Python.Python.3.11" in script_text
    assert "bootstrap-state.json" in script_text
    assert "Installing or updating required packages" in script_text


def test_launcher_runs_as_raw_source_file_without_installed_package() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy; "
                f"runpy.run_path(r'{(REPO_ROOT / 'app' / 'launcher.py').as_posix()}', run_name='__codex_smoke__')"
            ),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_source_checkout_supports_plain_module_import_without_pythonpath() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import maine_family_law_llm.case_corpus_builder, app.launcher; print('ok')",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


def test_launcher_build_new_case_wrapper_uses_multi_source_wizard(monkeypatch, tmp_path) -> None:
    from app import launcher

    captured: dict[str, object] = {}

    def fake_launch_new_case_wizard(*, repo_root, source_roots, output_root, case_name):
        captured["repo_root"] = repo_root
        captured["source_roots"] = list(source_roots)
        captured["output_root"] = output_root
        captured["case_name"] = case_name
        return {"ok": True}

    monkeypatch.setattr(launcher, "launch_new_case_wizard", fake_launch_new_case_wizard)
    repo_root = tmp_path / "repo"
    source_roots = [tmp_path / "src_one", tmp_path / "src_two"]
    output_root = tmp_path / "output"
    result = launcher.build_new_case_from_sources(repo_root, source_roots, output_root, "Combined Matter")
    assert result == {"ok": True}
    assert captured["repo_root"] == repo_root
    assert captured["source_roots"] == source_roots
    assert captured["output_root"] == output_root
    assert captured["case_name"] == "Combined Matter"


def test_launcher_import_wrapper_uses_multi_source_import_flow(monkeypatch, tmp_path) -> None:
    from app import launcher

    captured: dict[str, object] = {}

    def fake_import_additional_corpus(*, repo_root, existing_case_root, source_roots, output_root, case_name):
        captured["repo_root"] = repo_root
        captured["existing_case_root"] = existing_case_root
        captured["source_roots"] = list(source_roots)
        captured["output_root"] = output_root
        captured["case_name"] = case_name
        return {"ok": True}

    monkeypatch.setattr(launcher, "import_additional_corpus", fake_import_additional_corpus)
    repo_root = tmp_path / "repo"
    existing_case_root = tmp_path / "existing_case"
    source_roots = [tmp_path / "delta_one", tmp_path / "delta_two"]
    output_root = tmp_path / "output"
    result = launcher.import_case_from_sources(repo_root, existing_case_root, source_roots, output_root, "Expanded Matter")
    assert result == {"ok": True}
    assert captured["repo_root"] == repo_root
    assert captured["existing_case_root"] == existing_case_root
    assert captured["source_roots"] == source_roots
    assert captured["output_root"] == output_root
    assert captured["case_name"] == "Expanded Matter"


def test_launcher_source_mentions_workspace_reopen_flow() -> None:
    launcher_text = (REPO_ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    assert "Reopen Intake / Add More Evidence" in launcher_text
    assert "Open workspace folder" in launcher_text
    assert "Add Documents" in launcher_text
    assert "Add Pictures" in launcher_text
    assert "Missing remembered source paths" in launcher_text

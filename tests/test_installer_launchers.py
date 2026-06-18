from __future__ import annotations

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
    assert "Open intake guide" in launcher_text
    assert "Missing remembered source paths" in launcher_text


def test_bootstrap_repository_writes_reopenable_intake_guidance() -> None:
    bootstrap_repository(REPO_ROOT)
    intake_html = (REPO_ROOT / "docs" / "HOW_TO_ADD_YOUR_CORPUS.html").read_text(encoding="utf-8")
    readme_html = (REPO_ROOT / "docs" / "README_FOR_NONTECHNICAL_USERS.html").read_text(encoding="utf-8")
    start_here = (REPO_ROOT / "START_HERE.html").read_text(encoding="utf-8")
    assert "Reopen Intake / Add More Evidence" in intake_html
    assert "Downloads" in intake_html
    assert "Pictures" in intake_html
    assert "Reopen Intake / Add More Evidence" in readme_html
    assert "How to add your corpus" in start_here

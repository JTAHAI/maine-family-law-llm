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

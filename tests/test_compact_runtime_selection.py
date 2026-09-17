"""Actual child bootstrap tests, without loading a model or ambient .pth files."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange import compact_ranker_process as process


def test_selected_runtime_matches_loaded_dependencies():
    root = process.selected_runtime_site()
    assert root == Path(psutil.__file__).resolve().parent.parent
    assert root.name == "site-packages"


def test_mixed_runtime_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        process.metadata, "distribution", lambda _: SimpleNamespace(locate_file=lambda _: tmp_path)
    )
    with pytest.raises(LocalModelError) as caught:
        process.selected_runtime_site()
    assert caught.value.code == "fast_interchange_reranker_mixed_runtime_forbidden"


def test_bootstrap_ignores_pth_and_ambient_pythonpath(tmp_path):
    site = tmp_path / "Lib" / "site-packages"
    site.mkdir(parents=True)
    (site / "fixture_selected.py").write_text("value = 'selected'\n")
    (site / "malicious.pth").write_text("import sys; sys.exit(79)\n")
    (site / "sitecustomize.py").write_text("raise RuntimeError('must not execute')\n")
    (tmp_path / "fixture_selected.py").write_text("value = 'ambient'\n")
    code = process.WORKER_BOOTSTRAP.split(
        "from legal.fast_interchange.compact_ranker_worker import main;"
    )[0] + (
        "import fixture_selected,json;print(json.dumps(dict(value=fixture_selected.value,"
        "no_site=sys.flags.no_site,site_loaded='site' in sys.modules)))"
    )
    child = subprocess.run(
        [psutil.Process().exe(), "-I", "-S", "-B", "-c", code, str(site), str(site)],
        cwd=tmp_path,
        env={"PYTHONPATH": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {"value": "selected", "no_site": 1, "site_loaded": False}


def test_real_child_imports_selected_versions_only(tmp_path):
    root = process.selected_runtime_site()
    code = process.WORKER_BOOTSTRAP.replace(
        "raise SystemExit(main())",
        "import importlib.metadata as m,json;"
        "print(json.dumps({n:dict(version=m.version(n),"
        "selected=Path(m.distribution(n).locate_file('')).resolve()==_site.resolve()) "
        "for n in ['torch','transformers','safetensors','cryptography','psutil']}))",
    )
    child = subprocess.run(
        [psutil.Process().exe(), "-I", "-S", "-B", "-c", code, str(root), str(Path.cwd())],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        # This checks selected dependency identity, not a 15-second cold-start
        # SLA. Source compilation must fit the actual worker's warm deadline;
        # real startup timings are recorded separately, not hidden by this test.
        timeout=90,
    )
    assert child.returncode == 0, child.stderr
    for name, row in json.loads(child.stdout).items():
        assert row == {"version": process.metadata.version(name), "selected": True}

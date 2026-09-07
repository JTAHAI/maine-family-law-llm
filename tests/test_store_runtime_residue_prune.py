from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_prune_store_runtime_residue_only_removes_test_and_bytecode_paths(tmp_path) -> None:
    from scripts.prune_store_runtime_residue import prune

    runtime = tmp_path / "runtime"
    keep = runtime / "_internal" / "spacy" / "language.py"
    fixture = runtime / "_internal" / "spacy" / "tests" / "fixture.json"
    cache = runtime / "_internal" / "faker" / "__pycache__" / "provider.pyc.42"
    for path in (keep, fixture, cache):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fictional")

    planned = prune(runtime, apply=False)
    assert planned["status"] == "planned"
    assert {row["path"] for row in planned["removed"]} == {
        "_internal/faker/__pycache__/provider.pyc.42",
        "_internal/spacy/tests/fixture.json",
    }
    assert keep.is_file() and fixture.is_file() and cache.is_file()

    applied = prune(runtime, apply=True)
    assert applied["status"] == "applied"
    assert keep.read_bytes() == b"fictional"
    assert not fixture.exists()
    assert not cache.exists()


def test_store_runtime_build_runs_residue_prune_before_smoke() -> None:
    script = (REPO_ROOT / "scripts" / "build-store-runtime.ps1").read_text(encoding="utf-8")
    assert "prune_store_runtime_residue.py" in script
    assert "store-runtime-residue-prune.json" in script
    assert script.index("prune_store_runtime_residue.py") < script.index("test-store-runtime.ps1")

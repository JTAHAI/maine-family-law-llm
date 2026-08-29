"""Pruning preserves source/privacy findings without scanning packaged engines."""

from pathlib import Path

from legal.release.release_manifest import ReleaseManifest
from legal.release.source_tree import pruned_source_paths


def test_excluded_trees_are_never_descended_but_private_state_is_flagged(tmp_path, monkeypatch):
    for relative in (
        "dist/nested/ignored.db",
        "pkg.egg-info/metadata.txt",
        "runtime/private.db",
        "legal/runtime/public.py",
        "application.py",
        "settings.env",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fictional", encoding="utf-8")
    import os

    original = os.scandir
    visited = []

    def guarded(path):
        visited.append(Path(path).relative_to(tmp_path).as_posix())
        assert "dist" not in Path(path).relative_to(tmp_path).parts
        assert "pkg.egg-info" not in Path(path).relative_to(tmp_path).parts
        return original(path)

    monkeypatch.setattr(os, "scandir", guarded)
    findings = {row.path for row in ReleaseManifest(tmp_path).scan_release_tree()}
    assert "runtime/private.db" in findings and "settings.env" in findings
    assert "legal/runtime/public.py" not in findings
    assert not any(name.startswith("dist/") for name in findings)


def test_source_traversal_matches_legacy_filter_on_regular_files(tmp_path):
    for relative in (
        "src/a.py",
        "src/nested/b.txt",
        "legal/runtime/c.py",
        "build/out.txt",
        "dist/data.txt",
        ".venv/site.py",
        "meta.egg-info/version.txt",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    excluded = {"build", "dist", ".venv"}
    expected = {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if not any(
            part in excluded or part.endswith(".egg-info")
            for part in path.relative_to(tmp_path).parts
        )
    }
    actual = {
        path.relative_to(tmp_path).as_posix() for path in pruned_source_paths(tmp_path, excluded)
    }
    assert actual == expected

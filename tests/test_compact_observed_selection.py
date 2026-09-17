"""Observation cannot silently become qualification or erase unmet dependencies."""

import pytest

from scripts.plan_compact_observed_selection import select_observed


def test_selection_keeps_notices_and_unaccounted_paths_without_promotion():
    rows = [
        dict(path=name, bytes=1, sha256="a" * 64)
        for name in (
            "package_runtime/lib/source.py",
            "package_runtime/lib/unused.py",
            "package_runtime/foo.dist-info/METADATA",
            "supplemental_notices/LICENSE.txt",
        )
    ]
    trace = dict(
        schema="compact_observed_runtime_trace_v1",
        observed_only=True,
        modules=["package_runtime/lib/source.py"],
        opened=["package_runtime/lib/missing.pyc"],
        native_mappings=["windows/System32/example.dll"],
    )
    result = select_observed(rows, [trace])
    assert result["selected_files"] == result["selected_bytes"] == 3
    assert result["unaccounted_observed_runtime_paths"] == ["package_runtime/lib/missing.pyc"]
    assert result["observed_cached_bytecode_paths"] == ["package_runtime/lib/missing.pyc"]
    for field in (
        "enforced_import_allowlist",
        "native_closure_qualified",
        "production_admitted",
        "ga_ready",
    ):
        assert result[field] is False


def test_duplicate_inventory_cannot_shrink_budget():
    row = dict(path="package_runtime/x.py", bytes=10, sha256="a" * 64)
    with pytest.raises(ValueError, match="duplicate_inventory_path"):
        select_observed([row, row], [])


def test_unknown_report_is_not_runtime_trace():
    with pytest.raises(ValueError, match="not_an_observed_trace"):
        select_observed([], [dict(schema="fake", observed_only=True)])

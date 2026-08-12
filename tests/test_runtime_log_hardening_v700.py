from __future__ import annotations

from pathlib import Path

import pytest

from app import runtime_support
from app.runtime_support import RuntimeContext, append_runtime_log, build_runtime_context


def _context(tmp_path: Path) -> RuntimeContext:
    root = tmp_path / "bundle"
    return RuntimeContext(
        mode="store",
        bundle_root=root,
        writable_root=tmp_path / "writable",
        logs_root=tmp_path / "logs",
        runtime_data_root=tmp_path / "runtime-data",
        case_library_path=tmp_path / "case-library.json",
        api_state_path=tmp_path / "state" / "api.json",
        first_run_marker=tmp_path / "state" / "first-run.json",
        is_frozen=True,
    )


def test_runtime_log_is_bounded_and_accepts_safe_diagnostics(tmp_path: Path) -> None:
    context = _context(tmp_path)
    path = append_runtime_log(context, "first event")
    assert path.read_text(encoding="utf-8") == "first event\n"

    path.write_bytes(b"x" * (512 * 1024))
    append_runtime_log(context, "second event")
    content = path.read_text(encoding="utf-8")
    assert "retention limit" in content
    assert content.endswith("second event\n")
    assert path.stat().st_size < 512 * 1024


def test_runtime_log_refuses_symlinked_destination(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.logs_root.mkdir()
    outside = tmp_path / "outside.log"
    outside.write_text("outside", encoding="utf-8")
    log_path = context.logs_root / "store-runtime.log"
    try:
        log_path.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with pytest.raises(RuntimeError, match="cannot be written safely"):
        append_runtime_log(context, "must not follow a link")


def test_runtime_context_rejects_unsafe_mode_and_relative_appdata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MFL_RUNTIME_MODE", "..\\outside")
    with pytest.raises(ValueError, match="Runtime mode"):
        build_runtime_context()

    monkeypatch.delenv("MFL_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", ".\\unsafe-relative-root")
    assert runtime_support._local_appdata_root() == Path.home() / "AppData" / "Local"

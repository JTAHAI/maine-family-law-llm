"""Render the bundled v3 local family-justice workbench."""

from __future__ import annotations

import sys
from pathlib import Path

from .version import BUILD_NUMBER, PACKAGE_VERSION, UI_FOOTER_LABEL, UI_PASS_MARKER, UI_VERSION, VERSION


def ui_asset_root() -> Path:
    """Return the filesystem directory containing bundled workbench assets."""

    candidates = [Path(__file__).resolve().parent / "ui"]
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        frozen_root = Path(bundle_root)
        candidates.extend(
            [
                frozen_root / "maine_family_law_llm" / "ui",
                frozen_root / "src" / "maine_family_law_llm" / "ui",
            ]
        )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise RuntimeError("bundled_workbench_assets_missing")


def read_workbench_asset(name: str) -> str:
    """Read a bundled UTF-8 UI asset by safe leaf name."""

    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("invalid_workbench_asset_name")
    path = ui_asset_root() / name
    if not path.is_file():
        raise FileNotFoundError(f"workbench_asset_not_found:{name}")
    return path.read_text(encoding="utf-8")


def render_local_workbench_html() -> str:
    """Return the dependency-free local workbench shell."""

    return (
        read_workbench_asset("workbench.html")
        .replace("{{UI_VERSION}}", UI_VERSION)
        .replace("{{UI_PASS_MARKER}}", UI_PASS_MARKER)
        .replace("{{UI_FOOTER_LABEL}}", UI_FOOTER_LABEL)
        .replace("{{PRODUCT_VERSION}}", VERSION)
        .replace("{{BUILD_NUMBER}}", str(BUILD_NUMBER))
        .replace("{{PACKAGE_VERSION}}", PACKAGE_VERSION)
    )

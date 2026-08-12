from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "maine_family_law_llm"

if _SRC_PACKAGE.is_dir():
    # Point the compatibility package at the canonical src-layout package
    # without executing source text dynamically.
    __path__ = [str(_SRC_PACKAGE)]

from .version import VERSION

__all__ = ["__version__"]
__version__ = VERSION

from __future__ import annotations

import importlib
import sys
from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "maine_family_law_llm"

if _SRC_PACKAGE.exists():
    __path__ = [str(_SRC_PACKAGE)]
    exec((_SRC_PACKAGE / "__init__.py").read_text(encoding="utf-8"), globals())
else:
    __all__ = ["__version__"]
    __version__ = importlib.import_module("maine_family_law_llm.version").VERSION

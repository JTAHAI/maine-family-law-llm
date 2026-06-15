from __future__ import annotations

from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "maine_family_law_llm"
__path__ = [str(_SRC_PACKAGE)]

exec((_SRC_PACKAGE / "__init__.py").read_text(encoding="utf-8"), globals())

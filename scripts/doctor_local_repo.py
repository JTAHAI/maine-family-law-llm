#!/usr/bin/env python3
"""Compatibility wrapper for scripts/doctor-local-repo.py.

Some operator snippets used an underscore path. Keep this wrapper so both
commands work from a clean checkout:

    python scripts/doctor_local_repo.py
    python scripts/doctor-local-repo.py
"""

from __future__ import annotations

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("doctor-local-repo.py")), run_name="__main__")

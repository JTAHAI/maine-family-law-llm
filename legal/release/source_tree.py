"""Traverse source without descending into explicitly excluded build outputs."""

from __future__ import annotations

import os
from pathlib import Path


def pruned_source_paths(root: Path, excluded: set[str], *, exclude_egg_info=True):
    def ignored(name):
        return name in excluded or (exclude_egg_info and name.endswith(".egg-info"))

    def failed(error):
        raise error  # An unreadable source subtree is not an audit pass.

    for current, directories, files in os.walk(
        root, topdown=True, followlinks=False, onerror=failed
    ):
        directories[:] = sorted(name for name in directories if not ignored(name))
        for name in [*directories, *sorted(files)]:
            if not ignored(name):
                yield Path(current) / name

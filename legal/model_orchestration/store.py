from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from legal.ops.release_pilot_hardening import _safe_external_root, ReleasePilotHardeningError

DEFAULT_MODEL_DIRNAME = "model_store"
DEFAULT_MODEL_NAMESPACE = "maine-family-law-llm"
FORBIDDEN_SEGMENTS = {
    "matter",
    "matter_store",
    "matterstore",
    "msix",
    "msix_stage",
    "stage",
    "staging",
    "windows",
    "windowsapps",
    "program files",
    "program files (x86)",
    "programdata",
    "system32",
}
WINDOWS_DRIVE_RE = re.compile(r"(?i)^[a-z]:[\\/]")


class ModelStoreRootError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _casefold_parts(path: Path) -> set[str]:
    parts = {part.casefold() for part in path.parts}
    if path.drive:
        parts.add(path.drive.casefold())
    return parts


def _contains_forbidden_segment(path: Path, forbidden: Iterable[str]) -> str:
    parts = _casefold_parts(path)
    for candidate in forbidden:
        folded = candidate.casefold()
        for part in parts:
            if folded == part or folded in part or part in folded:
                return candidate
    return ""


def _looks_like_traversal(path: str) -> bool:
    raw = str(path or "")
    return ".." in Path(raw).parts or bool(WINDOWS_DRIVE_RE.search(raw) and raw.count("..") > 0)


def default_external_model_root(project_root: str | Path = ".") -> Path:
    project = Path(project_root).resolve()
    namespace = project.name or DEFAULT_MODEL_NAMESPACE
    return Path.home() / ".codex" / DEFAULT_MODEL_DIRNAME / namespace


def resolve_external_model_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    project = Path(project_root).resolve()
    if configured is None or not str(configured).strip():
        candidate = default_external_model_root(project)
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    raw = str(configured).strip()
    if _looks_like_traversal(raw):
        raise ModelStoreRootError(
            "model_store_path_traversal",
            "The model store root path contains a traversal segment.",
        )

    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise ModelStoreRootError(
            "model_store_symlink_refused",
            "The model store root cannot be a symlink.",
        )

    try:
        candidate = _safe_external_root(path, repo_root=project, create=create)
    except ReleasePilotHardeningError as exc:
        raise ModelStoreRootError(exc.code, str(exc), status_code=exc.status_code) from exc

    forbidden = _contains_forbidden_segment(candidate, FORBIDDEN_SEGMENTS)
    if forbidden:
        raise ModelStoreRootError(
            "model_store_inside_forbidden_root",
            f"The model store root cannot live inside forbidden directory segment: {forbidden}.",
        )
    if candidate.exists() and candidate.is_symlink():
        raise ModelStoreRootError(
            "model_store_symlink_refused",
            "The model store root cannot be a symlink.",
        )
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


@dataclass(frozen=True)
class ModelStoreLayout:
    root: Path

    @property
    def registry(self) -> Path:
        return self.root / "registry"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def runtime_profiles(self) -> Path:
        return self.root / "runtime_profiles"

    @property
    def benchmark_runs(self) -> Path:
        return self.root / "benchmark_runs"

    @property
    def health(self) -> Path:
        return self.root / "health"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    @property
    def routing(self) -> Path:
        return self.root / "routing"

    def ensure(self) -> None:
        for path in (
            self.registry,
            self.artifacts,
            self.runtime_profiles,
            self.benchmark_runs,
            self.health,
            self.logs,
            self.cache,
            self.quarantine,
            self.routing,
        ):
            path.mkdir(parents=True, exist_ok=True)


def external_model_store_layout(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = True,
) -> ModelStoreLayout:
    root = resolve_external_model_root(configured, project_root=project_root, create=create)
    layout = ModelStoreLayout(root=root)
    if create:
        layout.ensure()
    return layout

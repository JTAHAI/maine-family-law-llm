from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable

DEFAULT_PROVIDER_DIRNAME = "provider_store"
DEFAULT_PROVIDER_NAMESPACE = "maine-family-law-llm"
WINDOWS_DRIVE_RE = re.compile(r"(?i)^[a-z]:[\\/]")


class ProviderStoreRootError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _looks_like_traversal(path: str) -> bool:
    raw = str(path or "")
    return ".." in Path(raw).parts or bool(WINDOWS_DRIVE_RE.search(raw) and raw.count("..") > 0)


def _contains_forbidden_segment(path: Path, forbidden: Iterable[str]) -> str:
    parts = {part.casefold() for part in path.parts}
    if path.drive:
        parts.add(path.drive.casefold())
    for candidate in forbidden:
        folded = candidate.casefold()
        for part in parts:
            if folded == part or folded in part or part in folded:
                return candidate
    return ""


def default_external_provider_root(project_root: str | Path = ".") -> Path:
    project = Path(project_root).resolve()
    namespace = project.name or DEFAULT_PROVIDER_NAMESPACE
    return Path.home() / ".codex" / DEFAULT_PROVIDER_DIRNAME / namespace


def resolve_external_provider_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    project = Path(project_root).resolve()
    if configured is None or not str(configured).strip():
        candidate = default_external_provider_root(project)
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    raw = str(configured).strip()
    if _looks_like_traversal(raw):
        raise ProviderStoreRootError("provider_store_path_traversal", "The provider store root path contains a traversal segment.")

    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise ProviderStoreRootError("provider_store_symlink_refused", "The provider store root cannot be a symlink.")

    path = path.resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    forbidden = _contains_forbidden_segment(path, {"matter", "matter_store", "msix", "staging", "windows", "system32"})
    if forbidden:
        raise ProviderStoreRootError(
            "provider_store_inside_forbidden_root",
            f"The provider store root cannot live inside forbidden directory segment: {forbidden}.",
        )
    return path


@dataclass(frozen=True)
class ProviderStoreLayout:
    root: Path

    @property
    def connections(self) -> Path:
        return self.root / "connections"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    @property
    def audit(self) -> Path:
        return self.root / "audit"

    @property
    def usage(self) -> Path:
        return self.root / "usage"

    def ensure(self) -> None:
        for path in (self.connections, self.manifests, self.sessions, self.audit, self.usage):
            path.mkdir(parents=True, exist_ok=True)


def external_provider_store_layout(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = True,
) -> ProviderStoreLayout:
    root = resolve_external_provider_root(configured, project_root=project_root, create=create)
    layout = ProviderStoreLayout(root=root)
    if create:
        layout.ensure()
    return layout

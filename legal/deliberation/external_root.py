from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from legal.ops.release_pilot_hardening import _safe_external_root, ReleasePilotHardeningError

DEFAULT_DELIBERATION_DIRNAME = "deliberation_store"
DEFAULT_DELIBERATION_NAMESPACE = "maine-family-law-llm"
FORBIDDEN_SEGMENTS = {
    "matter",
    "matter_store",
    "model_store",
    "msix",
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


class DeliberationRootError(RuntimeError):
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


def default_external_deliberation_root(project_root: str | Path = ".") -> Path:
    project = Path(project_root).resolve()
    namespace = project.name or DEFAULT_DELIBERATION_NAMESPACE
    return Path.home() / ".codex" / DEFAULT_DELIBERATION_DIRNAME / namespace


def resolve_external_deliberation_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    project = Path(project_root).resolve()
    if configured is None or not str(configured).strip():
        candidate = default_external_deliberation_root(project)
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    raw = str(configured).strip()
    if _looks_like_traversal(raw):
        raise DeliberationRootError(
            "deliberation_root_path_traversal",
            "The deliberation root path contains a traversal segment.",
        )

    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise DeliberationRootError("deliberation_root_symlink_refused", "The deliberation root cannot be a symlink.")

    try:
        candidate = _safe_external_root(path, repo_root=project, create=create)
    except ReleasePilotHardeningError as exc:
        raise DeliberationRootError(exc.code, str(exc), status_code=exc.status_code) from exc

    forbidden = _contains_forbidden_segment(candidate, FORBIDDEN_SEGMENTS)
    if forbidden:
        raise DeliberationRootError(
            "deliberation_root_inside_forbidden_root",
            f"The deliberation root cannot live inside forbidden directory segment: {forbidden}.",
        )
    if candidate.exists() and candidate.is_symlink():
        raise DeliberationRootError("deliberation_root_symlink_refused", "The deliberation root cannot be a symlink.")
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


@dataclass(frozen=True)
class DeliberationLayout:
    root: Path

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def events(self) -> Path:
        return self.root / "events"

    @property
    def claims(self) -> Path:
        return self.root / "claims"

    @property
    def positions(self) -> Path:
        return self.root / "positions"

    @property
    def synthesis(self) -> Path:
        return self.root / "synthesis"

    @property
    def tool_audit(self) -> Path:
        return self.root / "tool_audit"

    @property
    def snapshots(self) -> Path:
        return self.root / "snapshots"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def quarantine(self) -> Path:
        return self.root / "quarantine"

    def ensure(self) -> None:
        for path in (
            self.runs,
            self.events,
            self.claims,
            self.positions,
            self.synthesis,
            self.tool_audit,
            self.snapshots,
            self.logs,
            self.quarantine,
        ):
            path.mkdir(parents=True, exist_ok=True)


def external_deliberation_layout(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = True,
) -> DeliberationLayout:
    root = resolve_external_deliberation_root(configured, project_root=project_root, create=create)
    layout = DeliberationLayout(root=root)
    if create:
        layout.ensure()
    return layout

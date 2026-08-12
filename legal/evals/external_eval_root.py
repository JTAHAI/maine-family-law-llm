from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from legal.ops.release_pilot_hardening import _safe_external_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL_DIRNAME = "eval_store"
DEFAULT_EVAL_NAMESPACE = "maine-family-law-llm"
FORBIDDEN_SEGMENTS = {
    "02_private_forensic_master",
    "02_private_forensic_master",
    "02_private",
    "private",
    "private_matter",
    "private_matter_store",
    "matter_store",
    "eval_data",
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


class ExternalEvalRootError(RuntimeError):
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
    return ".." in Path(raw).parts or WINDOWS_DRIVE_RE.search(raw) is not None and raw.count("..") > 0


def default_external_eval_root(project_root: str | Path = ".") -> Path:
    """Return the user-local eval store root outside the source repository."""

    project = Path(project_root).resolve()
    namespace = project.name or DEFAULT_EVAL_NAMESPACE
    home = Path.home()
    candidate = home / ".codex" / DEFAULT_EVAL_DIRNAME / namespace
    return resolve_external_eval_root(candidate, project_root=project, create=True)


def resolve_external_eval_root(
    configured: str | Path | None,
    *,
    project_root: str | Path = ".",
    create: bool = False,
) -> Path:
    """Resolve an external eval root with fail-closed containment checks."""

    project = Path(project_root).resolve()
    if configured is None or not str(configured).strip():
        candidate = default_external_eval_root(project)
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        return candidate

    raw = str(configured).strip()
    if _looks_like_traversal(raw):
        raise ExternalEvalRootError(
            "external_eval_root_path_traversal",
            "The evaluation root path contains a traversal segment.",
        )

    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise ExternalEvalRootError(
            "external_eval_root_symlink_refused",
            "The evaluation root cannot be a symlink.",
        )

    try:
        candidate = _safe_external_root(path, repo_root=project, create=create)
    except Exception as exc:  # pragma: no cover - delegated fail-closed guard
        code = getattr(exc, "code", "external_eval_root_unavailable")
        message = getattr(exc, "message", str(exc))
        status_code = getattr(exc, "status_code", 409)
        raise ExternalEvalRootError(code, message, status_code=status_code) from exc

    forbidden = _contains_forbidden_segment(candidate, FORBIDDEN_SEGMENTS)
    if forbidden:
        raise ExternalEvalRootError(
            "external_eval_root_inside_forbidden_root",
            f"The evaluation root cannot live inside forbidden directory segment: {forbidden}.",
        )
    if candidate.exists() and candidate.is_symlink():
        raise ExternalEvalRootError(
            "external_eval_root_symlink_refused",
            "The evaluation root cannot be a symlink.",
        )
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


@dataclass(frozen=True)
class ExternalEvalRootLayout:
    root: Path

    @property
    def annotation_queue(self) -> Path:
        return self.root / "annotation_queue"

    @property
    def assignments(self) -> Path:
        return self.root / "assignments"

    @property
    def reviews(self) -> Path:
        return self.root / "reviews"

    @property
    def adjudications(self) -> Path:
        return self.root / "adjudications"

    @property
    def promoted_gold(self) -> Path:
        return self.root / "promoted_gold"

    @property
    def datasets(self) -> Path:
        return self.root

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def metrics(self) -> Path:
        return self.root / "metrics"

    @property
    def failure_clusters(self) -> Path:
        return self.root / "failure_clusters"

    @property
    def release_comparisons(self) -> Path:
        return self.root / "release_comparisons"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def audit(self) -> Path:
        return self.root / "audit"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    def ensure(self) -> None:
        for path in (
            self.annotation_queue,
            self.assignments,
            self.reviews,
            self.adjudications,
            self.promoted_gold,
            self.runs,
            self.metrics,
            self.failure_clusters,
            self.release_comparisons,
            self.exports,
            self.audit,
            self.schemas,
        ):
            path.mkdir(parents=True, exist_ok=True)


def external_eval_root_layout(configured: str | Path | None, *, project_root: str | Path = ".", create: bool = True) -> ExternalEvalRootLayout:
    root = resolve_external_eval_root(configured, project_root=project_root, create=create)
    layout = ExternalEvalRootLayout(root=root)
    if create:
        layout.ensure()
    return layout

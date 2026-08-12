from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from legal.data_boundaries.data_classes import StoreName, coerce_store


@dataclass(frozen=True)
class StorePath:
    name: StoreName
    path: Path
    encrypted_required: bool
    packaged_allowed: bool = False


_ENCRYPTED_STORES = {StoreName.MATTER, StoreName.AUDIT}
_DEFAULT_EXTERNAL_DATA_ROOT_ENV = "MAINE_FAMILY_LAW_DATA_ROOT"


def _local_appdata_root() -> Path:
    base = os.environ.get("LOCALAPPDATA", "").strip()
    if base:
        return Path(base)
    return Path.home() / "AppData" / "Local"


def default_external_data_root(
    project_root: Path | str = ".",
    *,
    env_var: str = _DEFAULT_EXTERNAL_DATA_ROOT_ENV,
    app_name: str = "MaineFamilyLawLLM",
    leaf_name: str = "authority-data",
) -> Path:
    configured = os.environ.get(env_var)
    if configured:
        return Path(configured).expanduser().resolve()
    return (_local_appdata_root() / app_name / leaf_name).resolve()


def data_root(project_root: Path | str = ".", env_var: str = "MAINE_FAMILY_LAW_DATA_ROOT") -> Path:
    configured = os.environ.get(env_var)
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path(project_root).resolve() / ".local_data").resolve()


def store_path(store_name: StoreName | str, project_root: Path | str = ".") -> StorePath:
    store = coerce_store(store_name)
    path = data_root(project_root) / store.value
    return StorePath(
        name=store,
        path=path,
        encrypted_required=store in _ENCRYPTED_STORES,
        packaged_allowed=False,
    )


def all_store_paths(project_root: Path | str = ".") -> list[StorePath]:
    return [store_path(store, project_root=project_root) for store in StoreName]


def is_inside_project_repo(path: Path | str, project_root: Path | str = ".") -> bool:
    root = Path(project_root).resolve()
    candidate = Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def is_inside_any(path: Path | str, roots: tuple[Path | str, ...]) -> bool:
    candidate = Path(path).resolve()
    for root in roots:
        try:
            candidate.relative_to(Path(root).resolve())
        except ValueError:
            continue
        return True
    return False


def ensure_external_authority_root(
    path: Path | str,
    *,
    project_root: Path | str = ".",
    extra_forbidden_roots: tuple[Path | str, ...] = (),
) -> Path:
    root = Path(path).expanduser().resolve()
    if is_inside_project_repo(root, project_root):
        raise ValueError("authority data root must be outside the source repository")
    forbidden_roots = list(extra_forbidden_roots)
    if os.name == "nt":
        forbidden_roots.extend(
            [
                os.environ.get("WINDIR", r"C:\\Windows"),
                os.environ.get("ProgramFiles", r"C:\\Program Files"),
                os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"),
            ]
        )
    if forbidden_roots and is_inside_any(root, tuple(forbidden_roots)):
        raise ValueError("authority data root may not be inside a forbidden workspace or system directory")
    return root


def create_store_layout(project_root: Path | str = ".") -> list[StorePath]:
    stores = all_store_paths(project_root)
    for store in stores:
        store.path.mkdir(parents=True, exist_ok=True)
    return stores

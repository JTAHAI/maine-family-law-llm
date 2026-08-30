"""Model-empty, loopback-only shared-base LoRA worker.

The desktop host owns legal policy, matter authorization, exact-context
approval, source provenance, and review gates.  This module is only a narrow
inference appliance.  It never downloads an artifact or accepts caller paths,
adapter IDs, tools, streaming, or free sampling controls.
"""

from __future__ import annotations

import asyncio
import gc
import hashlib
import hmac
import ipaddress
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Event, RLock
from typing import Any, Protocol

from legal.security.strict_json import strict_json_load_path, strict_json_loads

from .admission import AdmissionAuthority, AdmissionError, AdmissionGrant
from .fleet import FAST_INTERCHANGE_CAPABILITIES
from .snapshot import SnapshotError, VerifiedSnapshot

try:  # Keep the model-empty package importable without the optional API extra.
    from starlette.requests import Request as WorkerRequest
except ImportError:  # pragma: no cover - exercised only without the API extra
    WorkerRequest = Any  # type: ignore[misc,assignment]


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ADMITTED = frozenset({"admitted_for_dev", "admitted_with_limits", "admitted_for_production"})
_REQUEST_KEYS = frozenset({"model", "messages", "temperature", "top_p", "max_tokens", "stream"})
_REQUEST_KEYS_V2 = _REQUEST_KEYS | {"request_id", "capability", "release_fingerprint"}
_MAX_BODY_BYTES = 160 * 1024
_MAX_PROMPT_TOKENS = 2048
_MAX_COMPLETION_TOKENS = 1024
_MAX_COMPLETION_CHARS = 120_000
_FIXED_ROLE_PROMPT_TEMPLATE = "fi-fixed-role-v1:[{role}]\\n{content}"


class FastInterchangeError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any, code: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _ID.fullmatch(candidate):
        raise FastInterchangeError(code)
    return candidate


def _sha(value: Any, code: str) -> str:
    candidate = str(value or "").strip().lower()
    if not _SHA256.fullmatch(candidate):
        raise FastInterchangeError(code)
    return candidate


def _relative(value: Any, code: str) -> str:
    candidate = str(value or "").replace("\\", "/").strip()
    path = Path(candidate)
    if (
        not candidate
        or path.is_absolute()
        or candidate.startswith("/")
        or any(
            part in {"", ".", ".."} or part.endswith((".", " ")) for part in candidate.split("/")
        )
        or re.search(r"[^A-Za-z0-9_./-]", candidate)
        or any(
            part.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(10)),
                *(f"LPT{i}" for i in range(10)),
            }
            for part in candidate.split("/")
        )
    ):
        raise FastInterchangeError(code)
    return candidate


def _inside(root: Path, relative: str, code: str) -> Path:
    root = root.resolve()
    candidate = root
    for part in _relative(relative, code).split("/"):
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
            raise FastInterchangeError(code)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise FastInterchangeError(code) from exc
    if root != resolved and root not in resolved.parents:
        raise FastInterchangeError(code)
    return resolved


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    sha256: str
    bytes: int

    @classmethod
    def from_dict(cls, value: Any) -> ArtifactFile:
        if not isinstance(value, dict) or set(value) != {"path", "sha256", "bytes"}:
            raise FastInterchangeError("fast_interchange_artifact_file_invalid")
        size = value.get("bytes")
        if type(size) is not int or not 1 <= size <= 8 * 1024**3:
            raise FastInterchangeError("fast_interchange_artifact_file_size_invalid")
        return cls(
            path=_relative(value.get("path"), "fast_interchange_artifact_path_invalid"),
            sha256=_sha(value.get("sha256"), "fast_interchange_artifact_hash_invalid"),
            bytes=size,
        )

    def verify(self, root: Path) -> None:
        path = _inside(root, self.path, "fast_interchange_artifact_unavailable")
        if not path.is_file() or path.is_symlink() or path.stat().st_size != self.bytes:
            raise FastInterchangeError("fast_interchange_artifact_mismatch")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(), self.sha256):
            raise FastInterchangeError("fast_interchange_artifact_mismatch")


@dataclass(frozen=True)
class ArtifactInventory:
    files: tuple[ArtifactFile, ...]

    @classmethod
    def from_dict(cls, value: Any) -> ArtifactInventory:
        if (
            not isinstance(value, dict)
            or set(value) != {"files"}
            or not isinstance(value["files"], list)
        ):
            raise FastInterchangeError("fast_interchange_inventory_invalid")
        files = tuple(
            sorted(
                (ArtifactFile.from_dict(item) for item in value["files"]),
                key=lambda item: item.path,
            )
        )
        if not 1 <= len(files) <= 128 or len({item.path.casefold() for item in files}) != len(
            files
        ):
            raise FastInterchangeError("fast_interchange_inventory_files_invalid")
        return cls(files=files)

    @property
    def digest(self) -> str:
        return _digest({"files": [item.__dict__ for item in self.files]})

    def verify(self, root: Path) -> None:
        for artifact in self.files:
            artifact.verify(root)


@dataclass(frozen=True)
class ArtifactBinding:
    release_id: str
    release_fingerprint: str
    base_dir: str
    adapter_dir: str
    base_inventory: ArtifactInventory
    tokenizer_inventory: ArtifactInventory
    adapter_inventory: ArtifactInventory
    adapter_config: ArtifactFile

    @classmethod
    def from_dict(cls, value: Any) -> ArtifactBinding:
        if not isinstance(value, dict) or set(value) != {
            "release_id",
            "release_fingerprint",
            "base_dir",
            "adapter_dir",
            "base_inventory",
            "tokenizer_inventory",
            "adapter_inventory",
            "adapter_config",
        }:
            raise FastInterchangeError("fast_interchange_binding_invalid")
        return cls(
            release_id=_id(value["release_id"], "fast_interchange_release_id_invalid"),
            release_fingerprint=_sha(
                value["release_fingerprint"], "fast_interchange_release_fingerprint_invalid"
            ),
            base_dir=_relative(value["base_dir"], "fast_interchange_base_dir_invalid"),
            adapter_dir=_relative(value["adapter_dir"], "fast_interchange_adapter_dir_invalid"),
            base_inventory=ArtifactInventory.from_dict(value["base_inventory"]),
            tokenizer_inventory=ArtifactInventory.from_dict(value["tokenizer_inventory"]),
            adapter_inventory=ArtifactInventory.from_dict(value["adapter_inventory"]),
            adapter_config=ArtifactFile.from_dict(value["adapter_config"]),
        )

    def verify(self, root: Path) -> None:
        _inside(root, self.base_dir, "fast_interchange_base_unavailable")
        _inside(root, self.adapter_dir, "fast_interchange_adapter_unavailable")
        self.base_inventory.verify(root)
        self.tokenizer_inventory.verify(root)
        self.adapter_inventory.verify(root)
        self.adapter_config.verify(root)
        self.verify_layout(root)

    def verify_layout(self, root: Path) -> None:
        for directory, inventory in (
            (self.base_dir, (*self.base_inventory.files, *self.tokenizer_inventory.files)),
            (self.adapter_dir, (*self.adapter_inventory.files, self.adapter_config)),
        ):
            expected: dict[str, ArtifactFile] = {}
            for artifact in inventory:
                if not artifact.path.startswith(directory + "/"):
                    raise FastInterchangeError("fast_interchange_inventory_scope_invalid")
                key = artifact.path.casefold()
                if key in expected and artifact != expected[key]:
                    raise FastInterchangeError("fast_interchange_inventory_conflict")
                expected[key] = artifact
            actual: set[str] = set()
            for current, dirs, names in os.walk(
                _inside(root, directory, "fast_interchange_artifact_unavailable"), followlinks=False
            ):
                for name in [*dirs, *names]:
                    item = Path(current) / name
                    if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
                        raise FastInterchangeError("fast_interchange_artifact_link_forbidden")
                for name in names:
                    item = Path(current) / name
                    relative = item.relative_to(root).as_posix()
                    if relative.casefold() in actual:
                        raise FastInterchangeError("fast_interchange_inventory_conflict")
                    actual.add(relative.casefold())
            if actual != set(expected):
                raise FastInterchangeError("fast_interchange_unlisted_loader_file")


@dataclass(frozen=True)
class FastInterchangeRelease:
    release_id: str
    model_id: str
    capability: str
    admission: str
    release_fingerprint: str
    base_inventory_sha256: str
    tokenizer_inventory_sha256: str
    adapter_inventory_sha256: str
    adapter_config_sha256: str
    runtime_abi: str
    prompt_template_sha256: str
    review_required: bool
    promotion_authority: bool

    @classmethod
    def from_dict(cls, value: Any) -> FastInterchangeRelease:
        required = {
            "release_id",
            "model_id",
            "capability",
            "admission",
            "release_fingerprint",
            "base_inventory_sha256",
            "tokenizer_inventory_sha256",
            "adapter_inventory_sha256",
            "adapter_config_sha256",
            "runtime_abi",
            "prompt_template_sha256",
            "review_required",
            "promotion_authority",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise FastInterchangeError("fast_interchange_release_invalid")
        capability = str(value["capability"] or "")
        if (
            capability not in FAST_INTERCHANGE_CAPABILITIES
            or value["review_required"] is not True
            or value["promotion_authority"] is not False
        ):
            raise FastInterchangeError("fast_interchange_release_policy_invalid")
        runtime_abi = str(value["runtime_abi"] or "")
        if runtime_abi != "fast_interchange_hotswap_v1":
            raise FastInterchangeError("fast_interchange_runtime_abi_invalid")
        return cls(
            release_id=_id(value["release_id"], "fast_interchange_release_id_invalid"),
            model_id=_id(value["model_id"], "fast_interchange_model_id_invalid"),
            capability=capability,
            admission=str(value["admission"] or ""),
            release_fingerprint=_sha(
                value["release_fingerprint"], "fast_interchange_release_fingerprint_invalid"
            ),
            base_inventory_sha256=_sha(
                value["base_inventory_sha256"], "fast_interchange_release_hash_invalid"
            ),
            tokenizer_inventory_sha256=_sha(
                value["tokenizer_inventory_sha256"], "fast_interchange_release_hash_invalid"
            ),
            adapter_inventory_sha256=_sha(
                value["adapter_inventory_sha256"], "fast_interchange_release_hash_invalid"
            ),
            adapter_config_sha256=_sha(
                value["adapter_config_sha256"], "fast_interchange_release_hash_invalid"
            ),
            runtime_abi=runtime_abi,
            prompt_template_sha256=_sha(
                value["prompt_template_sha256"], "fast_interchange_release_hash_invalid"
            ),
            review_required=True,
            promotion_authority=False,
        )

    def public(self) -> dict[str, Any]:
        return {
            "id": self.model_id,
            "release_id": self.release_id,
            "capability": self.capability,
            "admission": self.admission,
            "release_fingerprint": self.release_fingerprint,
            "review_required": True,
            "promotion_authority": False,
        }


@dataclass(frozen=True)
class HotSwapRegistry:
    root: Path
    releases: dict[str, FastInterchangeRelease]
    bindings: dict[str, ArtifactBinding]
    admission_authority: AdmissionAuthority | None = field(default=None, repr=False)
    signed_catalog: dict[str, Any] | None = field(default=None, repr=False)
    release_document: dict[str, Any] = field(default_factory=dict, repr=False)
    artifact_document: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dicts(cls, *, root: str | Path, releases: Any, artifacts: Any) -> HotSwapRegistry:
        original_root = Path(root)
        root_path = original_root.resolve()
        if (
            not root_path.is_dir()
            or original_root.is_symlink()
            or getattr(original_root, "is_junction", lambda: False)()
        ):
            raise FastInterchangeError("fast_interchange_artifact_root_invalid")
        if (
            not isinstance(releases, dict)
            or set(releases) != {"schema", "releases"}
            or releases.get("schema") != "fast_interchange_releases_v1"
            or not isinstance(releases.get("releases"), list)
        ):
            raise FastInterchangeError("fast_interchange_release_registry_invalid")
        if (
            not isinstance(artifacts, dict)
            or set(artifacts) != {"schema", "bindings"}
            or artifacts.get("schema") != "fast_interchange_artifacts_v1"
            or not isinstance(artifacts.get("bindings"), list)
        ):
            raise FastInterchangeError("fast_interchange_artifact_registry_invalid")
        release_rows = [FastInterchangeRelease.from_dict(item) for item in releases["releases"]]
        binding_rows = [ArtifactBinding.from_dict(item) for item in artifacts["bindings"]]
        release_map = {item.release_id: item for item in release_rows}
        binding_map = {item.release_id: item for item in binding_rows}
        if (
            not release_map
            or len(release_map) != len(release_rows)
            or set(release_map) != set(binding_map)
            or len(binding_map) != len(binding_rows)
            or len({item.model_id for item in release_rows}) != len(release_rows)
            or len(release_rows) > 64
        ):
            raise FastInterchangeError("fast_interchange_registry_identity_invalid")
        base_digests = {
            (item.base_dir, item.base_inventory.digest, item.tokenizer_inventory.digest)
            for item in binding_rows
        }
        if len(base_digests) != 1:
            raise FastInterchangeError("fast_interchange_shared_base_invalid")
        if len({(item.runtime_abi, item.prompt_template_sha256) for item in release_rows}) != 1:
            raise FastInterchangeError("fast_interchange_shared_template_invalid")
        for release_id, release in release_map.items():
            binding = binding_map[release_id]
            if binding.release_fingerprint != release.release_fingerprint or (
                binding.base_inventory.digest != release.base_inventory_sha256
                or binding.tokenizer_inventory.digest != release.tokenizer_inventory_sha256
                or binding.adapter_inventory.digest != release.adapter_inventory_sha256
                or binding.adapter_config.sha256 != release.adapter_config_sha256
            ):
                raise FastInterchangeError("fast_interchange_release_binding_mismatch")
        return cls(
            root=root_path,
            releases=release_map,
            bindings=binding_map,
            release_document=deepcopy(releases),
            artifact_document=deepcopy(artifacts),
        )

    @classmethod
    def load(
        cls,
        *,
        root: str | Path,
        release_registry: str | Path,
        artifact_registry: str | Path,
        admission_catalog: str | Path | None = None,
        admission_authority: AdmissionAuthority | None = None,
    ) -> HotSwapRegistry:
        try:
            releases = strict_json_load_path(
                release_registry, max_bytes=2 * 1024**2, require_object=True
            )
            artifacts = strict_json_load_path(
                artifact_registry, max_bytes=2 * 1024**2, require_object=True
            )
        except (OSError, ValueError) as exc:
            raise FastInterchangeError("fast_interchange_registry_unavailable") from exc
        registry = cls.from_dicts(root=root, releases=releases, artifacts=artifacts)
        if admission_catalog is not None and admission_authority is not None:
            try:
                catalog = strict_json_load_path(
                    admission_catalog, max_bytes=2 * 1024**2, require_object=True
                )
                admission_authority.verify(catalog, releases=releases, artifacts=artifacts)
                registry = replace(
                    registry, admission_authority=admission_authority, signed_catalog=catalog
                )
            except (ValueError, OSError) as exc:
                raise FastInterchangeError("fast_interchange_admission_invalid") from exc
        return registry

    def admission(self, release: FastInterchangeRelease) -> AdmissionGrant:
        if not self.admission_authority or not self.signed_catalog:
            raise FastInterchangeError("fast_interchange_signed_admission_required")
        try:
            _, grants = self.admission_authority.verify(
                self.signed_catalog,
                releases=self.release_document,
                artifacts=self.artifact_document,
            )
            grant = grants.get(release.release_id)
            original = next(
                (
                    row
                    for row in self.release_document["releases"]
                    if row["release_id"] == release.release_id
                ),
                None,
            )
            original_binding = next(
                (
                    row
                    for row in self.artifact_document["bindings"]
                    if row["release_id"] == release.release_id
                ),
                None,
            )
            if (
                not grant
                or original is None
                or FastInterchangeRelease.from_dict(original) != release
                or original_binding is None
                or ArtifactBinding.from_dict(original_binding)
                != self.bindings.get(release.release_id)
                or grant.model_id != release.model_id
                or grant.capability != release.capability
                or grant.release_fingerprint != release.release_fingerprint
                or grant.compatibility.prompt_template_sha256 != release.prompt_template_sha256
                or (release.admission == "admitted_for_production" and grant.scope != "production")
            ):
                raise FastInterchangeError("fast_interchange_admission_release_mismatch")
            return grant
        except AdmissionError as exc:
            raise FastInterchangeError(str(exc)) from exc

    def select(self, model_id: str, *, allow_test_only: bool) -> FastInterchangeRelease:
        model = _id(model_id, "fast_interchange_model_id_invalid")
        for release in self.releases.values():
            if release.model_id == model:
                if allow_test_only and release.admission == "test_only":
                    return release
                if release.admission in _ADMITTED:
                    self.admission(release)
                    return release
                raise FastInterchangeError("fast_interchange_release_not_admitted")
        raise FastInterchangeError("fast_interchange_model_not_registered")


class AdapterBackend(Protocol):
    def activate(
        self, *, root: Path, binding: ArtifactBinding, release: FastInterchangeRelease
    ) -> dict[str, str]: ...
    def complete(
        self, *, release: FastInterchangeRelease, messages: list[dict[str, str]]
    ) -> dict[str, Any]: ...
    def clear_context(self) -> None: ...
    def close(self) -> None: ...


class HotSwapManager:
    """One serialized worker, one resident base, and no cross-request cache."""

    def __init__(
        self, *, registry: HotSwapRegistry, backend: AdapterBackend, allow_test_only: bool = False
    ):
        self.registry = registry
        self.backend = backend
        self._lock = RLock()
        self._state_lock = RLock()
        self.allow_test_only = allow_test_only
        self._jobs: dict[str, dict[str, Any]] = {}
        self._snapshot: VerifiedSnapshot | None = None
        self._state = "cold"
        self._active_release_id = ""
        self._verified_releases: set[str] = set()
        self._requests = 0
        self._switches = 0
        self._quarantined = False
        self._last_error = ""

    def _quarantine(self, code: str) -> None:
        self._quarantined = True
        self._last_error = code
        self._state = "quarantined"
        try:
            self.backend.clear_context()
        except Exception:
            pass

    def prepare(self, release: FastInterchangeRelease, request_id: str) -> dict[str, Any]:
        if self.registry.select(release.model_id, allow_test_only=self.allow_test_only) != release:
            raise FastInterchangeError("fast_interchange_release_binding_mismatch")
        if not re.fullmatch(r"[a-f0-9]{32}", request_id):
            raise FastInterchangeError("fast_interchange_request_id_invalid")
        with self._state_lock:
            if self._quarantined:
                raise FastInterchangeError("fast_interchange_worker_quarantined")
            instant = time.monotonic()
            self._jobs = {
                key: row
                for key, row in self._jobs.items()
                if row["state"] in {"running", "canceling"} or row["expires"] > instant
            }
            if request_id in self._jobs:
                raise FastInterchangeError("fast_interchange_request_replayed")
            if (
                len(self._jobs) >= 128
                or sum(
                    row["state"] in {"reserved", "running", "canceling"}
                    for row in self._jobs.values()
                )
                >= 4
            ):
                raise FastInterchangeError("fast_interchange_worker_busy")
            self._jobs[request_id] = {
                "state": "reserved",
                "expires": instant + 300,
                "release_id": release.release_id,
                "cancel": Event(),
            }
            return {"request_id": request_id, "status": "reserved"}

    def cancel(self, request_id: str) -> dict[str, Any]:
        with self._state_lock:
            job = self._jobs.get(request_id)
            if job is None:
                raise FastInterchangeError("fast_interchange_request_not_found")
            if job["state"] in {"reserved", "running", "canceling"}:
                job["cancel"].set()
                job["state"] = "canceled" if job["state"] == "reserved" else "canceling"
            return {"request_id": request_id, "status": job["state"], "review_required": True}

    def complete(
        self,
        *,
        release: FastInterchangeRelease,
        messages: list[dict[str, str]],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if request_id is None:
            request_id = uuid.uuid4().hex
            self.prepare(release, request_id)
        if not self._lock.acquire(blocking=False):
            with self._state_lock:
                if request_id in self._jobs:
                    self._jobs[request_id]["state"] = "rejected_busy"
            raise FastInterchangeError("fast_interchange_worker_busy")
        try:
            if self._quarantined:
                raise FastInterchangeError("fast_interchange_worker_quarantined")
            with self._state_lock:
                job = self._jobs.get(request_id)
                if (
                    not job
                    or job["release_id"] != release.release_id
                    or job["expires"] <= time.monotonic()
                ):
                    raise FastInterchangeError("fast_interchange_request_not_found")
                if job["cancel"].is_set():
                    raise FastInterchangeError("fast_interchange_generation_canceled")
                if job["state"] != "reserved":
                    raise FastInterchangeError("fast_interchange_request_replayed")
                job["state"] = "running"
                self._state = "running"
            binding = self.registry.bindings.get(release.release_id)
            if binding is None:
                self._quarantine("fast_interchange_release_binding_missing")
                raise FastInterchangeError("fast_interchange_release_binding_missing")
            try:
                authorized = self.registry.select(
                    release.model_id, allow_test_only=self.allow_test_only
                )
                if authorized != release:
                    raise FastInterchangeError("fast_interchange_release_binding_mismatch")
                grant = (
                    self.registry.admission(release) if release.admission != "test_only" else None
                )
                if grant is not None:
                    configure = getattr(self.backend, "configure", None)
                    if not callable(configure):
                        raise FastInterchangeError("fast_interchange_backend_policy_required")
                    configure(grant.compatibility)
                if self._snapshot is None:
                    self._snapshot = VerifiedSnapshot()
                deadline = time.monotonic() + 120

                def check_snapshot_cancel():
                    if job["cancel"].is_set():
                        raise FastInterchangeError("fast_interchange_generation_canceled")
                    if time.monotonic() > deadline:
                        raise FastInterchangeError("fast_interchange_generation_timeout")

                if release.release_id not in self._verified_releases:
                    self._snapshot.prepare(
                        self.registry.root,
                        binding,
                        strict_models=grant is not None,
                        maximum_bytes=grant.compatibility.max_resident_bytes
                        if grant
                        else 16 * 1024**3,
                        check_cancellation=check_snapshot_cancel,
                    )
                    self._verified_releases.add(release.release_id)
                cancel_setter = getattr(self.backend, "set_cancellation", None)
                if callable(cancel_setter):
                    cancel_setter(job["cancel"], deadline)
                self.backend.clear_context()
                if self._active_release_id != release.release_id:
                    identity = dict(
                        self.backend.activate(
                            root=self._snapshot.root, binding=binding, release=release
                        )
                        or {}
                    )
                    expected = {
                        "release_id": release.release_id,
                        "model_id": release.model_id,
                        "release_fingerprint": release.release_fingerprint,
                    }
                    if any(
                        str(identity.get(key) or "") != value for key, value in expected.items()
                    ):
                        raise FastInterchangeError("fast_interchange_runtime_identity_mismatch")
                    self._active_release_id = release.release_id
                    self._switches += 1
                    self.backend.clear_context()
                if job["cancel"].is_set():
                    raise FastInterchangeError("fast_interchange_generation_canceled")
                response = dict(self.backend.complete(release=release, messages=messages) or {})
                self.backend.clear_context()
                if job["cancel"].is_set():
                    raise FastInterchangeError("fast_interchange_generation_canceled")
                self.registry.select(release.model_id, allow_test_only=self.allow_test_only)
                if str(response.get("model") or "") != release.model_id:
                    raise FastInterchangeError("fast_interchange_runtime_identity_mismatch")
                choices = response.get("choices")
                if not isinstance(choices, list) or len(choices) != 1:
                    raise FastInterchangeError("fast_interchange_completion_invalid")
                choice = choices[0]
                if (
                    not isinstance(choice, dict)
                    or set(choice) != {"message", "finish_reason"}
                    or choice.get("finish_reason") != "stop"
                ):
                    raise FastInterchangeError("fast_interchange_completion_invalid")
                message = choice.get("message")
                if (
                    not isinstance(message, dict)
                    or set(message) != {"role", "content"}
                    or message.get("role") != "assistant"
                    or not isinstance(message.get("content"), str)
                    or not message["content"].strip()
                    or len(message["content"]) > _MAX_COMPLETION_CHARS
                ):
                    raise FastInterchangeError("fast_interchange_completion_invalid")
                self._requests += 1
                job["state"] = "completed"
                self._state = "ready"
                # Return only the fixed text contract, never backend extras.
                return {"model": release.model_id, "choices": [choice]}
            except FastInterchangeError as exc:
                if exc.code == "fast_interchange_generation_canceled":
                    job["state"] = "canceled"
                    self._state = "canceled"
                    self._active_release_id = ""
                    # An interrupted copy must not leave a partial snapshot
                    # masquerading as a loadable or resumable artifact.
                    if (
                        self._snapshot is not None
                        and release.release_id not in self._verified_releases
                    ):
                        self.backend.close()
                        self._snapshot.close()
                        self._snapshot = None
                        self._verified_releases.clear()
                else:
                    job["state"] = "failed"
                    self._quarantine(exc.code)
                raise
            except SnapshotError as exc:
                job["state"] = "failed"
                self._quarantine(str(exc))
                raise FastInterchangeError(str(exc)) from exc
            except Exception as exc:
                job["state"] = "failed"
                self._quarantine("fast_interchange_worker_failed")
                raise FastInterchangeError("fast_interchange_worker_failed") from exc
            finally:
                try:
                    self.backend.clear_context()
                except Exception as exc:
                    job["state"] = "failed"
                    self._quarantine("fast_interchange_context_clear_failed")
                    raise FastInterchangeError("fast_interchange_context_clear_failed") from exc
        finally:
            self._lock.release()

    def status(self) -> dict[str, Any]:
        return {
            "status": "quarantined" if self._quarantined else self._state,
            "active_release_id": self._active_release_id,
            "requests": self._requests,
            "switches": self._switches,
            "shared_matter_cache": False,
            "streaming": False,
            "remote_downloads": False,
            "cancellation_supported": True,
            "maximum_reserved_requests": 4,
            "private_snapshot": self._snapshot is not None,
            "quarantined": self._quarantined,
            "last_error": self._last_error,
        }

    def close(self) -> None:
        with self._lock:
            try:
                try:
                    self.backend.clear_context()
                finally:
                    self.backend.close()
            finally:
                if self._snapshot is not None:
                    self._snapshot.close()
                self._quarantine("fast_interchange_worker_closed")


class TransformersPeftAdapterBackend:
    """Optional local-files-only backend; imports ML packages only on use."""

    def __init__(
        self, *, allow_cpu: bool = False, cuda_device: int = 0,
        force_cpu: bool = False, cpu_threads: int | None = None,
    ):
        if cpu_threads is not None and (type(cpu_threads) is not int or not 1 <= cpu_threads <= 4):
            raise FastInterchangeError("fast_interchange_cpu_thread_limit_invalid")
        if force_cpu and not allow_cpu:
            raise FastInterchangeError("fast_interchange_cpu_mode_not_authorized")
        self.allow_cpu = bool(allow_cpu)
        self.force_cpu = bool(force_cpu)
        self.cpu_threads = min(cpu_threads or 4, max(1, (os.cpu_count() or 1) - 1))
        self.cuda_device = int(cuda_device)
        self._torch: Any = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._loaded_adapters: set[str] = set()
        self._cancellation = None
        self._deadline = 0.0
        self._compatibility = None

    def configure(self, compatibility) -> None:
        from importlib.metadata import PackageNotFoundError, version

        from .admission import Compatibility

        if not isinstance(compatibility, Compatibility):
            raise FastInterchangeError("fast_interchange_runtime_policy_invalid")
        try:
            for library in ("torch", "transformers", "peft", "safetensors"):
                if version(library) != getattr(compatibility, library + "_version"):
                    raise FastInterchangeError("fast_interchange_runtime_version_mismatch")
        except PackageNotFoundError as exc:
            raise FastInterchangeError("fast_interchange_optional_runtime_missing") from exc
        # v1 uses this fixed framing, never a downloaded executable template.
        expected_template = hashlib.sha256(
            b"fi-fixed-role-v1:[ROLE]\\nCONTENT;join=\\n"
        ).hexdigest()
        if compatibility.prompt_template_sha256 != expected_template:
            raise FastInterchangeError("fast_interchange_prompt_template_mismatch")
        if self._compatibility is not None and compatibility != self._compatibility:
            raise FastInterchangeError("fast_interchange_shared_runtime_policy_mismatch")
        self._compatibility = compatibility

    def set_cancellation(self, event: Event, deadline: float) -> None:
        self._cancellation = event
        self._deadline = deadline

    def _check_cancel(self) -> None:
        if self._cancellation is not None and self._cancellation.is_set():
            raise FastInterchangeError("fast_interchange_generation_canceled")
        if self._deadline and time.monotonic() > self._deadline:
            raise FastInterchangeError("fast_interchange_generation_timeout")

    def _imports(self) -> tuple[Any, Any, Any]:
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise FastInterchangeError("fast_interchange_optional_runtime_missing") from exc
        if not torch.cuda.is_available() and not self.allow_cpu:
            raise FastInterchangeError("fast_interchange_cpu_mode_not_authorized")
        return torch, PeftModel, (AutoModelForCausalLM, AutoTokenizer)

    def activate(
        self, *, root: Path, binding: ArtifactBinding, release: FastInterchangeRelease
    ) -> dict[str, str]:
        self._check_cancel()
        torch, PeftModel, transformers = self._imports()
        if self._compatibility is None:
            raise FastInterchangeError("fast_interchange_runtime_policy_required")
        use_cuda = torch.cuda.is_available() and not self.force_cpu
        if not use_cuda and self._compatibility.quantization != "fp32":
            raise FastInterchangeError("fast_interchange_cpu_dtype_not_supported")
        AutoModelForCausalLM, AutoTokenizer = transformers
        base_dir = _inside(root, binding.base_dir, "fast_interchange_base_unavailable")
        adapter_dir = _inside(root, binding.adapter_dir, "fast_interchange_adapter_unavailable")
        if self._model is None:
            device = f"cuda:{self.cuda_device}" if use_cuda else "cpu"
            if not use_cuda:
                # The production backend runs in an owned process, not the UI.
                # Leave CPU capacity for interaction instead of oversubscribing.
                torch.set_num_threads(self.cpu_threads)
            self._tokenizer = AutoTokenizer.from_pretrained(
                str(base_dir), local_files_only=True, trust_remote_code=False
            )
            base = AutoModelForCausalLM.from_pretrained(
                str(base_dir),
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
                torch_dtype=getattr(
                    torch,
                    {"fp32": "float32", "fp16": "float16", "bf16": "bfloat16"}[
                        self._compatibility.quantization
                    ],
                ),
            )
            self._model = PeftModel.from_pretrained(
                base, str(adapter_dir), adapter_name=release.release_id, is_trainable=False
            )
            self._model.to(device)
            self._loaded_adapters.add(release.release_id)
        elif release.release_id not in self._loaded_adapters:
            self._model.load_adapter(
                str(adapter_dir), adapter_name=release.release_id, is_trainable=False
            )
            self._loaded_adapters.add(release.release_id)
        self._model.set_adapter(release.release_id)
        for previous in tuple(self._loaded_adapters - {release.release_id}):
            self._model.delete_adapter(previous)
            self._loaded_adapters.remove(previous)
        self._model.eval()
        self._torch = torch
        self._check_cancel()
        return {
            "release_id": release.release_id,
            "model_id": release.model_id,
            "release_fingerprint": release.release_fingerprint,
        }

    def complete(
        self, *, release: FastInterchangeRelease, messages: list[dict[str, str]]
    ) -> dict[str, Any]:
        if self._model is None or self._tokenizer is None or self._torch is None:
            raise FastInterchangeError("fast_interchange_backend_not_active")
        self._check_cancel()
        # Keep the actual serialized prompt aligned with the immutable prompt
        # template fingerprint verified during admission.  A compatibility hash
        # is meaningless if inference uses a different wire format than the
        # format an adapter was trained and evaluated against.
        prompt = "\\n".join(
            _FIXED_ROLE_PROMPT_TEMPLATE.format(
                role=item["role"].upper(), content=item["content"]
            )
            for item in messages
        )
        # Exact-context approval is invalid if tokenization silently drops text.
        encoded = self._tokenizer(prompt, return_tensors="pt", truncation=False)
        input_shape = getattr(encoded.get("input_ids"), "shape", ())
        if len(input_shape) != 2 or input_shape[0] != 1 or input_shape[1] < 1:
            # A malformed/incompatible tokenizer must never reach generation
            # with no approved context, even if the model supplies a BOS token.
            raise FastInterchangeError("fast_interchange_tokenization_invalid")
        prompt_tokens = input_shape[1]
        context_limit = (
            self._compatibility.max_context_tokens if self._compatibility else _MAX_PROMPT_TOKENS
        )
        output_limit = (
            self._compatibility.max_new_tokens if self._compatibility else _MAX_COMPLETION_TOKENS
        )
        model_limit = getattr(getattr(self._model, "config", None), "max_position_embeddings", None)
        if prompt_tokens > context_limit or (
            type(model_limit) is int and prompt_tokens + output_limit > model_limit
        ):
            raise FastInterchangeError("fast_interchange_context_limit_exceeded")
        device = next(self._model.parameters()).device
        encoded = {key: value.to(device) for key, value in encoded.items()}
        generation_options = {}
        if self._cancellation is not None:
            from transformers import StoppingCriteria, StoppingCriteriaList

            backend = self

            class CancelOrDeadline(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    backend._check_cancel()
                    return False

            generation_options["stopping_criteria"] = StoppingCriteriaList([CancelOrDeadline()])
        with self._torch.no_grad():
            output = self._model.generate(
                **encoded,
                **generation_options,
                do_sample=False,
                # A fresh dynamic cache belongs only to this generate call.
                # Recomputing the entire source prompt for every token makes
                # even a small model unusable on CPU. Never accept caller KV
                # state, use a persistent/static cache, or return cache tensors.
                use_cache=True,
                cache_implementation="dynamic",
                return_dict_in_generate=False,
                # Override any advisory sampling fields stored in a public
                # base model's GenerationConfig.  The worker's immutable
                # contract is greedy/deterministic; leaving those inherited
                # values present produces warnings and weakens audit clarity.
                temperature=None,
                top_p=None,
                top_k=None,
                max_new_tokens=output_limit,
            )
        self._check_cancel()
        generated = output[0][prompt_tokens:]
        token_ids = generated.tolist()
        eos = getattr(getattr(self._model, "generation_config", None), "eos_token_id", None)
        eos_ids = [eos] if type(eos) is int else eos
        if (
            not isinstance(eos_ids, (list, tuple))
            or not eos_ids
            or any(type(token) is not int for token in eos_ids)
            or not token_ids
            # A configured forced EOS at the output ceiling must not disguise
            # budget-truncated prose as a naturally completed answer.
            or len(token_ids) >= output_limit
            or token_ids[-1] not in eos_ids
        ):
            # Hitting the output budget (or unknown stopping semantics) is not
            # a completed answer. Do not decode or expose partial prose.
            raise FastInterchangeError("fast_interchange_completion_incomplete")
        text = self._tokenizer.decode(generated, skip_special_tokens=True).strip()
        if not text:
            raise FastInterchangeError("fast_interchange_empty_completion")
        return {
            "model": release.model_id,
            "choices": [
                {"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
            ],
        }

    def clear_context(self) -> None:
        gc.collect()
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    def close(self) -> None:
        self._model = None
        self._tokenizer = None
        self._loaded_adapters.clear()
        self.clear_context()


def _strict_json(raw: bytes) -> Any:
    try:
        return strict_json_loads(raw, max_bytes=_MAX_BODY_BYTES, require_object=True)
    except ValueError as exc:
        raise FastInterchangeError("fast_interchange_request_invalid") from exc


def _payload(value: Any, *, allow_legacy_test: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or (
        set(value) != _REQUEST_KEYS_V2 and not (allow_legacy_test and set(value) == _REQUEST_KEYS)
    ):
        raise FastInterchangeError("fast_interchange_request_contract_invalid")
    model = _id(value.get("model"), "fast_interchange_model_id_invalid")
    if (
        value.get("stream") is not False
        or type(value.get("max_tokens")) is not int
        or value["max_tokens"] != 1024
    ):
        raise FastInterchangeError("fast_interchange_generation_policy_invalid")
    if (
        type(value.get("temperature")) not in {int, float}
        or value["temperature"] != 0
        or type(value.get("top_p")) not in {int, float}
        or value["top_p"] != 1
    ):
        raise FastInterchangeError("fast_interchange_generation_policy_invalid")
    messages = value.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 8:
        raise FastInterchangeError("fast_interchange_messages_invalid")
    safe_messages: list[dict[str, str]] = []
    for item in messages:
        if (
            not isinstance(item, dict)
            or set(item) != {"role", "content"}
            or item.get("role") not in {"system", "user"}
        ):
            raise FastInterchangeError("fast_interchange_messages_invalid")
        content = item.get("content")
        if not isinstance(content, str) or not content or len(content) > 120_000:
            raise FastInterchangeError("fast_interchange_messages_invalid")
        safe_messages.append({"role": item["role"], "content": content})
    return {
        "model": model,
        "messages": safe_messages,
        **{
            key: value[key]
            for key in ("request_id", "capability", "release_fingerprint")
            if key in value
        },
    }


def create_worker_app(
    *,
    manager: HotSwapManager,
    registry: HotSwapRegistry,
    worker_token: str,
    allow_test_only: bool = False,
) -> Any:
    try:
        from fastapi import Depends, FastAPI, Header
        from fastapi.responses import JSONResponse
    except ImportError as exc:
        raise FastInterchangeError("fast_interchange_api_runtime_missing") from exc
    if (
        not isinstance(worker_token, str)
        or not 32 <= len(worker_token) <= 256
        or not worker_token.isascii()
        or any(c.isspace() for c in worker_token)
    ):
        raise FastInterchangeError("fast_interchange_worker_token_invalid")
    if allow_test_only != manager.allow_test_only:
        raise FastInterchangeError("fast_interchange_test_policy_mismatch")

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            await asyncio.to_thread(manager.close)

    app = FastAPI(
        title="FAST INTERCHANGE local worker",
        version="2",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    def protected(response: Any) -> Any:
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.middleware("http")
    async def headers(request: Any, call_next: Any) -> Any:
        client_host = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            loopback = allow_test_only and client_host == "testclient"
        if not loopback or request.headers.get("origin"):
            return protected(
                JSONResponse(
                    status_code=403,
                    content={"error": {"code": "fast_interchange_local_host_required"}},
                )
            )
        for name in ("authorization", "content-length", "content-type"):
            if len(request.headers.getlist(name)) > 1:
                return protected(
                    JSONResponse(
                        status_code=400,
                        content={"error": {"code": "fast_interchange_duplicate_header"}},
                    )
                )
        if request.method == "POST":
            try:
                length = int(request.headers.get("content-length", "1"))
            except ValueError:
                length = 0
            if not 1 <= length <= _MAX_BODY_BYTES:
                return protected(
                    JSONResponse(status_code=413, content={"error": {"code": "request_too_large"}})
                )
        return protected(await call_next(request))

    @app.exception_handler(FastInterchangeError)
    async def fast_interchange_error(_: Any, error: FastInterchangeError) -> Any:
        specific = {
            "fast_interchange_worker_authentication_required": 401,
            "fast_interchange_generation_canceled": 409,
            "fast_interchange_worker_busy": 429,
            "fast_interchange_request_replayed": 409,
            "fast_interchange_request_not_found": 404,
            "fast_interchange_request_too_large": 413,
            "fast_interchange_request_timeout": 408,
        }
        return JSONResponse(
            status_code=specific.get(
                error.code,
                503 if error.code.endswith(("quarantined", "failed", "unavailable")) else 400,
            ),
            content={"error": {"code": error.code}},
        )

    def actor(authorization: str | None = Header(default=None)) -> None:
        if (
            not isinstance(authorization, str)
            or not authorization.startswith("Bearer ")
            or len(authorization) > 300
            or not hmac.compare_digest(
                authorization[7:].encode("utf-8"), worker_token.encode("ascii")
            )
        ):
            raise FastInterchangeError("fast_interchange_worker_authentication_required")

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"network": "loopback_only", **manager.status()}

    @app.get("/v1/models")
    def models(_: None = Depends(actor)) -> dict[str, Any]:
        admitted = []
        for item in registry.releases.values():
            try:
                registry.select(item.model_id, allow_test_only=allow_test_only)
                admitted.append(item.public())
            except FastInterchangeError:
                continue
        return {
            "object": "list",
            "data": admitted,
            "runtime": manager.status(),
        }

    async def read_payload(request: WorkerRequest) -> dict[str, Any]:
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
            raise FastInterchangeError("fast_interchange_request_content_type_invalid")

        async def read() -> bytes:
            body = bytearray()
            async for block in request.stream():
                if len(body) + len(block) > _MAX_BODY_BYTES:
                    raise FastInterchangeError("fast_interchange_request_too_large")
                body.extend(block)
            return bytes(body)

        try:
            return _strict_json(await asyncio.wait_for(read(), timeout=10))
        except TimeoutError as exc:
            raise FastInterchangeError("fast_interchange_request_timeout") from exc

    def selected(payload: dict[str, Any]) -> FastInterchangeRelease:
        release = registry.select(payload["model"], allow_test_only=allow_test_only)
        if "request_id" in payload and (
            not isinstance(payload["request_id"], str)
            or not re.fullmatch(r"[a-f0-9]{32}", payload["request_id"])
            or payload.get("capability") != release.capability
            or payload.get("release_fingerprint") != release.release_fingerprint
        ):
            raise FastInterchangeError("fast_interchange_request_release_mismatch")
        return release

    @app.post("/v1/requests/prepare")
    async def prepare_request(request: WorkerRequest, _: None = Depends(actor)) -> dict[str, Any]:
        payload = await read_payload(request)
        if set(payload) != {"model", "request_id", "capability", "release_fingerprint"}:
            raise FastInterchangeError("fast_interchange_request_contract_invalid")
        return manager.prepare(selected(payload), payload["request_id"])

    @app.post("/v1/requests/cancel")
    async def cancel_request(request: WorkerRequest, _: None = Depends(actor)) -> dict[str, Any]:
        payload = await read_payload(request)
        if set(payload) != {"request_id"} or not isinstance(payload["request_id"], str):
            raise FastInterchangeError("fast_interchange_request_contract_invalid")
        return manager.cancel(payload["request_id"])

    @app.post("/v1/chat/completions")
    async def completion(request: WorkerRequest, _: None = Depends(actor)) -> dict[str, Any]:
        payload = _payload(await read_payload(request), allow_legacy_test=allow_test_only)
        release = selected(payload)
        result = await asyncio.to_thread(
            manager.complete,
            release=release,
            messages=payload["messages"],
            request_id=payload.get("request_id"),
        )
        return {
            **result,
            "release_fingerprint": release.release_fingerprint,
            "capability": release.capability,
            "request_id": payload.get("request_id"),
            "review_required": True,
        }

    return app


def _required_env(name: str, minimum_bytes: int = 1) -> str:
    value = os.environ.get(name, "")
    if len(value.encode("utf-8")) < minimum_bytes:
        raise FastInterchangeError("fast_interchange_environment_missing")
    return value


def main() -> int:
    try:
        import uvicorn
    except ImportError as exc:
        raise FastInterchangeError("fast_interchange_api_runtime_missing") from exc
    host = os.environ.get("MFL_FAST_INTERCHANGE_HOST", "127.0.0.1")
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ValueError
        port = int(os.environ.get("MFL_FAST_INTERCHANGE_PORT", "8105"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as exc:
        raise FastInterchangeError("fast_interchange_loopback_binding_required") from exc
    from .host import load_operator_registry
    from .process_backend import IsolatedAdapterBackend

    registry = load_operator_registry()
    if any(item.admission == "test_only" for item in registry.releases.values()):
        raise FastInterchangeError("fast_interchange_test_release_forbidden")
    for release in registry.releases.values():
        registry.select(release.model_id, allow_test_only=False)
    backend = IsolatedAdapterBackend(
        allow_cpu=os.environ.get("MFL_FAST_INTERCHANGE_ALLOW_CPU") == "1"
    )
    app = create_worker_app(
        manager=HotSwapManager(registry=registry, backend=backend),
        registry=registry,
        worker_token=_required_env("MFL_FAST_INTERCHANGE_WORKER_TOKEN", 32),
        allow_test_only=False,
    )
    uvicorn.run(app, host=host, port=port, access_log=False, log_level="warning")
    return 0


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())

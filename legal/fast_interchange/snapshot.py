"""Worker-private verified model snapshots, not mutable installation paths.

On Windows, open read handles deny write/delete sharing until worker shutdown.
Other platforms use private directories/read-only files; protecting against a
compromised OS account or administrator is outside this process boundary.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile
import weakref
from pathlib import Path
from typing import Any

from legal.security.strict_json import strict_json_load_path, strict_json_loads


class SnapshotError(ValueError):
    pass


def validate_model_budget(config: dict, adapter: dict, *, maximum_bytes: int) -> None:
    """Bound config-driven allocations before importing a model architecture.

    This conservative parameter estimate is not measured peak process memory.
    New architectures/quantized formats require a separately reviewed loader.
    """
    if config.get("model_type") not in {"llama", "mistral", "qwen2", "qwen3"}:
        raise SnapshotError("fast_interchange_architecture_not_supported")
    limits = {
        "hidden_size": 4096,
        "intermediate_size": 24576,
        "num_hidden_layers": 64,
        "vocab_size": 262144,
        "num_attention_heads": 64,
    }
    for name, maximum in limits.items():
        value = config.get(name)
        if type(value) is not int or not 1 <= value <= maximum:
            raise SnapshotError("fast_interchange_model_config_budget_invalid")
    hidden, intermediate = config["hidden_size"], config["intermediate_size"]
    if hidden % config["num_attention_heads"]:
        raise SnapshotError("fast_interchange_model_config_budget_invalid")
    estimate = 4 * (
        2 * hidden * config["vocab_size"]
        + config["num_hidden_layers"] * (4 * hidden * hidden + 3 * hidden * intermediate)
    )
    if estimate > maximum_bytes:
        raise SnapshotError("fast_interchange_model_allocation_budget_exceeded")
    if config.get("quantization_config") or config.get("configuration_files"):
        raise SnapshotError("fast_interchange_dynamic_model_config_forbidden")
    if (
        adapter.get("peft_type") != "LORA"
        or adapter.get("task_type") != "CAUSAL_LM"
        or type(adapter.get("r")) is not int
        or not 1 <= adapter["r"] <= 128
        or adapter.get("rank_pattern")
        or adapter.get("modules_to_save")
        or adapter.get("loftq_config")
    ):
        raise SnapshotError("fast_interchange_adapter_config_invalid")


def _lock_read(path: Path):
    if os.name != "nt":
        return path.open("rb")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    create = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    handle = create(str(path), 0x80000000, 1, None, 3, 0x80, None)  # read, share-read only
    if handle == ctypes.c_void_p(-1).value:
        raise SnapshotError("fast_interchange_snapshot_lock_failed")
    return os.fdopen(msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY), "rb")


def validate_safetensors(path: Path, *, maximum_bytes: int) -> None:
    with path.open("rb") as handle:
        length_bytes = handle.read(8)
        if len(length_bytes) != 8:
            raise SnapshotError("fast_interchange_tensor_header_invalid")
        length = struct.unpack("<Q", length_bytes)[0]
        if not 2 <= length <= 4 * 1024**2:
            raise SnapshotError("fast_interchange_tensor_header_invalid")
        header = strict_json_loads(handle.read(length), max_bytes=4 * 1024**2, require_object=True)
    data_bytes = path.stat().st_size - length - 8
    widths = {
        "BOOL": 1,
        "U8": 1,
        "I8": 1,
        "I16": 2,
        "U16": 2,
        "F16": 2,
        "BF16": 2,
        "I32": 4,
        "U32": 4,
        "F32": 4,
        "I64": 8,
        "U64": 8,
        "F64": 8,
    }
    spans = []
    if not 1 <= data_bytes <= maximum_bytes or len(header) > 100_000:
        raise SnapshotError("fast_interchange_tensor_budget_exceeded")
    for name, tensor in header.items():
        if name == "__metadata__":
            if not isinstance(tensor, dict) or any(not isinstance(v, str) for v in tensor.values()):
                raise SnapshotError("fast_interchange_tensor_metadata_invalid")
            continue
        if not isinstance(tensor, dict) or set(tensor) != {"dtype", "shape", "data_offsets"}:
            raise SnapshotError("fast_interchange_tensor_header_invalid")
        width = widths.get(tensor["dtype"])
        shape, offsets = tensor["shape"], tensor["data_offsets"]
        if not width or not isinstance(shape, list) or len(shape) > 8:
            raise SnapshotError("fast_interchange_tensor_shape_invalid")
        size = width
        for dimension in shape:
            if type(dimension) is not int or not 1 <= dimension <= 2**24:
                raise SnapshotError("fast_interchange_tensor_shape_invalid")
            size *= dimension
            if size > maximum_bytes:
                raise SnapshotError("fast_interchange_tensor_budget_exceeded")
        if (
            not isinstance(offsets, list)
            or len(offsets) != 2
            or any(type(x) is not int for x in offsets)
            or not 0 <= offsets[0] < offsets[1] <= data_bytes
            or offsets[1] - offsets[0] != size
        ):
            raise SnapshotError("fast_interchange_tensor_offsets_invalid")
        spans.append(tuple(offsets))
    previous = 0
    for start, end in sorted(spans):
        if start != previous:
            raise SnapshotError("fast_interchange_tensor_coverage_invalid")
        previous = end
    if previous != data_bytes:
        raise SnapshotError("fast_interchange_tensor_coverage_invalid")


def _read_model_json(path: Path) -> dict[str, Any]:
    """Read a declared loader file without rejecting standard large tokenizers.

    Qwen-class tokenizer vocabularies can contain more than 200,000 JSON tree
    values while remaining a bounded, local 64 MiB loader asset.  Keep the
    stricter default for every other model file, but allow no more than two
    million primitive/container values for the one tokenizer format that
    requires it.  Duplicate keys, non-finite values, invalid UTF-8, depth, and
    byte limits remain enforced by ``strict_json_load_path``.
    """

    return strict_json_load_path(
        path,
        max_bytes=64 * 1024**2,
        max_items=2_000_000 if path.name == "tokenizer.json" else 200_000,
        require_object=True,
    )


def _release_snapshot(handles, verified, root, temporary) -> None:
    for handle in handles:
        handle.close()
    handles.clear()
    for relative in verified:
        path = root / relative
        if path.is_file():
            path.chmod(0o600)
    temporary.cleanup()


class VerifiedSnapshot:
    def __init__(self, *, directory: Path | None = None):
        self._temporary = tempfile.TemporaryDirectory(prefix="mfl-fi-model-snapshot-", dir=directory)
        self.root = Path(self._temporary.name).resolve()
        self._verified: dict[str, tuple[str, int]] = {}
        self._handles: list[Any] = []
        # Registered after TemporaryDirectory's finalizer, so OS read locks are
        # released before its cleanup even when a caller exits unexpectedly.
        self._finalizer = weakref.finalize(
            self, _release_snapshot, self._handles, self._verified, self.root, self._temporary
        )

    def prepare(
        self,
        source_root: Path,
        binding: Any,
        *,
        strict_models: bool,
        maximum_bytes: int,
        check_cancellation=None,
    ) -> Path:
        binding.verify_layout(source_root)
        files = {
            item.path: item
            for item in (
                *binding.base_inventory.files,
                *binding.tokenizer_inventory.files,
                *binding.adapter_inventory.files,
                binding.adapter_config,
            )
        }
        remaining = sum(item.bytes for item in files.values() if item.path not in self._verified)
        if remaining > shutil.disk_usage(self.root).free - 64 * 1024**2:
            raise SnapshotError("fast_interchange_snapshot_disk_space")
        for relative, item in files.items():
            if check_cancellation is not None:
                check_cancellation()
            identity = (item.sha256, item.bytes)
            if relative in self._verified:
                if self._verified[relative] != identity:
                    raise SnapshotError("fast_interchange_snapshot_identity_conflict")
                continue
            source = source_root / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            hasher, count = hashlib.sha256(), 0
            with source.open("rb") as reader, target.open("xb") as writer:
                while block := reader.read(1024 * 1024):
                    if check_cancellation is not None:
                        check_cancellation()
                    count += len(block)
                    if count > item.bytes:
                        raise SnapshotError("fast_interchange_snapshot_source_changed")
                    hasher.update(block)
                    writer.write(block)
                writer.flush()
                os.fsync(writer.fileno())
            if count != item.bytes or hasher.hexdigest() != item.sha256:
                raise SnapshotError("fast_interchange_artifact_mismatch")
            target.chmod(0o400)
            self._handles.append(_lock_read(target))
            self._verified[relative] = identity
        binding.verify_layout(self.root)
        if strict_models:
            self._validate_models(binding, maximum_bytes)
        return self.root

    def _validate_models(self, binding: Any, maximum_bytes: int) -> None:
        files = {
            item.path
            for item in (
                *binding.base_inventory.files,
                *binding.tokenizer_inventory.files,
                *binding.adapter_inventory.files,
                binding.adapter_config,
            )
        }
        required = {
            f"{binding.base_dir}/config.json",
            f"{binding.base_dir}/model.safetensors",
            f"{binding.base_dir}/tokenizer.json",
            f"{binding.adapter_dir}/adapter_model.safetensors",
            f"{binding.adapter_dir}/adapter_config.json",
        }
        if not required <= files:
            raise SnapshotError("fast_interchange_required_model_files_missing")
        allowed_base = {
            "config.json",
            "generation_config.json",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "added_tokens.json",
            "vocab.json",
            "merges.txt",
            "README.md",
            "LICENSE",
            "chat_template.jinja",
        }
        allowed_adapter = {
            "adapter_model.safetensors",
            "adapter_config.json",
            "README.md",
            "LICENSE",
        }
        if any(
            relative
            not in {f"{binding.base_dir}/{name}" for name in allowed_base}
            | {f"{binding.adapter_dir}/{name}" for name in allowed_adapter}
            for relative in files
        ):
            raise SnapshotError("fast_interchange_loader_layout_not_supported")
        validate_model_budget(
            strict_json_load_path(
                self.root / binding.base_dir / "config.json", max_bytes=1024**2, require_object=True
            ),
            strict_json_load_path(
                self.root / binding.adapter_dir / "adapter_config.json",
                max_bytes=1024**2,
                require_object=True,
            ),
            maximum_bytes=maximum_bytes,
        )
        for relative in files:
            path = self.root / relative
            if (
                path.suffix.lower() not in {".json", ".safetensors", ".txt", ".md", ".jinja"}
                and path.name != "LICENSE"
            ):
                raise SnapshotError("fast_interchange_model_file_type_forbidden")
            if path.suffix == ".safetensors":
                validate_safetensors(path, maximum_bytes=maximum_bytes)
            if path.suffix == ".json":
                value = _read_model_json(path)
                if (
                    value.get("auto_map")
                    or value.get("auto_mapping")
                    or value.get("trust_remote_code")
                ):
                    raise SnapshotError("fast_interchange_remote_code_forbidden")

    def close(self) -> None:
        self._finalizer()

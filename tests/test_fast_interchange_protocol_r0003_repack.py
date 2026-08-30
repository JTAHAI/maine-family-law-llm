from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repack_fast_interchange_protocol_r0003.py"


def _module():
    specification = importlib.util.spec_from_file_location("mfl_protocol_r0003_repack", SCRIPT)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_protocol_r0003_repack_requires_a_distinct_tag_and_public_output() -> None:
    module = _module()
    assert module.SOURCE_PACK_ID == "mfl-fast-interchange-protocol-r0002"
    assert module.RELEASE_TAG == "protocol-r0003"
    assert module._outside_repository(ROOT.parent / "external-models") == (ROOT.parent / "external-models").resolve()


def test_protocol_r0003_repack_rejects_unsafe_or_malformed_safetensor_headers(tmp_path) -> None:
    module = _module()
    good = tmp_path / "good.safetensors"
    header = b'{"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
    good.write_bytes(struct.pack("<Q", len(header)) + header + b"\0\0\0\0")
    assert module._tensor_header_is_clean(good)

    unsafe = tmp_path / "unsafe.safetensors"
    unsafe_header = b'{"metadata":"D:\\\\private-build"}'
    unsafe.write_bytes(struct.pack("<Q", len(unsafe_header)) + unsafe_header)
    assert not module._tensor_header_is_clean(unsafe)

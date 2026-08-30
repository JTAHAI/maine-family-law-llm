from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_fast_interchange_protocol_r0002.py"


def _module():
    specification = importlib.util.spec_from_file_location("mfl_protocol_r0002_builder", SCRIPT)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_protocol_r0002_rows_are_deterministic_nonlegal_and_eos_trainable() -> None:
    builder = _module()
    rows = builder.protocol_rows("intake_triage", copies=1)
    assert len(rows) == len(builder.SCENARIOS)
    assert not any("verification only" in row["prompt"] for row in rows)
    assert all(row["prompt"].startswith(r"fi-fixed-role-v1:[USER]\n") for row in rows)
    assert all("Maine statute" not in row["prompt"] for row in rows)
    assert all(row["response"] == '{"next":"verify_source","status":"review_required"}' for row in rows)
    assert builder.PROMPT_TEMPLATE_SHA256 == __import__("hashlib").sha256(
        builder.PROMPT_TEMPLATE.encode("utf-8")
    ).hexdigest()
    assert "LICENSE" in builder.BASE_FILES


def test_protocol_r0002_rejects_unknown_capability_and_invalid_copies() -> None:
    builder = _module()
    for capability, copies in (("unknown", 1), ("drafting", 0), ("drafting", 17)):
        try:
            builder.protocol_rows(capability, copies=copies)
        except ValueError:
            pass
        else:  # pragma: no cover - assertion detail
            raise AssertionError("protocol_row_input_should_fail_closed")


def test_protocol_builder_release_tags_are_immutable_and_strict() -> None:
    builder = _module()
    assert builder._release_tag("protocol-r0003") == "protocol-r0003"
    for invalid in ("protocol-r3", "r0003", "protocol-r0002/../r0003", "protocol-r00030"):
        try:
            builder._release_tag(invalid)
        except ValueError as exc:
            assert str(exc) == "release_tag_invalid"
        else:  # pragma: no cover - assertion detail
            raise AssertionError("release_tag_should_fail_closed")


def test_protocol_r0002_cuda_selector_is_process_local_and_rejects_invalid_values(monkeypatch) -> None:
    builder = _module()
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    builder._select_cuda_device(0)
    assert __import__("os").environ["CUDA_VISIBLE_DEVICES"] == "0"

    for invalid in (-1, "0"):
        try:
            builder._select_cuda_device(invalid)
        except ValueError as exc:
            assert str(exc) == "cuda_visible_device_invalid"
        else:  # pragma: no cover - assertion detail
            raise AssertionError("invalid_cuda_selector_should_fail_closed")


def test_protocol_r0002_adapter_metadata_uses_public_base_identity_and_rejects_private_metadata(tmp_path) -> None:
    builder = _module()
    config = tmp_path / "adapter_config.json"
    config.write_text(
        json.dumps(
            {
                "base_model_name_or_path": r"D:\\private-build\\base-model",
                "peft_type": "LORA",
            }
        ),
        encoding="utf-8",
    )

    builder._sanitize_adapter_config(tmp_path)

    stored = json.loads(config.read_text(encoding="utf-8"))
    assert stored["base_model_name_or_path"] == "Qwen/Qwen3-0.6B"
    assert "private-build" not in config.read_text(encoding="utf-8")

    config.write_text(
        json.dumps(
            {
                "base_model_name_or_path": "Qwen/Qwen3-0.6B",
                "note": "Northstar must never appear in a public pack",
            }
        ),
        encoding="utf-8",
    )
    try:
        builder._sanitize_adapter_config(tmp_path)
    except RuntimeError as exc:
        assert str(exc) == "adapter_config_private_metadata"
    else:  # pragma: no cover - assertion detail
        raise AssertionError("private_metadata_should_fail_closed")

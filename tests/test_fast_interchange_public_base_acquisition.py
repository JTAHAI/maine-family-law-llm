from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acquire_fast_interchange_qwen3_base.py"


def _module():
    specification = importlib.util.spec_from_file_location("mfl_public_base_acquisition", SCRIPT)
    assert specification and specification.loader
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_public_base_acquisition_locks_the_expected_public_model_and_complete_inventory() -> None:
    module = _module()
    assert module.MODEL_ID == "Qwen/Qwen3-0.6B"
    assert len(module.MODEL_REVISION) == 40
    assert set(module.REQUIRED_FILES) == {
        "LICENSE",
        "config.json",
        "generation_config.json",
        "merges.txt",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    }


def test_public_base_acquisition_refuses_repository_output(tmp_path) -> None:
    module = _module()
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    with pytest.raises(ValueError, match="base_output_must_be_outside_repository"):
        module._inside_external_root(repository_root / "models", repository_root)


def test_public_base_acquisition_requires_explicit_resume_for_existing_stage(tmp_path) -> None:
    module = _module()
    output = tmp_path / "base"
    stage = tmp_path / "base.building"
    stage.mkdir()
    with pytest.raises(ValueError, match="base_stage_exists"):
        module._stage_for_output(output, resume=False)
    assert module._stage_for_output(output, resume=True) == stage


def test_public_base_acquisition_accepts_mapping_style_model_card_license() -> None:
    module = _module()

    class Card:
        def get(self, key, default=None):
            return "apache-2.0" if key == "license" else default

    class Info:
        cardData = Card()

    assert module._license_from_card(Info()) == "Apache-2.0"

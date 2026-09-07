from pathlib import Path

import pytest

from scripts.validate_bundled_mfl_specialists import (
    tree_identity,
    validate,
    validate_inventory_coverage,
)


def test_validator_script_is_directly_invocable():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/validate_bundled_mfl_specialists.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--pack" in result.stdout


def test_tree_identity_changes_with_any_pack_byte(tmp_path: Path):
    root = tmp_path / "pack"
    root.mkdir()
    artifact = root / "artifact.bin"
    artifact.write_bytes(b"fictional-one")
    before = tree_identity(root)
    artifact.write_bytes(b"fictional-two")
    after = tree_identity(root)
    assert before[0] != after[0]
    assert before[1:] == after[1:]


def test_validator_rejects_private_key_before_admission(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "never.key").write_text("fictional", encoding="utf-8")
    trust = tmp_path / "trust.json"
    trust.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="private_key_forbidden"):
        validate(pack, trust, tmp_path / "state")


def test_validator_rejects_unlisted_root_residue_before_admission(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "training-log.txt").write_text("fictional", encoding="utf-8")
    trust = tmp_path / "trust.json"
    trust.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted_root_file"):
        validate(pack, trust, tmp_path / "state")


def test_validator_rejects_unlisted_root_directory_before_admission(tmp_path: Path):
    pack = tmp_path / "pack"
    (pack / "training-cache").mkdir(parents=True)
    trust = tmp_path / "trust.json"
    trust.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="unlisted_root_directory"):
        validate(pack, trust, tmp_path / "state")


def test_metadata_validation_does_not_claim_measured_cpu_qualification(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from scripts import validate_bundled_mfl_specialists as validator

    pack = tmp_path / "pack"
    pack.mkdir()
    trust = tmp_path / "trust.json"
    trust.write_text("{}", encoding="utf-8")
    releases = {
        name: SimpleNamespace(
            capability=name, admission="admitted_for_production", model_id=name,
            release_id=name, release_fingerprint="a" * 64,
        )
        for name in validator.CAPABILITIES
    }
    grant = SimpleNamespace(
        scope="production",
        evaluation=SimpleNamespace(
            dataset_kind="attorney_reviewed", report_sha256="b" * 64, sample_count=104,
        ),
        licenses=SimpleNamespace(redistribution_permitted=True),
        compatibility=SimpleNamespace(
            quantization="fp32", max_resident_bytes=4 * 1024**3, max_new_tokens=256,
            **{f"{name}_version": "fictional-version" for name in (
                "torch", "transformers", "peft", "safetensors",
            )},
        ),
    )
    registry = SimpleNamespace(
        releases=releases, select=lambda name, **kw: releases[name],
        admission=lambda release: grant,
        bindings={name: SimpleNamespace(
            verify=lambda root: None,
            base_inventory=SimpleNamespace(files=()),
            tokenizer_inventory=SimpleNamespace(files=()),
            adapter_inventory=SimpleNamespace(files=()),
            adapter_config=SimpleNamespace(path="adapters/fictional/adapter_config.json"),
        ) for name in releases},
    )
    monkeypatch.setattr(validator, "AdmissionAuthority", lambda **kw: object())
    monkeypatch.setattr(validator.HotSwapRegistry, "load", lambda **kw: registry)
    monkeypatch.setattr(validator, "version", lambda name: "fictional-version")
    result = validate(pack, trust, tmp_path / "state")
    assert result["cpu_fallback_runtime_compatible"] is True
    assert result["cpu_fallback_qualified"] is False
    assert result["qualification_scope"].endswith("not_measured_inference")


@pytest.mark.parametrize("residue", [
    "adapters/unused/training-records.jsonl", "adapters/hidden-cache.bin",
    "base/unused/extra.bin",
])
def test_signed_inventory_rejects_unreferenced_nested_payload(tmp_path, residue):
    from types import SimpleNamespace

    pack = tmp_path / "pack"
    artifact = pack / residue
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fictional residue")
    with pytest.raises(ValueError, match="unlisted_payload_file"):
        validate_inventory_coverage(pack, SimpleNamespace(releases={}))


def test_inventory_coverage_accepts_only_bound_files_and_public_metadata(tmp_path):
    from types import SimpleNamespace

    from legal.fast_interchange.worker import ArtifactFile

    pack = tmp_path / "pack"
    pack.mkdir()
    artifact = ArtifactFile("adapters/fictional/adapter_config.json", "a" * 64, 2)
    path = pack / artifact.path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{}")
    (pack / "BASE-LICENSE.txt").write_text("Fictional test license", encoding="utf-8")
    binding = SimpleNamespace(
        base_inventory=SimpleNamespace(files=()),
        tokenizer_inventory=SimpleNamespace(files=()),
        adapter_inventory=SimpleNamespace(files=()), adapter_config=artifact,
    )
    registry = SimpleNamespace(
        releases={"fixture": SimpleNamespace(release_id="fixture")},
        bindings={"fixture": binding},
    )
    validate_inventory_coverage(pack, registry)

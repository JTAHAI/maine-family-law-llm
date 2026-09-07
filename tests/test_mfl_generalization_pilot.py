import hashlib
import json

import pytest

from scripts.audit_mfl_generalization_pilot import validate_rows
from scripts.build_mfl_evidence_corrective_corpus import canonical
from scripts.build_mfl_generalization_pilot import development_cases, training_case
from scripts.train_mfl_adapter_continuation import (
    prepare_workspace,
    valid_cuda_selector,
    validate_split_contract,
)


def fixture_rows():
    rows, packets = [], []
    for index in range(512):
        question, sources, quotes, limit, forbidden = training_case(index)
        packet = {
            "case_id": str(index),
            "sources": sources,
            "quotes": quotes,
            "question": question,
            "forbidden_literals": forbidden,
            "split": "train",
        }
        bound = "; ".join(
            f'"{q}" [{next(i for i, s in enumerate(sources, 1) if q in s)}]' for q in quotes
        )
        rows.append(
            {
                "example_id": str(index),
                "split": "train",
                "source_digest": hashlib.sha256(canonical(packet)).hexdigest(),
                "privacy_class": "no_client_data",
                "rights_class": "company_owned",
                "response": bound + limit + " Review required.",
                "task_family": str(index % 8),
                "instruction": json.dumps([{"role": "user", "content": question}]),
            }
        )
        packets.append(packet)
    return rows, packets, {"training_use_permitted": False, "cases": development_cases()}


def test_pilot_has_source_bound_targets_without_development_leakage():
    result = validate_rows(*fixture_rows())
    assert result["rows"] == 512
    assert len(result["families"]) == 8
    assert result["declared_development_overlap"] == 0


@pytest.mark.parametrize(
    "attack", ["private", "binding", "marker", "split", "overlap", "source_digest"]
)
def test_pilot_audit_fails_closed(attack):
    rows, packets, development = fixture_rows()
    if attack == "private":
        rows[6]["response"] += packets[6]["forbidden_literals"][0] + " Review required."
    elif attack == "binding":
        rows[0]["response"] = rows[0]["response"].replace("[1]", "[99]")
    elif attack == "marker":
        rows[0]["response"] = rows[0]["response"].removesuffix("Review required.")
    elif attack == "split":
        rows[0]["split"] = "development"
    elif attack == "source_digest":
        rows[0]["source_digest"] = "0" * 64
    else:
        development["cases"][0]["question"] = packets[0]["question"]
    with pytest.raises(ValueError):
        validate_rows(rows, packets, development)


def test_small_pilot_requires_explicit_isolated_contract():
    counts = {"train": 512}
    manifest = {
        "split_counts": counts,
        "purpose": "bounded_generalization_pilot",
        "development_cases": 8,
        "development_sha256": "a" * 64,
    }
    validate_split_contract(counts, manifest, pilot=True)
    with pytest.raises(ValueError):
        validate_split_contract(counts, manifest, pilot=False)
    with pytest.raises(ValueError):
        validate_split_contract(counts, {**manifest, "development_cases": 0}, pilot=True)
    validate_split_contract({"train": 25600}, {"split_counts": {"train": 25600}}, pilot=False)


def test_trainer_rejects_external_scratch_before_creating_it(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.train_mfl_adapter_continuation.ROOT", tmp_path / "repo")
    with pytest.raises(ValueError, match="repository dist"):
        prepare_workspace(tmp_path / "outside-repo")
    assert not (tmp_path / "outside-repo").exists()


@pytest.mark.parametrize("value", ["0", "31", "GPU-74c52c2b-927c-1904-d5bd-727d249d7ff9"])
def test_gpu_selector_allows_exact_uuid_or_bounded_ordinal(value):
    assert valid_cuda_selector(value)


@pytest.mark.parametrize("value", ["-1", "32", "0,1", "GPU-*", "", "0;anything"])
def test_gpu_selector_rejects_masks_and_invalid_devices(value):
    assert not valid_cuda_selector(value)


def test_research_registry_reuses_base_without_copying_or_admitting(tmp_path, monkeypatch):
    from legal.fast_interchange.worker import FastInterchangeError
    from scripts import evaluate_mfl_adapter_pilot as pilot
    from tests.test_fast_interchange_worker import _registry

    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    root = tmp_path / "dist/model-candidates"
    parent = root / "parent"
    original = _registry(parent)
    releases = original.release_document
    artifacts = original.artifact_document
    releases["releases"] = releases["releases"][:1]
    artifacts["bindings"] = artifacts["bindings"][:1]
    (parent / "releases.json").write_text(json.dumps(releases), encoding="utf-8")
    (parent / "artifacts.json").write_text(json.dumps(artifacts), encoding="utf-8")
    adapter = root / "candidate"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(b"synthetic-not-a-model")
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    registry = pilot.research_registry(parent, adapter, root)
    release = next(iter(registry.releases.values()))
    binding = registry.bindings[release.release_id]
    assert binding.base_dir == "parent/base"
    assert binding.adapter_dir == "candidate"
    assert release.admission == "unadmitted_local_research"
    with pytest.raises(FastInterchangeError, match="signed_admission_required"):
        registry.admission(release)
    assert {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    (adapter / "adapter_model.safetensors").write_bytes(b"tampered")
    with pytest.raises(FastInterchangeError):
        binding.verify(root)

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gpu_validator_is_explicitly_fictional_and_never_release_eligible():
    source = (ROOT / "scripts" / "validate_evidence_research_model.py").read_text(encoding="utf-8")
    assert "fictional_research_opt_in_required" in source
    assert "HF_HUB_OFFLINE" in source
    assert '"raw_model_output_visible": False' in source
    assert '"release_eligible": False' in source
    assert "output_sha256" in source
    assert "max_new_tokens_must_be_between_1_and_256" in source

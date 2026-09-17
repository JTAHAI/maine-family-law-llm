"""Opt-in identical-weight score parity, NOT relevance/abstention acceptance."""

import hashlib
import json
import os

import pytest

from scripts.acquire_compact_model_candidates import OUTPUT, ROOT
from scripts.diagnose_compact_ranker_startup import measured_child
from scripts.prepare_compact_bert_overlay import DIRECTORY, verify
from scripts.verify_compact_reranker import execute


@pytest.mark.skipif(os.environ.get("MFL_RUN_BERT_PARITY") != "1", reason="Opt-in real CPU model")
def test_selected_overlay_preserves_real_full_runtime_scores():
    baseline_path = OUTPUT / "reranker-fixed-bert-full-01.json"
    overlay_path = OUTPUT / "reranker-fixed-bert-overlay-01.json"
    target = OUTPUT / "fixed-bert-score-parity-01.json"
    assert not target.exists(), "Preserve prior evidence"
    baseline = json.loads(baseline_path.read_text())
    for name, digest in baseline["implementation"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    selection = verify()
    reuse = os.environ.get("MFL_REUSE_BERT_PARITY") == "1"
    if not reuse:
        assert not overlay_path.exists(), "Preserve prior evidence"
        with measured_child(OUTPUT / "fixed-bert-parity-trace-01.jsonl", DIRECTORY):
            # Relevance failures are retained, not turned into model-quality passes.
            execute(overlay_path.name, baseline["fixture_name"], isolated=True)
    overlay = json.loads(overlay_path.read_text())
    assert overlay["implementation"] == baseline["implementation"]
    assert not baseline["errors"] and not overlay["errors"]
    assert baseline["clean_shutdown"] and overlay["clean_shutdown"]
    assert baseline["weights_sha256"] == overlay["weights_sha256"]
    assert baseline["fixture_sha256"] == overlay["fixture_sha256"]
    assert len(baseline["cases"]) == len(overlay["cases"]) == 12
    compared, delta = 0, 0.0
    for a, b in zip(baseline["cases"], overlay["cases"], strict=True):
        assert a["id"] == b["id"] and a["selected_passages"] == b["selected_passages"]
        assert len(a["rankings"]) == len(b["rankings"])
        for left, right in zip(a["rankings"], b["rankings"], strict=True):
            assert left["reference"] == right["reference"]
            assert len(left["ranks"]) == len(right["ranks"])
            for x, y in zip(left["ranks"], right["ranks"], strict=True):
                assert x.keys() == y.keys()
                assert {k: v for k, v in x.items() if k != "relevance_score"} == {
                    k: v for k, v in y.items() if k != "relevance_score"
                }
                delta = max(delta, abs(x["relevance_score"] - y["relevance_score"]))
                compared += 1
    assert delta <= 1e-6
    report = {
        "score_parity_passed": True,
        "reused_recorded_model_runs": reuse,
        "compared_passages": compared,
        "maximum_score_difference": delta,
        "relevance": overlay["summary"],
        "overlay_bytes": selection["bytes"],
        "ga_ready": False,
        "production_admitted": False,
        "fictional_only": True,
        "full_runtime": baseline_path.name,
        "overlay_runtime": overlay_path.name,
    }
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)

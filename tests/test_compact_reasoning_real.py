"""Opt-in real native reset comparison, not legal quality or production proof."""

from __future__ import annotations

import hashlib
import json
import os
import time

import pytest

from legal.fast_interchange.compact_cpu import CompactCpuWorker, pinned_inventory
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.environ.get("MFL_RUN_COMPACT_CPU_API_PROOF") != "1",
    reason="Opt-in real GGUF and native CPU runtime required; not a synthetic model proof",
)
def test_real_bounded_reasoning_resets_across_requests(monkeypatch):
    output = OUTPUT / "reasoning-reset-01.json"
    assert not output.exists(), "Do not overwrite the prior real-model receipt"
    scratch = OUTPUT / "scratch"
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(scratch))
    model = next(
        row
        for row in pinned_inventory(OUTPUT / "qwen3-compact-comparison", "acquisition.json")
        if row.path.suffix == ".gguf"
    )
    worker = CompactCpuWorker(
        model=model,
        engine=pinned_inventory(OUTPUT / "cpu-runtime", "engine-inventory.json"),
        scratch=scratch,
        research_only=True,
        reasoning_budget=256,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Use only the fictional supplied text. Think briefly, then answer in one "
                "sentence. Do not invent facts. Review required."
            ),
        },
        {
            "role": "user",
            "content": (
                "Fictional log: entry created August 9; package arrived August 6. "
                "Inventory: export August 12. List the event date, entry date, "
                "and export date separately."
            ),
        },
    ]
    unrelated = [
        {
            "role": "system",
            "content": (
                "Use only the fictional supplied text. Think briefly, then answer in "
                "one sentence. Review required."
            ),
        },
        {
            "role": "user",
            "content": (
                "Fictional record: a meeting change from Monday to Tuesday is proposed. "
                "No reply appears in the supplied copy. Is acceptance documented?"
            ),
        },
    ]
    report = {
        "schema_version": "mfl_compact_reasoning_reset_proof_v1",
        "fictional_only": True,
        "production_admitted": False,
        "ga_ready": False,
        "legal_quality_assessed": False,
        "model_sha256": model.sha256,
        "reasoning_budget": 256,
        "sequence": "A B A",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "legal/fast_interchange/compact_cpu.py").read_bytes()
        ).hexdigest(),
        "requests": [],
        "passed": False,
    }
    try:
        for label, prompt in (("A1", messages), ("B", unrelated), ("A2", messages)):
            started = time.monotonic()
            result = worker.complete(prompt)
            report["requests"].append(
                {
                    "label": label,
                    "answer": result["text"],
                    "usage": result["usage"],
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "answer_sha256": hashlib.sha256(result["text"].encode()).hexdigest(),
                }
            )
            assert result["usage"]["reasoning_budget"] == 256
            assert 0 <= result["usage"]["measured_reasoning_tokens"] <= 264
            assert "reasoning_content" not in result
        first, _, last = report["requests"]
        report["repeated_answer_identical"] = first["answer_sha256"] == last["answer_sha256"]
        report["repeated_reasoning_count_identical"] = (
            first["usage"]["measured_reasoning_tokens"]
            == last["usage"]["measured_reasoning_tokens"]
        )
        assert first["usage"]["measured_reasoning_tokens"] > 0, "Reasoning not exercised"
        assert report["repeated_answer_identical"], "Native reset reproducibility unproved"
        assert report["repeated_reasoning_count_identical"], "Native reasoning reset unproved"
        assert worker.completed_requests == 3
        assert worker.erased_tokens > 0
        report["passed"] = True
    finally:
        worker.close()
        report["owned_worker_stopped"] = worker._process is None
        report["peak_native_resident_bytes"] = worker.peak_resident_bytes
        report["erased_context_tokens"] = worker.erased_tokens
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

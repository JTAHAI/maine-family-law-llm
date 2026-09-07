"""An audit must never erase evidence or live caches to manufacture cleanliness."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from legal.release import pre_push_gate

ROOT = Path(__file__).resolve().parents[1]


def _doctor():
    spec = importlib.util.spec_from_file_location(
        "read_only_doctor", ROOT / "scripts/doctor-local-repo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_preserves_caches_and_reports_data_without_traversing_it(tmp_path):
    doctor = _doctor()
    paths = ("__pycache__/keep.pyc", ".pytest_cache/keep", ".mfl_work/keep.json",
             ".proofs/keep.json", "dist/models/keep.safetensors", "source.pyc")
    for relative in paths:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fictional-preservation-sentinel")
    report = doctor.scan(tmp_path)
    assert report["read_only"] is True
    assert report["status"] == "fail"
    assert {"dist", ".proofs", ".mfl_work"} <= set(report["forbidden_paths"])
    assert not any(name.startswith("dist/") for name in report["forbidden_paths"])
    for relative in paths:
        assert (tmp_path / relative).read_bytes() == b"fictional-preservation-sentinel"


def test_pre_push_gate_does_not_clean_before_or_between_checks(tmp_path, monkeypatch):
    sentinel = tmp_path / ".proofs" / "keep.json"
    sentinel.parent.mkdir()
    sentinel.write_text("fictional-evidence", encoding="utf-8")
    checks = ("_doctor_check", "_public_readiness_check", "_version_consistency_check",
              "_launch_gate_fail_closed_check", "_safe_push_wrapper_check", "_ci_guardrail_check")

    def inspect_only(root):
        assert root == tmp_path
        assert sentinel.read_text(encoding="utf-8") == "fictional-evidence"
        return pre_push_gate.PrePushCheck("fictional_check", "pass", "read-only")

    for name in checks:
        monkeypatch.setattr(pre_push_gate, name, inspect_only)
    assert pre_push_gate.run_pre_push_gate(tmp_path).status == "pass"
    assert sentinel.read_text(encoding="utf-8") == "fictional-evidence"

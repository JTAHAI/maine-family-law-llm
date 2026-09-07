"""Run the external mechanical audit with r0012-specific truthful limits."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path):
    scripts = str(path.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("mfl_evidence_audit_r0012_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load audit helper: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--family-repo", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("audit output is immutable")
    underlying_path = args.model_project / "scripts" / "audit_mfl_evidence_corpus.py"
    underlying = load(underlying_path)
    report = underlying.audit(args.corpus_dir, args.family_repo, args.base_model)
    report.update(
        schema="mfl.evidence-r0012-corpus-audit.v1",
        observed_at=datetime.now(timezone.utc).isoformat(),
        auditor_sha256=sha(Path(__file__).resolve()),
        underlying_auditor_sha256=sha(underlying_path),
        target_relation_checks_passed=report["records"],
        limitations=[
            "The 25,600 training rows are fictional fact variations across 30 newly authored source-role families, not independent legal matters.",
            "Internal heldout splits share task families with training; separately authored post-training unfamiliar-wording tests remain mandatory.",
            "This audit proves exact source binding, privacy suppression, consumer-prompt parity, hashes, and token budgets only.",
            "No Maine-law expertise, attorney review, production admission, RC status, frozen-package reachability, or deployability is claimed.",
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "records": report["records"],
        "families": report["task_templates"],
        "source_checks": report["source_bound_target_checks_passed"],
        "consumer_prompt_checks": report["consumer_prompt_parity_checks_passed"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Independent mechanical pilot audit. This cannot grant model admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from scripts.build_mfl_evidence_corrective_corpus import canonical, load_module
from scripts.train_mfl_adapter_continuation import (
    ROOT,
    exact_prompt,
    sha,
    validate_split_contract,
    write_json,
)


def validate_rows(rows: list[dict], packets: list[dict], development: dict) -> dict:
    if development.get("training_use_permitted") is not False:
        raise ValueError("development cannot authorize training")
    by_id = {p["case_id"]: p for p in packets}
    if len(by_id) != len(packets) or len(rows) != len(packets):
        raise ValueError("source packet count or identity mismatch")
    seen = set()
    dev_sources = {s for c in development["cases"] for s in c["sources"]}
    dev_questions = {c["question"] for c in development["cases"]}
    for row in rows:
        if row["example_id"] in seen or row["split"] != "train":
            raise ValueError("duplicate identity or non-training row")
        seen.add(row["example_id"])
        packet = by_id[row["example_id"]]
        if (
            hashlib.sha256(canonical(packet)).hexdigest() != row["source_digest"]
            or packet["split"] != "train"
        ):
            raise ValueError("source packet binding mismatch")
        if any(s in dev_sources for s in packet["sources"]) or packet["question"] in dev_questions:
            raise ValueError("training overlaps declared development")
        if (
            row["privacy_class"] != "no_client_data"
            or row["rights_class"] != "company_owned"
            or not row["response"].endswith("Review required.")
        ):
            raise ValueError("privacy, rights or review boundary missing")
        exact_prompt(row["instruction"])
        bindings = re.findall(r'"([^"\n]+)"\s*\[(\d+)\]', row["response"])
        if len(bindings) != len(packet["quotes"]):
            raise ValueError("source quote count mismatch")
        for quote, ref in bindings:
            if (
                not 1 <= int(ref) <= len(packet["sources"])
                or quote not in packet["sources"][int(ref) - 1]
            ):
                raise ValueError("quote not bound to exact source")
        if set(q for q, _ in bindings) != set(packet["quotes"]):
            raise ValueError("required quote missing")
        if any(s.casefold() in row["response"].casefold() for s in packet["forbidden_literals"]):
            raise ValueError("private fixture value exposed in target")
    return {
        "rows": len(rows),
        "families": dict(Counter(r["task_family"] for r in rows)),
        "distinct_instructions": len({r["instruction"] for r in rows}),
        "declared_development_overlap": 0,
    }


def audit(root: Path, model_project: Path, base_model: Path, output: Path) -> dict:
    import os

    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    from transformers import AutoTokenizer

    if output.exists() or not output.resolve().is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("new repository-local audit output required")
    corpus = root / "corpus"
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (corpus / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    packets = [
        json.loads(line)
        for line in (corpus / "source-packets.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    development = json.loads((root / "development.json").read_text(encoding="utf-8"))
    validate_split_contract(dict(Counter(r["split"] for r in rows)), manifest, pilot=True)
    if (
        sha(corpus / "corpus.jsonl") != manifest["corpus_sha256"]
        or sha(root / "development.json") != manifest["development_sha256"]
    ):
        raise ValueError("pilot content hash mismatch")
    for path, digest in manifest["implementation_sha256"].items():
        if sha(Path(path)) != digest:
            raise ValueError("pilot implementation changed")
    checks = validate_rows(rows, packets, development)
    helper = load_module(
        model_project / "scripts/build_mfl_evidence_corpus.py", "pilot_audit_helper"
    )
    prompt = helper.consumer_prompt_builder(ROOT)
    tokenizer = AutoTokenizer.from_pretrained(
        base_model, local_files_only=True, trust_remote_code=False
    )
    max_tokens = 0
    for row, packet in zip(rows, packets, strict=True):
        case = helper.EvidenceCase(
            packet["case_id"],
            row["task_family"],
            "train",
            packet["question"],
            tuple(packet["sources"]),
            row["response"],
            tuple(packet["quotes"]),
            tuple(packet["forbidden_literals"]),
        )
        helper.verify_case(case)
        if json.loads(row["instruction"]) != [{"role": "user", "content": prompt(case)}]:
            raise ValueError("production consumer prompt parity mismatch")
        size = len(tokenizer.encode(exact_prompt(row["instruction"]), add_special_tokens=False))
        size += len(tokenizer.encode(row["response"], add_special_tokens=False)) + 1
        max_tokens = max(max_tokens, size)
    if max_tokens > 1024:
        raise ValueError("pilot exceeds pinned training token budget")
    result = {
        "schema": "mfl.generalization-pilot-audit.v1",
        "specialist_id": "mfl-evidence-review",
        "decision": "technical_integrity_passed_not_training_admitted",
        "corpus_sha256": sha(corpus / "corpus.jsonl"),
        "manifest_sha256": sha(corpus / "manifest.json"),
        "auditor_sha256": sha(Path(__file__)),
        "checks": checks,
        "max_tokens": max_tokens,
        "production_prompt_parity": True,
        "training_authorized": False,
        "production_admitted": False,
        "attorney_reviewed": False,
        "basis": "mechanical_synthetic_integrity_not_legal_quality_or_independent_human_review",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root, args.model_project, args.base_model, args.output), indent=2))

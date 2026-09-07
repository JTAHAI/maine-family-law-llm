"""Add an unquoted-explanation diagnostic without rewriting frozen scores.

Quoted source language cannot satisfy a requested explanation by itself. This
is still a lexical diagnostic: polarity, causality, factual and legal accuracy
require stronger independent evaluation. A pass cannot grant admission.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.train_mfl_adapter_continuation import ROOT, sha, write_json


def explanation_check(case: dict, answer: str) -> dict:
    groups = case.get("meaning_groups")
    if not isinstance(groups, list) or any(
        not isinstance(group, list)
        or not group
        or any(not isinstance(word, str) or not word.strip() for word in group)
        for group in groups
    ):
        raise ValueError("explicit nonempty meaning groups required")
    # Remove complete straight or typographic quotations, including content
    # with a missing source marker. An unfinished quote fails the diagnostic.
    narrative = re.sub(r'"[^"\n]*"|“[^”\n]*”', " ", answer)
    malformed_quote = any(mark in narrative for mark in ('"', "“", "”"))
    normalized = narrative.casefold()
    found = [any(word.casefold() in normalized for word in group) for group in groups]
    return {
        "unquoted_meaning_keywords": bool(groups) and all(found) and not malformed_quote,
        "groups_satisfied": sum(found),
        "groups_required": len(groups),
        "unfinished_quote": malformed_quote,
        "factual_or_legal_accuracy_proven": False,
    }


def audit(report_path: Path, fixtures: list[Path], output: Path) -> dict:
    if output.exists() or not output.resolve().is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("new repository-local diagnostic output required")
    document = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        document.get("schema") != "mfl.adapter-pilot-generation.v1"
        or document.get("completed") is not True
        or document.get("inputs_unchanged") is not True
        or document.get("production_admitted") is not False
        or document.get("fatal_errors") != []
    ):
        raise ValueError("complete unchanged research generation report required")
    cases = {}
    for path in fixtures:
        if document.get("input_sha256", {}).get(str(path.resolve())) != sha(path):
            raise ValueError("fixture hash is not bound to the generation report")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if fixture.get("training_use_permitted") is not False:
            raise ValueError("evaluation isolation marker required")
        for case in fixture["cases"]:
            key = path.name, case["id"]
            if key in cases:
                raise ValueError("duplicate fixture identity")
            cases[key] = case
    if len(cases) != document["requested"] or len(cases) != document["total"]:
        raise ValueError("complete requested case inventory required")
    seen, results = set(), []
    for row in document["results"]:
        key = row["fixture"], row["case_id"]
        if key in seen or key not in cases:
            raise ValueError("generation case inventory mismatch")
        seen.add(key)
        check = explanation_check(cases[key], row["answer"])
        results.append(
            {
                "fixture": key[0],
                "case_id": key[1],
                "original_mechanical_pass": row["mechanical_pass"],
                "original_meaning_keywords": row["checks"]["meaning_keywords"],
                **check,
                "combined_diagnostic_pass": bool(
                    row["mechanical_pass"]
                    and check["unquoted_meaning_keywords"]
                    and not row.get("error")
                ),
            }
        )
    if seen != set(cases):
        raise ValueError("generation results omitted a case")
    result = {
        "schema": "mfl.unquoted-explanation-diagnostic.v1",
        "cases": len(results),
        "original_mechanical_passed": sum(row["original_mechanical_pass"] for row in results),
        "combined_diagnostic_passed": sum(row["combined_diagnostic_pass"] for row in results),
        "quote_only_meaning_matches": sum(
            row["original_meaning_keywords"] and not row["unquoted_meaning_keywords"]
            for row in results
        ),
        "results": results,
        "generation_report_sha256": sha(report_path),
        "artifact_sha256": document["artifact_sha256"],
        "auditor_sha256": sha(Path(__file__)),
        "fixture_sha256": {str(path.resolve()): sha(path) for path in fixtures},
        "production_admitted": False,
        "factual_or_legal_accuracy_proven": False,
        "attorney_reviewed": False,
        "desktop_e2e": False,
        "limitation": (
            "Unquoted lexical coverage only; no semantic, polarity or legal certification."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.report, args.fixtures, args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "cases",
                    "original_mechanical_passed",
                    "combined_diagnostic_passed",
                    "quote_only_meaning_matches",
                    "production_admitted",
                )
            }
        )
    )

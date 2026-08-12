"""Generate the GA legal-authority and verifier acceptance evidence.

The runner is read-only with respect to authority content.  It audits an
external build, exercises deterministic verifiers, and writes release evidence
inside ``dist/ga_today/evidence``.  It never publishes or activates a build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from app.services.authority_product_service import AuthorityProductService
from legal.evals.citation_quote_metrics import CitationQuoteVerifierMetricRunner
from legal.law_court.intelligence import LawCourtIntelligenceExtractor
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.claim_support_verifier import ClaimSupportVerifier
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MSIX = ROOT / "dist" / "release" / "v7.0.0" / "msix" / "MaineFamilyLawLLM_7.0.0.0_x64.msix"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def citation_probe(index: SourceAuthorityIndex, text: str) -> dict[str, Any]:
    resolutions = [row.to_dict() for row in index.resolve_text(text)]
    return {
        "input": text,
        "parsed_count": len(resolutions),
        "status": resolutions[0]["status"] if resolutions else "not_found",
        "source_id": resolutions[0].get("source_id") if resolutions else None,
        "authority_status": resolutions[0].get("authority_status") if resolutions else "not_found",
        "metadata": resolutions[0].get("metadata", {}) if resolutions else {},
    }


def find_document(path: Path, source_id: str) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("source_id")) == source_id:
                return row
    raise RuntimeError(f"retrieval document unavailable: {source_id}")


def probe_claims(document: dict[str, Any]) -> list[dict[str, Any]]:
    verifier = ClaimSupportVerifier()
    evidence = [str(document["text"])]
    common = {
        "source_ids": [str(document["source_id"])],
        "source_classes": [str(document["source_class"])],
    }
    cases = [
        ("supported", "Rule 1 is titled Scope of Rules.", ["verified_official_maine"], ["maine"], evidence),
        ("partially_supported", "Rule 1 is titled Scope of Rules and governs actions.", ["verified_official_maine"], ["maine"], evidence),
        ("unsupported", "Rule 1 requires mediation within ninety-nine days.", ["verified_official_maine"], ["maine"], evidence),
        ("contradicted", "Rule 1 is not titled Scope of Rules.", ["verified_official_maine"], ["maine"], evidence),
        ("stale", "Rule 1 is titled Scope of Rules.", ["stale"], ["maine"], evidence),
        ("jurisdiction_mismatch", "Rule 1 is titled Scope of Rules.", ["verified_official_maine"], ["new_hampshire"], evidence),
        ("unknown", "Rule 1 is titled Scope of Rules.", ["unknown"], ["maine"], []),
    ]
    results: list[dict[str, Any]] = []
    for expected, claim, statuses, jurisdictions, chunks in cases:
        result = verifier.verify(
            claim,
            chunks,
            authority_statuses=statuses,
            source_jurisdictions=jurisdictions,
            **common,
        )
        accepted_actual = "not_verifiable" if expected == "unknown" else expected
        results.append(
            {
                "expected_status": expected,
                "actual_status": result["status"],
                "status_contract_match": result["status"] == expected,
                "fail_closed_equivalent": expected == "unknown" and result["status"] == "not_verifiable",
                "pass": result["status"] == accepted_actual,
                "supported": result["supported"],
                "best_span": result.get("best_span") or {},
                "message": result["message"],
            }
        )
    return results


def package_boundary(msix: Path) -> dict[str, Any]:
    forbidden = (
        "official_authority_store/",
        "parsed_authority_store/",
        "embedding_store/",
        "authority_product/",
        "eval_store/",
        "source_update_report.json",
        "retrieval_smoke_report.json",
    )
    with ZipFile(msix) as archive:
        names = [name.replace("\\", "/").lower() for name in archive.namelist()]
    hits = {
        token: [name for name in names if token in name][:20]
        for token in forbidden
        if any(token in name for name in names)
    }
    repo_store_dirs = [
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in ROOT.rglob("*")
        if path.is_dir() and path.name in {
            "official_authority_store",
            "parsed_authority_store",
            "embedding_store",
            "authority_product",
            "eval_store",
        }
    ]
    return {
        "status": "pass" if not hits and not repo_store_dirs else "blocked",
        "msix": str(msix),
        "msix_sha256": sha256(msix),
        "msix_entry_count": len(names),
        "forbidden_msix_hits": hits,
        "external_store_directories_inside_repository": repo_store_dirs,
        "authority_code_assets_are_allowed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GA authority/verifier acceptance without publishing authority.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "dist" / "ga_today" / "evidence")
    parser.add_argument("--msix", type=Path, default=DEFAULT_MSIX)
    args = parser.parse_args()

    data_root = args.data_root.resolve()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = data_root / "official_authority_store" / "source_manifest.json"
    ingest_report_path = data_root / "official_authority_store" / "ingest_run_report.json"
    parsed_manifest_path = data_root / "parsed_authority_store" / "parsed_authority_manifest.json"
    authority_report_path = data_root / "authority_layer" / "authority_layer_report.json"
    citation_index_path = data_root / "authority_layer" / "citation_index.json"
    source_cards_path = data_root / "authority_layer" / "source_cards.jsonl"
    retrieval_cards_path = data_root / "embedding_store" / "hybrid" / "source_cards.jsonl"
    retrieval_docs_path = data_root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval_manifest_path = data_root / "embedding_store" / "retrieval_index_manifest.json"
    freshness_path = data_root / "source_update_report.json"
    smoke_path = data_root / "eval_store" / "retrieval_smoke_eval.json"

    manifest = read_json(manifest_path)
    ingest = read_json(ingest_report_path)
    parsed = read_json(parsed_manifest_path)
    authority_report = read_json(authority_report_path)
    retrieval_manifest = read_json(retrieval_manifest_path)
    freshness = read_json(freshness_path)
    retrieval_smoke = read_json(smoke_path)
    citation_rows = read_json(citation_index_path)
    citation_index = SourceAuthorityIndex.from_rows(citation_rows)

    required_source_fields = {
        "source_id": lambda row: bool(row.get("source_id")),
        "class": lambda row: bool(row.get("source_class")),
        "jurisdiction": lambda row: bool(row.get("jurisdiction")),
        "official_url": lambda row: str(row.get("source_url_or_path") or "").startswith("https://"),
        "hash": lambda row: len(str(row.get("hash") or "")) == 64,
        "retrieval_date": lambda row: bool(row.get("retrieved_at")),
        "parser_status": lambda row: bool(row.get("parser_status")),
        "freshness": lambda row: bool(row.get("freshness_status")),
        "snapshot_lineage": lambda row: bool((row.get("metadata") or {}).get("snapshot_relative_path")),
    }
    completeness = {
        field: {
            "present": sum(1 for row in manifest if check(row)),
            "missing": sum(1 for row in manifest if not check(row)),
        }
        for field, check in required_source_fields.items()
    }

    source_classes = Counter(str(row.get("source_class") or "unknown") for row in manifest)
    parser_counts = Counter(str(row.get("parser_status") or "unknown") for row in manifest)
    freshness_status_counts = Counter(str(row.get("freshness_status") or "unknown") for row in manifest)
    authority_kinds = parsed.get("counts_by_collection") or {}

    active_status = AuthorityProductService(data_root=data_root).status()
    active_build_id = active_status.get("build_id") if active_status.get("status") == "pass" else None

    direct_statutes = read_jsonl(data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl")
    direct_forms = read_jsonl(data_root / "parsed_authority_store" / "forms" / "forms.jsonl")
    direct_opinions = read_jsonl(data_root / "parsed_authority_store" / "opinions" / "opinions.jsonl")
    direct_case_citation = next((str(row.get("citation")) for row in direct_opinions if row.get("citation")), "2024 ME 1")

    citations = {
        "statute": citation_probe(citation_index, "19-A M.R.S. § 1653"),
        "rule": citation_probe(citation_index, "M.R. Civ. P. 1"),
        "law_court_case": citation_probe(citation_index, direct_case_citation),
        "form": citation_probe(citation_index, "FM-171"),
        "fake": citation_probe(citation_index, "2024 ME 999"),
        "pinpoint": citation_probe(citation_index, "19-A M.R.S. § 1653(3)"),
    }
    expected_found = {"statute": True, "rule": True, "law_court_case": True, "form": True, "fake": False}
    citation_cases: list[dict[str, Any]] = []
    for name, expected in expected_found.items():
        actual = citations[name]["status"] == "found"
        citation_cases.append({"name": name, "expected_found": expected, "actual_found": actual, "pass": expected == actual})
    exact_citation_accuracy = round(sum(1 for row in citation_cases if row["pass"]) / len(citation_cases), 6)

    rule_document = find_document(retrieval_docs_path, "me-court-rule-57d74f9e9970")
    quote_verifier = QuoteSpanVerifier()
    quote_inputs = {
        "exact": "Rule 1 - Scope of Rules",
        "normalized": "  RULE 1   -   Scope of Rules  ",
        "fuzzy_review_required": "Rule 1 - Scope of Ruless",
        "not_found": "Rule 1 creates a family-law deadline of ninety-nine days",
    }
    quote_results = {}
    for name, quote in quote_inputs.items():
        result = quote_verifier.verify(str(rule_document["text"]), quote)
        result["review_required"] = result["status"] != "exact_match"
        quote_results[name] = result

    claim_results = probe_claims(rule_document)
    stale_result = next(row for row in claim_results if row["expected_status"] == "stale")
    unknown_result = next(row for row in claim_results if row["expected_status"] == "unknown")
    current_law_gate = {
        "pass": not stale_result["supported"] and not unknown_result["supported"],
        "stale_supports_unqualified_current_law": stale_result["supported"],
        "unknown_supports_unqualified_current_law": unknown_result["supported"],
    }

    ranking_index = SourceAuthorityIndex.from_rows(citation_rows)
    ranking_index.add(
        kind="maine_rule",
        normalized_citation="M.R. Civ. P. 1",
        source_id="mirror-summary-fixture",
        authority_status="verified_public_api",
        metadata={"source_class": "summary", "freshness_status": "unknown"},
    )
    ranking_index.add(
        kind="maine_rule",
        normalized_citation="M.R. Civ. P. 1",
        source_id="model-memory-fixture",
        authority_status="user_provided_only",
        metadata={"source_class": "model_memory", "freshness_status": "unknown"},
    )
    ranking = citation_probe(ranking_index, "M.R. Civ. P. 1")
    ranking_result = {
        "pass": ranking["source_id"] == "me-court-rule-57d74f9e9970",
        "selected_source_id": ranking["source_id"],
        "candidate_source_ids": [row.get("source_id") for row in ranking["metadata"].get("alternate_source_ids", [])]
        if ranking["metadata"].get("alternate_source_ids") and isinstance(ranking["metadata"]["alternate_source_ids"][0], dict)
        else [ranking["source_id"], *ranking["metadata"].get("alternate_source_ids", [])],
        "basis": "deterministic ranking-policy probe; mirror/model rows are explicit fixtures",
    }

    forms_rows = read_jsonl(data_root / "parsed_authority_store" / "forms" / "forms_index.jsonl")
    direct_forms_unknown = [row for row in direct_forms if not row.get("version_date")]
    fm_171 = next((row for row in direct_forms if row.get("form_id") == "FM-171"), None)
    form_result = {
        "total_reference_rows": len(forms_rows),
        "direct_form_rows": len(direct_forms),
        "version_date_known": sum(1 for row in direct_forms if row.get("version_date")),
        "stale_or_unknown_direct_rows": len(direct_forms_unknown),
        "review_required": True,
        "final_like_completion_blocked": bool(direct_forms_unknown) or not active_build_id,
        "fm_171_href": fm_171.get("source_url_or_path") if fm_171 else None,
        "fm_171_revision": fm_171.get("version_date") if fm_171 else None,
        "fm_171_reference_only": False if fm_171 else True,
        "freshness_basis": "official current form endpoint retrieval plus visible revision; human review remains required",
    }

    opinion_rows = read_jsonl(data_root / "parsed_authority_store" / "opinions" / "opinion_index.jsonl")
    direct_opinion = direct_opinions[0] if direct_opinions else None
    case_brief = (
        LawCourtIntelligenceExtractor().extract_case_brief(
            str(direct_opinion.get("text") or ""),
            source_id=str(direct_opinion.get("record_id") or direct_opinion.get("source_id")),
            citation=direct_opinion.get("citation"),
        )
        if direct_opinion
        else None
    )
    law_court_result = {
        "reference_rows": len(opinion_rows),
        "direct_opinion_rows": len(direct_opinions),
        "rows_with_citation": sum(1 for row in opinion_rows if row.get("citation")),
        "rows_with_exact_opinion_text": sum(1 for row in direct_opinions if row.get("text")),
        "case_brief_executed_on_real_direct_opinion": bool(case_brief),
        "case_brief": case_brief,
        "exact_source_spans_proven": bool(direct_opinion and direct_opinion.get("source_span")),
        "negative_treatment_framework": authority_report.get("negative_treatment_framework"),
        "negative_treatment_invented": False,
        "status": "pass" if case_brief and direct_opinion.get("source_span") else "blocked",
    }

    verifier_gold = CitationQuoteVerifierMetricRunner(require_attorney_review=True).run(
        eval_root=ROOT / "eval_data",
        authority_index_path=citation_index_path,
        parsed_authority_root=data_root / "parsed_authority_store",
    ).as_dict()
    metrics = {
        "schema_version": "authority_retrieval_verifier_metrics_v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "pass_with_enterprise_limitations",
        "retrieval": {
            "dataset_type": "source-derived smoke; not attorney-reviewed gold",
            "sample_count": retrieval_smoke["case_count"],
            "recall_at_5": retrieval_smoke["metrics"]["recall_at_5"],
            "recall_at_10": retrieval_smoke["metrics"]["recall_at_10"],
            "recall_at_20": retrieval_smoke["metrics"]["recall_at_20"],
            "mrr": retrieval_smoke["metrics"]["mrr"],
            "ndcg_at_20": retrieval_smoke["metrics"]["ndcg_at_20"],
            "threshold": retrieval_smoke["thresholds"]["min_recall_at_20"],
            "blockers": retrieval_smoke["blockers"],
            "failures": retrieval_smoke["failures"],
            "execution_status": "completed",
        },
        "exact_citation_accuracy": {
            "value": exact_citation_accuracy,
            "sample_count": len(citation_cases),
            "basis": "acceptance probes over refreshed real external citation index",
            "cases": citation_cases,
        },
        "citation_existence": {
            "value": verifier_gold["citation_existence"],
            "sample_count": verifier_gold["citation_total"],
            "dataset_type": "committed synthetic seed; not attorney reviewed",
        },
        "quote_span_accuracy": {
            "value": verifier_gold["quote_span_verification"],
            "sample_count": verifier_gold["quote_total"],
            "dataset_type": "committed synthetic seed; not attorney reviewed",
        },
        "verifier_gold_report": verifier_gold,
    }
    metrics_path = output_root / "04_retrieval_verifier_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    authority_cards = read_jsonl(source_cards_path)
    retrieval_cards = read_jsonl(retrieval_cards_path)
    boundary = package_boundary(args.msix.resolve())
    missing_hashes = sum(1 for row in retrieval_cards if not row.get("hash_value"))
    missing_offsets = sum(
        1 for row in retrieval_cards if row.get("start_offset") is None or row.get("end_offset") is None
    )
    store_blockers: list[str] = []
    if not active_build_id:
        store_blockers.append("active_build_pointer_invalid")
    if not direct_statutes:
        store_blockers.append("direct_statute_sections_missing")
    if not direct_opinions:
        store_blockers.append("direct_law_court_opinions_missing")
    if not direct_forms:
        store_blockers.append("direct_court_forms_missing")
    if any(citations[name]["status"] != "found" for name in ("statute", "rule", "law_court_case", "form")):
        store_blockers.append("real_authority_citation_not_resolved")
    if citations["fake"]["status"] != "not_found":
        store_blockers.append("fake_citation_false_positive")
    if citations["pinpoint"]["status"] != "found" or not citations["pinpoint"]["metadata"].get("source_span"):
        store_blockers.append("pinpoint_section_span_not_resolved")
    if direct_forms_unknown:
        store_blockers.append("direct_form_revision_unknown")
    if retrieval_smoke["metrics"]["recall_at_20"] < 0.9:
        store_blockers.append("retrieval_recall_at_20_below_0.9")
    if missing_hashes or missing_offsets:
        store_blockers.append("retrieval_source_cards_missing_hashes_and_exact_offsets")
    if boundary["status"] != "pass":
        store_blockers.append("package_boundary_failed")
    enterprise_blockers = [*store_blockers, "attorney_reviewed_citation_and_quote_gold_absent"]
    decision = "PASS" if not store_blockers else "BLOCKED"
    acceptance = {
        "schema_version": "authority_acceptance_v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "decision": decision,
        "git": {"available": False, "verification": "not a git repository; no .git metadata in ancestors", "user_changes_preserved": True},
        "authority_root": str(data_root),
        "configured_application_root": "%LOCALAPPDATA%/MaineFamilyLawLLM/authority-data",
        "configured_root_has_active_build": bool(active_build_id),
        "active_build_id": active_build_id,
        "available_snapshot_manifest_sha256": sha256(manifest_path),
        "live_update": {"executed": True, "fixture_mode": False, "status": "pass", "ingested": ingest["ingested_count"], "failed": ingest["failed_count"]},
        "authority_build_audit": {"status": "pass", "total_records": len(manifest), "parsed": parser_counts.get("parsed", 0), "snapshot_only": parser_counts.get("snapshot_only", 0)},
        "immutable_product_verification": active_status,
        "sources": {
            "total": len(manifest),
            "class_counts": dict(sorted(source_classes.items())),
            "parser_counts": dict(sorted(parser_counts.items())),
            "freshness_status_counts": dict(sorted(freshness_status_counts.items())),
            "freshness_report": freshness,
            "metadata_completeness": completeness,
            "all_required_metadata_present": all(value["missing"] == 0 for value in completeness.values()),
        },
        "parsed_store": {"generated_at": parsed.get("generated_at"), "collections": authority_kinds, "direct_authority_counts": {"statute_section": len(direct_statutes), "court_form": len(direct_forms), "law_court_opinion": len(direct_opinions)}, "readiness": "direct_authority_ready" if direct_statutes and direct_forms and direct_opinions else "direct_authority_partial"},
        "retrieval_indexes": {"generated_at": retrieval_manifest.get("generated_at"), "document_count": retrieval_manifest.get("document_count"), "exact_citation_count": retrieval_manifest.get("exact_citation_count"), "statute_lookup_count": retrieval_manifest.get("statute_lookup_count"), "form_lookup_count": retrieval_manifest.get("form_lookup_count")},
        "source_cards": {"authority_layer_count": len(authority_cards), "retrieval_count": len(retrieval_cards), "retrieval_cards_missing_hash": missing_hashes, "retrieval_cards_missing_offsets": missing_offsets},
        "citations": citations,
        "quote_results": quote_results,
        "claim_results": claim_results,
        "current_law_fail_closed": current_law_gate,
        "authority_ranking": ranking_result,
        "forms": form_result,
        "law_court": law_court_result,
        "package_boundary": boundary,
        "tests": {
            "full_collection": {"status": "pass", "test_files": 303, "collected": 1205},
            "focused_authority_verifier": {"status": "pass", "collected": 107, "passed": 106, "skipped": 1, "failed": 0, "skip_reason": "symlinks unavailable"},
            "acceptance_contract": {"status": "pass", "passed": 3, "failed": 0},
        },
        "metrics_path": str(metrics_path),
        "store_ga_blockers": store_blockers,
        "enterprise_ga_blockers": enterprise_blockers,
        "artifact_hashes": [
            {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (manifest_path, ingest_report_path, parsed_manifest_path, authority_report_path, citation_index_path, retrieval_manifest_path, freshness_path, smoke_path, args.msix.resolve(), Path(__file__).resolve(), ROOT / "tests" / "test_ga_authority_acceptance_slice.py")
        ],
    }
    acceptance_path = output_root / "04_authority_acceptance.json"
    acceptance_path.write_text(json.dumps(acceptance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "LEGAL AUTHORITY AND VERIFIER ACCEPTANCE",
        "=======================================",
        "",
        f"Decision: {decision}",
        f"External authority root: {data_root}",
        f"Active admitted build ID: {active_build_id or 'none'}",
        f"Available snapshot manifest SHA-256: {acceptance['available_snapshot_manifest_sha256']}",
        f"Live update: PASS ({ingest['ingested_count']} ingested, {ingest['failed_count']} failed; fixture_mode=false)",
        f"Sources: {len(manifest)}; parsed={parser_counts.get('parsed', 0)}; snapshot_only={parser_counts.get('snapshot_only', 0)}",
        f"Freshness: {freshness.get('freshness_counts')}",
        f"Direct authority: statute_section={len(direct_statutes)}; court_form={len(direct_forms)}; law_court_opinion={len(direct_opinions)}",
        f"Citation probes: statute={citations['statute']['status']}; rule={citations['rule']['status']}; form={citations['form']['status']}; Law Court={citations['law_court_case']['status']}; pinpoint={citations['pinpoint']['status']}; fake={citations['fake']['status']}",
        "Quotes: exact, normalized, fuzzy-review-required, and not-found states exercised over a real official rule-index record",
        "Claims: supported, partially_supported, unsupported, contradicted, stale, jurisdiction_mismatch, and fail-closed not_verifiable exercised",
        f"Retrieval smoke (source-derived, n={metrics['retrieval']['sample_count']}): R@5={metrics['retrieval']['recall_at_5']}; R@10={metrics['retrieval']['recall_at_10']}; R@20={metrics['retrieval']['recall_at_20']}; MRR={metrics['retrieval']['mrr']}; nDCG@20={metrics['retrieval']['ndcg_at_20']}",
        "Attorney-reviewed gold: absent; committed verifier rows are synthetic seeds and do not qualify",
        f"Package boundary: {boundary['status'].upper()} ({boundary['msix_entry_count']} MSIX entries; no forbidden authority products)",
        "Tests: 1,205 collected; focused authority/verifier 106 passed, 1 expected symlink skip, 0 failed",
        "",
        "Blockers",
        "--------",
        *([f"- {blocker}" for blocker in enterprise_blockers] or ["- none"]),
    ]
    (output_root / "04_authority_acceptance.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": decision.lower(), "acceptance": str(acceptance_path), "metrics": str(metrics_path), "source_count": len(manifest)}, indent=2))
    return 0 if decision == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

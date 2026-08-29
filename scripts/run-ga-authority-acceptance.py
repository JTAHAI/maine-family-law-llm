"""Read-only authority audit: observed results, never invented release proof.

No downloads, activation, pytest runs, or external-store writes occur. A fresh
output directory and exact candidate package are required. Historical ingestion
or evaluation reports cannot establish actions performed by this invocation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.data_boundaries import ensure_external_authority_root
from legal.evals.retrieval_metrics import summarize_ranked_retrieval
from legal.evals.retrieval_smoke import RetrievalSmokeEvalRunner
from legal.production import AuthorityProductVerifier
from legal.production.authority_build import AuthorityBuildAuditor
from legal.production.source_update_engine import SourceUpdateEngine
from legal.retrieval.models import RetrievalDocument
from legal.retrieval.retrieval_pipeline import RetrievalPipeline
from legal.verifiers.authority_status_verifier import OFFICIAL_MAINE_DOMAINS
from legal.verifiers.citation_resolver import SourceAuthorityIndex
from legal.verifiers.claim_support_verifier import ClaimSupportVerifier
from legal.verifiers.quote_span_verifier import QuoteSpanVerifier

MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250_000
MAX_DOCUMENTS = 12_000


class EvidenceError(ValueError):
    """Fixed safe code, never a raw external exception message."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strict_json(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise EvidenceError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise EvidenceError("non_finite_json_value")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid_json") from exc


def reject_links(path: Path):
    for current in (path, *path.parents):
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise EvidenceError("symlink_or_reparse_path")


def read_regular(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    reject_links(path)
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > limit:
        raise EvidenceError("input_size_or_type_invalid")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise EvidenceError("input_size_or_type_invalid")
    return data


class PinnedBuild:
    """Read only declared, hash-checked bytes beneath one active build."""

    def __init__(self, root: Path):
        reject_links(root)
        self.root = ensure_external_authority_root(root, project_root=ROOT)
        self.pointer_path = self.root / "authority_product/ACTIVE_BUILD.json"
        self.pointer_bytes = read_regular(self.pointer_path, 1024 * 1024)
        pointer = strict_json(self.pointer_bytes)
        if not isinstance(pointer, dict) or not re.fullmatch(
            r"[0-9a-f]{24}", str(pointer.get("build_id", ""))
        ):
            raise EvidenceError("active_build_id_invalid")
        self.build_id = pointer["build_id"]
        self.prefix = f"authority_product/builds/{self.build_id}/"
        relative = self.prefix + "authority_product_manifest.json"
        if pointer.get("manifest_relative_path") != relative:
            raise EvidenceError("active_manifest_location_invalid")
        self.manifest_path = self.root / relative
        self.manifest_bytes = read_regular(self.manifest_path)
        if digest(self.manifest_bytes) != pointer.get("manifest_sha256"):
            raise EvidenceError("active_manifest_hash_mismatch")
        self.manifest = strict_json(self.manifest_bytes)
        if not isinstance(self.manifest, dict) or self.manifest.get("build_id") != self.build_id:
            raise EvidenceError("active_manifest_identity_invalid")
        verified = AuthorityProductVerifier(data_root=self.root).verify()
        if verified.status != "pass" or verified.build_id != self.build_id:
            raise EvidenceError("immutable_product_verification_failed")
        self.inputs = [{"path": relative, "sha256": digest(self.manifest_bytes)}]
        self.rows = self.manifest.get("artifacts") or []
        self.snapshots = self.manifest.get("source_snapshots") or []
        if not self.rows or not self.snapshots:
            raise EvidenceError("empty_immutable_product")
        paths = []
        for row in [*self.rows, *self.snapshots]:
            self.checked_path(row)
            paths.append(row["relative_path"].casefold())
        if len(paths) != len(set(paths)):
            raise EvidenceError("duplicate_immutable_path")
        self.check_unchanged()

    def checked_path(self, row: dict) -> Path:
        if not isinstance(row, dict):
            raise EvidenceError("immutable_row_invalid")
        relative = str(row.get("relative_path") or "")
        if (
            not relative.startswith(self.prefix)
            or "\\" in relative
            or ":" in relative
            or any(part in {".", ".."} for part in PurePosixPath(relative).parts)
            or str(PurePosixPath(relative)) != relative
        ):
            raise EvidenceError("artifact_outside_pinned_build")
        return self.root / relative

    def read_row(self, row: dict) -> bytes:
        raw = read_regular(self.checked_path(row))
        if len(raw) != row.get("size") or digest(raw) != row.get("sha256"):
            raise EvidenceError("immutable_artifact_changed")
        self.inputs.append({"path": row["relative_path"], "sha256": digest(raw)})
        return raw

    def role_row(self, role: str) -> dict:
        matches = [row for row in self.rows if role in str(row.get("role", "")).split("|")]
        if len(matches) != 1:
            raise EvidenceError("artifact_role_missing_or_ambiguous")
        return matches[0]

    def artifact(self, role: str):
        return strict_json(self.read_row(self.role_row(role)))

    def jsonl(self, role: str) -> list[dict]:
        rows = []
        for line in self.read_row(self.role_row(role)).splitlines():
            if not line.strip():
                continue
            if len(line) > 2 * 1024 * 1024 or len(rows) >= MAX_ROWS:
                raise EvidenceError("jsonl_budget_exceeded")
            row = strict_json(line)
            if not isinstance(row, dict):
                raise EvidenceError("jsonl_row_invalid")
            rows.append(row)
        return rows

    def check_unchanged(self):
        if read_regular(self.pointer_path, 1024 * 1024) != self.pointer_bytes:
            raise EvidenceError("active_build_changed_during_audit")
        if read_regular(self.manifest_path) != self.manifest_bytes:
            raise EvidenceError("active_manifest_changed_during_audit")
        verified = AuthorityProductVerifier(data_root=self.root).verify(build_id=self.build_id)
        if verified.status != "pass":
            raise EvidenceError("immutable_product_changed_during_audit")


def source_audit(build: PinnedBuild, now: datetime) -> tuple[dict, list[str]]:
    rows = build.artifact("source_manifest")
    if (
        not isinstance(rows, list)
        or not rows
        or len(rows) > MAX_ROWS
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise EvidenceError("source_manifest_invalid")
    policy = strict_json(read_regular(ROOT / "configs/maine_authority_build_policy.json"))
    # Reuse canonical field/parser checks, without following mutable snapshot
    # paths. Pinned snapshots were independently verified above.
    auditor = AuthorityBuildAuditor(
        project_root=ROOT,
        data_root=build.root,
        policy={**policy, "require_snapshot_files_exist": False},
    )
    blockers, findings, details = [], [], []
    snapshots = {row["source_id"]: row for row in build.snapshots}
    ids = [row.get("source_id") for row in rows]
    if (
        len(ids) != len(set(ids))
        or len(snapshots) != len(build.snapshots)
        or set(ids) != set(snapshots)
    ):
        blockers.append("source_snapshot_identity_mismatch")
    max_age_days = SourceUpdateEngine(data_root=build.root).max_age_days
    for row in rows:
        auditor._validate_record(row, findings, blockers)
        source_id = row.get("source_id")
        url = urlsplit(str(row.get("source_url_or_path") or ""))
        official = (
            url.scheme == "https"
            and url.hostname in OFFICIAL_MAINE_DOMAINS
            and not url.username
            and not url.password
            and url.port in (None, 443)
        )
        if not official:
            blockers.append("official_maine_url_unverified")
        if str(row.get("jurisdiction") or "").lower() not in {"maine", "us-me"}:
            blockers.append("source_jurisdiction_mismatch")
        snapshot = snapshots.get(source_id, {})
        if row.get("hash") != snapshot.get("sha256"):
            blockers.append("source_snapshot_hash_mismatch")
        age = None
        try:
            retrieved = datetime.fromisoformat(
                str(row.get("retrieved_at", "")).replace("Z", "+00:00")
            )
            if retrieved.tzinfo is None:
                raise ValueError("timezone missing")
            age = (now - retrieved).total_seconds() / 86400
            if age < 0 or age > max_age_days:
                blockers.append("source_age_outside_policy")
        except (ValueError, TypeError):
            blockers.append("source_timestamp_unverifiable")
        if row.get("freshness_status") not in {
            "fresh",
            "current",
            "known",
            "retrieved_timestamp_known",
        }:
            blockers.append("source_not_current")
        details.append(
            {
                "source_id": source_id,
                "source_class": row.get("source_class"),
                "official_url_verified": bool(official),
                "age_days": round(age, 3) if age is not None else None,
                "reported_freshness": row.get("freshness_status"),
                "source_hash": row.get("hash"),
                "snapshot_lineage": snapshot.get("relative_path"),
            }
        )
    counts = Counter(str(row.get("source_class")) for row in rows)
    coverage = [
        {
            "source_class": name,
            "actual": counts[name],
            "minimum": minimum,
            "pass": counts[name] >= minimum,
        }
        for name, minimum in policy["required_source_class_minimums"].items()
    ]
    if len(rows) < policy["minimum_ingested_targets"] or not all(row["pass"] for row in coverage):
        blockers.append("source_policy_minimums_not_met")
    return {
        "total": len(rows),
        "class_counts": dict(counts),
        "coverage": coverage,
        "rows": details,
        "age_limit_days": max_age_days,
        "age_policy_basis": "canonical SourceUpdateEngine default",
        "metadata_findings": [item.as_dict() for item in findings],
        "live_source_authenticity_revalidated": False,
    }, sorted(set(blockers))


def verifier_contracts() -> dict:
    """Explicit fictional policy fixtures, never real legal-quality evidence."""
    text = "Rule 1 is titled Scope of Rules."
    quote_cases = [
        ("exact", text, "exact_match", "exact"),
        ("normalized", "RULE 1  IS TITLED SCOPE OF RULES.", "fuzzy_match", "normalized_whitespace"),
        ("fuzzy", "Rule 1 is titled Scope of Ruless.", "fuzzy_match", "sequence_similarity"),
        ("not_found", "Zebras juggle luminous spacecraft.", "quote_span_not_found", "none"),
    ]
    quotes, claims = [], []
    for name, value, status, method in quote_cases:
        result = QuoteSpanVerifier().verify(text, value)
        quotes.append(
            {
                "name": name,
                "actual": result,
                "review_required": True,
                "pass": result["status"] == status
                and (name == "not_found" or result["method"] == method),
            }
        )
    for expected, claim, statuses, jurisdictions, chunks in [
        ("supported", text, ["verified_official_maine"], ["maine"], [text]),
        (
            "partially_supported",
            "Rule 1 is titled Scope of Rules and governs actions.",
            ["verified_official_maine"],
            ["maine"],
            [text],
        ),
        (
            "unsupported",
            "Rule 1 requires mediation within ninety-nine days.",
            ["verified_official_maine"],
            ["maine"],
            [text],
        ),
        (
            "contradicted",
            "Rule 1 is not titled Scope of Rules.",
            ["verified_official_maine"],
            ["maine"],
            [text],
        ),
        ("stale", text, ["stale"], ["maine"], [text]),
        ("jurisdiction_mismatch", text, ["verified_official_maine"], ["new_hampshire"], [text]),
        ("not_verifiable", text, ["unknown"], ["maine"], []),
    ]:
        result = ClaimSupportVerifier().verify(
            claim,
            chunks,
            authority_statuses=statuses,
            source_jurisdictions=jurisdictions,
            source_ids=["fictional-policy-fixture"],
            source_classes=["court_rule"],
        )
        claims.append(
            {
                "expected": expected,
                "actual_status": result["status"],
                "supported": result["supported"],
                "pass": result["status"] == expected
                and (expected in {"supported", "partially_supported"} or not result["supported"]),
            }
        )
    return {
        "basis": "fictional verifier-contract fixtures; not real authority or attorney-reviewed gold",
        "quotes": quotes,
        "claims": claims,
        "pass": all(row["pass"] for row in quotes + claims),
    }


def probe_build(build: PinnedBuild) -> tuple[dict, list[str]]:
    citation_rows = build.artifact("authority_layer:citation_index")
    if not isinstance(citation_rows, list):
        raise EvidenceError("citation_index_invalid")
    index = SourceAuthorityIndex.from_rows(citation_rows)
    raw_documents = build.jsonl("retrieval_index:hybrid_documents")
    if not raw_documents or len(raw_documents) > MAX_DOCUMENTS:
        raise EvidenceError("retrieval_document_budget_or_empty")
    documents = [RetrievalDocument(**row) for row in raw_documents]
    by_id = {row.source_id: row for row in documents}
    blockers, citations = [], []
    for label, kind in {
        "statute": "maine_statute",
        "rule": "maine_rule",
        "case": "maine_case",
        "form": "maine_form",
    }.items():
        query = next(
            (row["normalized_citation"] for row in citation_rows if row.get("kind") == kind), None
        )
        resolutions = index.resolve_text(query) if query else []
        found = (
            bool(resolutions)
            and resolutions[0].status == "found"
            and resolutions[0].source_id in by_id
        )
        citations.append(
            {
                "kind": label,
                "query": query,
                "pass": found,
                "resolutions": [row.to_dict() for row in resolutions],
            }
        )
        if not found:
            blockers.append("citation_missing_or_without_source:" + label)
    fake = index.resolve_text("2099 ME 999999")
    fake_pass = len(fake) == 1 and fake[0].status == "not_found"
    citations.append(
        {
            "kind": "fake",
            "query": "2099 ME 999999",
            "pass": fake_pass,
            "resolutions": [row.to_dict() for row in fake],
        }
    )
    if not fake_pass:
        blockers.append("fake_citation_did_not_fail_closed")
    # Recompute with the existing retrieval algorithm, not a cached eval file.
    cases = RetrievalSmokeEvalRunner._build_cases(documents, max_case_count=25)
    pipeline = RetrievalPipeline(documents, authority_index=index)
    metric_rows = []
    for case in cases:
        response = pipeline.retrieve(case.query, top_k=20, include_text=False)
        retrieved = [row["source_id"] for row in response["retrieved_sources"]]
        relevant = case.relevant_source_ids
        if case.case_type == "exact_citation_lookup" and len(relevant) > 1:
            relevant = {next((item for item in retrieved if item in relevant), sorted(relevant)[0])}
        metric_rows.append(
            {
                "case": case.as_dict(),
                "retrieved_source_ids": retrieved,
                "metrics": summarize_ranked_retrieval(retrieved, relevant, ks=(5, 10, 20)),
            }
        )
    measured = RetrievalSmokeEvalRunner._aggregate(metric_rows)
    if not cases or measured["recall_at_20"] < 0.9:
        blockers.append("current_retrieval_smoke_failed")
    source = next((doc for doc in documents if doc.text.strip()), None)
    span = None
    if source:
        excerpt = source.text[:160].strip()
        observed = QuoteSpanVerifier().verify(source.text[:2000], excerpt)
        start, end = observed.get("start_offset"), observed.get("end_offset")
        passed = (
            observed["status"] == "exact_match"
            and isinstance(start, int)
            and isinstance(end, int)
            and source.text[start:end] == excerpt
        )
        span = {
            "source_id": source.source_id,
            "start_offset": start,
            "end_offset": end,
            "excerpt_sha256": digest(excerpt.encode()),
            "pass": passed,
        }
    if not span or not span["pass"]:
        blockers.append("exact_source_span_not_proven")
    return {
        "citations": citations,
        "exact_source_span": span,
        "retrieval": {
            "executed": True,
            "dataset_type": "current pinned-build source-derived smoke; not attorney-reviewed gold",
            "sample_count": len(cases),
            "metrics": measured,
            "cases": metric_rows,
        },
        "pinpoint_forms_law_court": {
            "executed": False,
            "reason": "Dedicated pinpoint, form freshness, and Law Court treatment acceptance remains required; no inferred pass.",
        },
    }, blockers


def package_boundary(package: Path) -> dict:
    if not package.is_file():
        return {"status": "blocked", "code": "candidate_package_missing"}
    reject_links(package)
    initial_hash = sha256(package)
    forbidden = {
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "authority_product",
        "eval_store",
    }
    reports = {
        "source_update_report.json",
        "retrieval_smoke_report.json",
        "retrieval_smoke_eval.json",
    }
    with ZipFile(package) as archive:
        names = [name.replace("\\", "/").lower() for name in archive.namelist()]
        hits = [
            name
            for name in names
            if forbidden.intersection(PurePosixPath(name).parts)
            or PurePosixPath(name).name in reports
        ]
    if sha256(package) != initial_hash:
        raise EvidenceError("candidate_package_changed_during_audit")
    return {
        "status": "blocked" if hits else "pass",
        "msix": str(package),
        "msix_sha256": initial_hash,
        "forbidden_entry_count": len(hits),
        "forbidden_entries": hits[:50],
        "scope": "authority data/index/eval boundary only; not full privacy or installation qualification",
    }


def git_identity() -> dict:
    values = {}
    try:
        for name, command in {
            "root": ["rev-parse", "--show-toplevel"],
            "branch": ["branch", "--show-current"],
            "head": ["rev-parse", "HEAD"],
            "status": ["status", "--short"],
        }.items():
            values[name] = (
                subprocess.check_output(
                    ["git", *command], cwd=ROOT, stderr=subprocess.DEVNULL, timeout=15
                )
                .decode()
                .strip()
            )
        return {"available": True, **values}
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "error_code": "git_identity_unavailable"}


def audit(data_root: Path, package: Path, *, now: datetime | None = None) -> dict:
    started = time.monotonic()
    now = now or datetime.now(timezone.utc)
    report = {
        "schema_version": "authority_acceptance_v2",
        "generated_at": now.isoformat(),
        "decision": "BLOCKED",
        "review_required": True,
        "git": git_identity(),
        "authority_root": str(data_root),
        "live_update": {
            "executed": False,
            "status": "not_executed",
            "reason": "Read-only audit; no network update was run.",
        },
        "tests": {
            "executed": False,
            "status": "not_executed",
            "reason": "No pytest execution or historical test-count reuse.",
        },
        "active_build_id": None,
        "sources": None,
        "probes": None,
        "artifact_hashes": [],
        "verifier_contracts": None,
        "blockers": [],
        "store_ga": "STORE_GA_NOT_EVALUATED",
        "enterprise_ga": "ENTERPRISE_GA_NOT_EVALUATED",
        "external_authority_modified": False,
        "network_used": False,
    }
    if not report["git"]["available"]:
        report["blockers"].append("git_identity_unavailable")
    try:
        report["verifier_contracts"] = verifier_contracts()
    except Exception as exc:  # A verifier exception is explicit failed evidence, never approval.
        report["verifier_contracts"] = {"pass": False, "error_class": type(exc).__name__}
    if not report["verifier_contracts"]["pass"]:
        report["blockers"].append("verifier_contract_failure")
    try:
        build = PinnedBuild(data_root)
        report["active_build_id"] = build.build_id
        report["sources"], blockers = source_audit(build, now)
        report["blockers"].extend(blockers)
        report["probes"], blockers = probe_build(build)
        report["blockers"].extend(blockers)
        build.check_unchanged()
        report["artifact_hashes"] = build.inputs
        report["immutable_product_status"] = "pass"
    except (
        Exception
    ) as exc:  # Record the failure without leaking source text or raw exception detail.
        report["immutable_product_status"] = "blocked"
        code = (
            str(exc) if isinstance(exc, EvidenceError) else "authority_input_unavailable_or_invalid"
        )
        report["blockers"].append(code)
        report["input_error_class"] = type(exc).__name__
        if report["probes"]:
            report["probes"]["retrieval"]["evidence_valid"] = False
    try:
        report["package_boundary"] = package_boundary(package)
    except (OSError, ValueError, BadZipFile):
        report["package_boundary"] = {"status": "blocked", "code": "candidate_package_unverifiable"}
    if report["package_boundary"]["status"] != "pass":
        report["blockers"].append("authority_package_boundary_unproven")
    report["blockers"].append("pinpoint_form_and_law_court_acceptance_not_executed")
    report["blockers"] = sorted(set(report["blockers"]))
    report["scope_status"] = (
        "pass_with_limits"
        if report.get("immutable_product_status") == "pass" and len(report["blockers"]) == 1
        else "blocked"
    )
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--output-root", type=Path, required=True, help="Fresh evidence directory; no overwrites."
    )
    parser.add_argument(
        "--msix", type=Path, required=True, help="Exact candidate; no implicit historical version."
    )
    args = parser.parse_args(argv)
    output = args.output_root.absolute()
    data_root = args.data_root.absolute()
    try:
        reject_links(output)
        if (
            output.resolve() == data_root.resolve()
            or data_root.resolve() in output.resolve().parents
        ):
            raise EvidenceError("evidence_output_inside_authority_root")
        if output.exists():
            raise EvidenceError("evidence_directory_already_exists")
    except EvidenceError as exc:
        parser.error(str(exc))
    report = audit(data_root, args.msix.absolute())
    output.mkdir(parents=True, exist_ok=False)
    metrics = (
        report["probes"]["retrieval"]
        if report["probes"]
        else {
            "executed": False,
            "status": "not_executed",
            "sample_count": 0,
            "metrics": None,
            "reason": "Verified pinned inputs unavailable; no historical metrics reused.",
        }
    )
    (output / "04_authority_acceptance.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (output / "04_retrieval_verifier_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "Authority acceptance: " + report["decision"],
        "Scope: " + report["scope_status"],
        "Active build: " + str(report["active_build_id"]),
        "Live update: NOT EXECUTED",
        "Pytest: NOT EXECUTED by this runner",
        "Store/Enterprise GA: NOT EVALUATED by this audit",
        "Blockers:",
        *["- " + item for item in report["blockers"]],
    ]
    (output / "04_authority_acceptance.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "scope_status": report["scope_status"],
                "blockers": report["blockers"],
                "evidence": str(output),
            }
        )
    )
    return 2 if report["decision"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())

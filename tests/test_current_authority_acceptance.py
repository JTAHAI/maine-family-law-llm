"""Fictional audit-tool tests. No live authority or legal approval is asserted."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

from legal.production import AuthorityProductPublisher
from legal.retrieval.models import RetrievalDocument
from legal.verifiers import SourceAuthorityIndex
from test_v55_immutable_authority_product import _fixture_data_root

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "current_authority_acceptance", ROOT / "scripts/run-ga-authority-acceptance.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
NOW = datetime(2026, 8, 28, tzinfo=timezone.utc)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def candidate(tmp_path):
    path = tmp_path / "fictional-boundary-only.msix"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "_internal/src/legal/authority_store/code.py", "# source code, not authority data"
        )
    return path


@pytest.fixture
def external(tmp_path):
    root = _fixture_data_root(tmp_path)
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "statute-19a-1653")
    write_json(root / "authority_layer/citation_index.json", index.to_rows())
    document = RetrievalDocument(
        source_id="statute-19a-1653",
        document_id="statute-19a-1653",
        title="Fictional statute fixture",
        text="Best interest factors.",
        citation="19-A M.R.S. § 1653",
        source_class="statute_section",
        authority_status="verified_official_maine",
        freshness_status="fresh",
    )
    (root / "embedding_store/hybrid/retrieval_documents.jsonl").write_text(
        json.dumps(document.to_dict()) + "\n"
    )
    result = AuthorityProductPublisher(data_root=root).publish(product_version="fictional-test")
    assert result.status == "pass"
    return root


def inventory(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_missing_build_writes_blocked_without_live_update_tests_or_metrics(tmp_path, candidate):
    output = tmp_path / "evidence"
    code = runner.main(
        [
            "--data-root",
            str(tmp_path / "absent"),
            "--msix",
            str(candidate),
            "--output-root",
            str(output),
        ]
    )
    report = json.loads((output / "04_authority_acceptance.json").read_text())
    metrics = json.loads((output / "04_retrieval_verifier_metrics.json").read_text())
    assert code == 2 and report["decision"] == "BLOCKED"
    assert report["live_update"]["executed"] is False
    assert report["tests"]["executed"] is False
    assert "passed" not in report["tests"]
    assert report["sources"] is None and report["active_build_id"] is None
    assert metrics["executed"] is False and metrics["metrics"] is None
    assert report["git"]["available"] is True and report["git"]["head"]


def test_pinned_artifacts_not_mutable_ingest_or_cached_scores(external, candidate):
    (external / "official_authority_store/source_manifest.json").write_text("MUTABLE-CANARY")
    (external / "embedding_store/hybrid/retrieval_documents.jsonl").write_text("MUTABLE-CANARY")
    write_json(
        external / "official_authority_store/ingest_run_report.json",
        {"ingested_count": 1000000, "failed_count": 0},
    )
    write_json(
        external / "eval_store/retrieval_smoke_eval.json",
        {"case_count": 99999, "metrics": {"recall_at_20": 999}},
    )
    before = inventory(external)
    result = runner.audit(external, candidate, now=NOW)
    assert inventory(external) == before
    assert result["immutable_product_status"] == "pass"
    assert result["sources"]["total"] == 1
    measured = result["probes"]["retrieval"]
    assert measured["executed"] and 0 < measured["sample_count"] < 25
    assert 0 <= measured["metrics"]["recall_at_20"] <= 1
    assert "not attorney-reviewed gold" in measured["dataset_type"]
    assert "MUTABLE-CANARY" not in json.dumps(result)
    assert result["probes"]["exact_source_span"]["pass"]
    assert result["decision"] == "BLOCKED"  # The tiny fixture does not satisfy production coverage.
    assert "source_policy_minimums_not_met" in result["blockers"]
    assert result["package_boundary"]["status"] == "pass"


def test_contract_fixtures_are_labeled_and_all_observed_states_match():
    result = runner.verifier_contracts()
    assert "fictional" in result["basis"]
    assert result["pass"], result
    assert len(result["quotes"]) == 4 and len(result["claims"]) == 7
    assert all(row["review_required"] for row in result["quotes"])
    assert not next(row for row in result["claims"] if row["expected"] == "stale")["supported"]


def test_tampered_immutable_artifact_fails_before_probes(external, candidate):
    build = runner.PinnedBuild(external)
    path = build.checked_path(build.role_row("source_manifest"))
    path.write_bytes(path.read_bytes() + b" ")
    result = runner.audit(external, candidate, now=NOW)
    assert result["probes"] is None
    assert "immutable_product_verification_failed" in result["blockers"]


def test_pointer_changes_invalidate_measured_results(external, candidate, monkeypatch):
    original = runner.probe_build

    def switch(build):
        result = original(build)
        build.pointer_path.write_bytes(build.pointer_bytes + b" ")
        return result

    monkeypatch.setattr(runner, "probe_build", switch)
    result = runner.audit(external, candidate, now=NOW)
    assert "active_build_changed_during_audit" in result["blockers"]
    assert result["probes"]["retrieval"]["evidence_valid"] is False
    assert result["scope_status"] == "blocked"


@pytest.mark.parametrize(
    "relative",
    [
        "official_authority_store/source_manifest.json",
        "../outside.json",
        "authority_product/builds/000000000000000000000000/a.json",
        "C:/private.txt",
        "a\\..\\private.txt",
    ],
)
def test_declared_artifact_cannot_escape_active_build(external, relative):
    build = runner.PinnedBuild(external)
    with pytest.raises(runner.EvidenceError, match="artifact_outside_pinned_build"):
        build.checked_path({"relative_path": relative})


@pytest.mark.parametrize(
    "payload", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b"not-json"]
)
def test_strict_json_rejects_ambiguous_reports(payload):
    with pytest.raises(runner.EvidenceError):
        runner.strict_json(payload)


def test_ambiguous_role_is_not_first_match_wins(external):
    build = runner.PinnedBuild(external)
    build.rows.append(dict(build.role_row("source_manifest")))
    with pytest.raises(runner.EvidenceError, match="missing_or_ambiguous"):
        build.artifact("source_manifest")


def test_expired_timestamp_not_promoted_by_fresh_label(external):
    report, blockers = runner.source_audit(
        runner.PinnedBuild(external), datetime(2028, 1, 1, tzinfo=timezone.utc)
    )
    assert report["rows"][0]["reported_freshness"] == "fresh"
    assert report["rows"][0]["age_days"] > report["age_limit_days"]
    assert "source_age_outside_policy" in blockers


def test_future_timestamp_fails_closed(external):
    _, blockers = runner.source_audit(
        runner.PinnedBuild(external), datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    assert "source_age_outside_policy" in blockers


def test_missing_source_classes_and_citations_remain_blockers(external, candidate):
    result = runner.audit(external, candidate, now=NOW)
    assert result["sources"]["total"] == 1
    assert {
        "citation_missing_or_without_source:rule",
        "citation_missing_or_without_source:case",
        "citation_missing_or_without_source:form",
    } <= set(result["blockers"])
    assert next(row for row in result["probes"]["citations"] if row["kind"] == "fake")["pass"]


@pytest.mark.parametrize(
    "member",
    [
        "_internal/authority_product/ACTIVE_BUILD.json",
        "embedding_store/index.json",
        "eval_store/gold.json",
        "_internal/source_update_report.json",
        "parsed_authority_store/private.json",
    ],
)
def test_authority_payload_not_allowed_in_candidate(tmp_path, member):
    package = tmp_path / "fictional.msix"
    with ZipFile(package, "w") as archive:
        archive.writestr(member, "{}")
    result = runner.package_boundary(package)
    assert result["status"] == "blocked" and result["forbidden_entry_count"] == 1


def test_no_overwrite_of_prior_evidence(tmp_path, candidate):
    output = tmp_path / "evidence"
    output.mkdir()
    marker = output / "prior.json"
    marker.write_text("preserved")
    with pytest.raises(SystemExit) as exc:
        runner.main(
            [
                "--data-root",
                str(tmp_path / "empty"),
                "--msix",
                str(candidate),
                "--output-root",
                str(output),
            ]
        )
    assert exc.value.code == 2 and marker.read_text() == "preserved"


def test_cannot_write_evidence_into_external_store(external, candidate):
    before = inventory(external)
    with pytest.raises(SystemExit):
        runner.main(
            [
                "--data-root",
                str(external),
                "--msix",
                str(candidate),
                "--output-root",
                str(external / "evidence"),
            ]
        )
    assert inventory(external) == before


@pytest.mark.parametrize("target", ["verifier_contracts", "probe_build"])
def test_verifier_and_retrieval_exceptions_block_without_raw_detail(
    external, candidate, monkeypatch, target
):
    def broken(*args):
        raise RuntimeError("PRIVATE-CANARY C:/sensitive.txt")

    monkeypatch.setattr(runner, target, broken)
    result = runner.audit(external, candidate, now=NOW)
    assert result["decision"] == "BLOCKED"
    assert "PRIVATE-CANARY" not in json.dumps(result) and "sensitive.txt" not in json.dumps(result)
    assert (
        "verifier_contract_failure" in result["blockers"]
        or result["immutable_product_status"] == "blocked"
    )


def test_git_identity_failure_not_hardcoded_success(tmp_path, candidate, monkeypatch):
    def absent(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(runner.subprocess, "check_output", absent)
    result = runner.audit(tmp_path / "missing", candidate)
    assert result["git"]["available"] is False and "git_identity_unavailable" in result["blockers"]


def test_cli_works_with_selected_interpreter_and_fresh_output(tmp_path, candidate):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run-ga-authority-acceptance.py"),
            "--data-root",
            str(tmp_path / "missing"),
            "--msix",
            str(candidate),
            "--output-root",
            str(tmp_path / "report"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["decision"] == "BLOCKED"

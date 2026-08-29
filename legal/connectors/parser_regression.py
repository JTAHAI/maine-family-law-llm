"""Versioned, offline parser-regression corpus for authority connectors.

The corpus deliberately contains synthetic page *shapes*, not admitted legal
authority.  It protects parser behavior against markup changes and malformed
downloads without turning test fixtures into a research corpus or current-law
source.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.connectors.maine_forms import parse_forms_index
from legal.connectors.maine_revisor import parse_revisor_section_html, parse_revisor_title_index
from legal.connectors.maine_rules import parse_rules_text
from legal.connectors.maine_sjc_opinions import parse_law_court_opinion_index


_SUPPORTED_PARSERS = {
    "maine_revisor_title_index",
    "maine_revisor_section",
    "maine_forms_index",
    "maine_rules_pdf",
    "maine_law_court_opinion_index",
}


@dataclass(frozen=True)
class ParserRegressionFixtureResult:
    fixture_id: str
    fixture_version: str
    scenario: str
    parser_name: str
    content_sha256: str | None
    status: str
    expected_status: str
    extracted_count: int
    expected_minimum_extracted_count: int
    checks: list[str]
    blockers: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "scenario": self.scenario,
            "parser_name": self.parser_name,
            "fixture_sha256": self.content_sha256,
            "status": self.status,
            "expected_status": self.expected_status,
            "extracted_count": self.extracted_count,
            "expected_minimum_extracted_count": self.expected_minimum_extracted_count,
            "checks": self.checks,
            "blockers": self.blockers,
            "review_required": True,
            "source_lane": "synthetic_parser_fixture",
            "can_support_legal_claim": False,
        }


class ParserRegressionCorpus:
    """Run a local, content-hash-bound parser fixture corpus.

    No network client is imported or used.  The runner rejects missing,
    symlinked, or hash-mismatched fixture files before handing any text to a
    parser.  A malformed-download scenario is intentionally quarantined rather
    than being treated as a best-effort authority document.
    """

    schema_version = "parser_regression_corpus_v1"

    def __init__(self, fixture_root: str | Path) -> None:
        self.fixture_root = Path(fixture_root).expanduser().resolve()
        self.manifest_path = self.fixture_root / "manifest.json"

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.is_symlink() or not self.manifest_path.is_file():
            raise ValueError("parser_regression_manifest_unavailable")
        try:
            loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("parser_regression_manifest_invalid") from exc
        if not isinstance(loaded, dict) or not isinstance(loaded.get("fixtures"), list):
            raise ValueError("parser_regression_manifest_invalid")
        if loaded.get("schema_version") != self.schema_version:
            raise ValueError("parser_regression_manifest_schema_invalid")
        return loaded

    def _fixture_path(self, fixture: dict[str, Any]) -> Path:
        relative = str(fixture.get("content_file") or "")
        candidate = (self.fixture_root / relative).resolve()
        try:
            candidate.relative_to(self.fixture_root)
        except ValueError as exc:
            raise ValueError("parser_regression_fixture_path_escape") from exc
        return candidate

    @staticmethod
    def _read_fixture(path: Path, expected_hash: str) -> tuple[bytes | None, list[str]]:
        if path.is_symlink() or not path.is_file():
            return None, ["fixture_file_missing_or_symlinked"]
        content = path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if not expected_hash or actual_hash != expected_hash:
            return None, ["fixture_content_hash_mismatch"]
        return content, []

    @staticmethod
    def _fixture_url(fixture: dict[str, Any]) -> str:
        # This marker is intentionally not an official source URL.  It keeps
        # parser outputs deterministic while preventing a synthetic page shape
        # from being displayed as a research source.
        return f"https://fixture.invalid/parser-regression/{fixture.get('fixture_id', 'unknown')}"

    def _run_parser(self, fixture: dict[str, Any], content: bytes) -> tuple[str, int, dict[str, Any], list[str]]:
        fixture_id = str(fixture.get("fixture_id") or "")
        parser_name = str(fixture.get("parser_name") or "")
        if fixture.get("scenario") == "malformed_download":
            return "quarantined", 0, {}, ["malformed_download_quarantined"]
        if parser_name not in _SUPPORTED_PARSERS:
            return "blocked", 0, {}, ["parser_not_admitted_to_regression_corpus"]
        text = content.decode("utf-8", errors="replace")
        source_id = f"fixture-{fixture_id}"
        url = self._fixture_url(fixture)
        if parser_name == "maine_revisor_title_index":
            _document, audit = parse_revisor_title_index(text, source_id=source_id, url=url)
        elif parser_name == "maine_revisor_section":
            _document, audit = parse_revisor_section_html(text, source_id=source_id, url=url)
        elif parser_name == "maine_forms_index":
            _documents, audit = parse_forms_index(text, source_id=source_id, url=url)
        elif parser_name == "maine_rules_pdf":
            _documents, audit = parse_rules_text(text, source_id=source_id, url=url)
        else:
            _documents, audit = parse_law_court_opinion_index(text, source_id=source_id, url=url)
        return audit.status, int(audit.extracted_count), dict(audit.metadata or {}), list(audit.warnings or [])

    def run_fixture(self, fixture_id: str) -> dict[str, Any]:
        manifest = self._load_manifest()
        fixtures = [item for item in manifest["fixtures"] if isinstance(item, dict) and str(item.get("fixture_id") or "") == fixture_id]
        if len(fixtures) != 1:
            return {
                "status": "blocked",
                "fixture_id": fixture_id,
                "blockers": ["parser_regression_fixture_not_found"],
                "review_required": True,
                "can_support_legal_claim": False,
            }
        return self._run_fixture_definition(fixtures[0]).as_dict()

    def _run_fixture_definition(self, fixture: dict[str, Any]) -> ParserRegressionFixtureResult:
        fixture_id = str(fixture.get("fixture_id") or "")
        version = str(fixture.get("fixture_version") or "")
        scenario = str(fixture.get("scenario") or "")
        parser_name = str(fixture.get("parser_name") or "")
        expected = fixture.get("expected") if isinstance(fixture.get("expected"), dict) else {}
        expected_status = str(expected.get("status") or "blocked")
        expected_minimum = int(expected.get("minimum_extracted_count") or 0)
        blockers: list[str] = []
        checks: list[str] = []
        try:
            path = self._fixture_path(fixture)
        except ValueError as exc:
            return ParserRegressionFixtureResult(
                fixture_id, version, scenario, parser_name, None, "blocked", expected_status, 0, expected_minimum, checks, [str(exc)]
            )
        content, read_blockers = self._read_fixture(path, str(fixture.get("content_sha256") or ""))
        if read_blockers:
            return ParserRegressionFixtureResult(
                fixture_id, version, scenario, parser_name, None, "blocked", expected_status, 0, expected_minimum, checks, read_blockers
            )
        assert content is not None
        content_sha256 = hashlib.sha256(content).hexdigest()
        observed_status, extracted_count, metadata, parser_warnings = self._run_parser(fixture, content)
        if observed_status == expected_status:
            checks.append("expected_status_matched")
        else:
            blockers.append("parser_status_regression")
        if extracted_count >= expected_minimum:
            checks.append("minimum_extracted_count_met")
        else:
            blockers.append("parser_extraction_count_regression")
        for key, expected_value in (expected.get("required_metadata") or {}).items():
            if metadata.get(key) == expected_value:
                checks.append(f"required_metadata:{key}")
            else:
                blockers.append(f"parser_metadata_regression:{key}")
        if parser_warnings:
            checks.append("parser_warnings_recorded")
            checks.extend(parser_warnings)
        status = "passed" if not blockers else "failed"
        return ParserRegressionFixtureResult(
            fixture_id,
            version,
            scenario,
            parser_name,
            content_sha256,
            status,
            expected_status,
            extracted_count,
            expected_minimum,
            checks,
            blockers,
        )

    def run(self) -> dict[str, Any]:
        manifest = self._load_manifest()
        results = [self._run_fixture_definition(item).as_dict() for item in manifest["fixtures"] if isinstance(item, dict)]
        passed = [item for item in results if item["status"] == "passed"]
        failed = [item for item in results if item["status"] != "passed"]
        return {
            "schema_version": self.schema_version,
            "corpus_id": str(manifest.get("corpus_id") or "parser-regression"),
            "corpus_version": str(manifest.get("corpus_version") or ""),
            "fixture_count": len(results),
            "passed_count": len(passed),
            "failed_count": len(failed),
            "fixtures": results,
            "blockers": sorted({blocker for item in failed for blocker in item.get("blockers", [])}),
            "status": "passed" if not failed else "failed",
            "review_required": True,
            "network_used": False,
            "persistent_state_changed": False,
            "corpus_is_legal_authority": False,
            "can_support_legal_claim": False,
            "notice": (
                "These are versioned synthetic parser fixtures. They test parser behavior only and are not admitted "
                "authority, a source update, a current-law determination, or a legal conclusion."
            ),
        }

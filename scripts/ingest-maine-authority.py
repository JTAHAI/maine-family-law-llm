#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.connectors import OfficialAuthorityIngestor, OfficialSourceFetcher, load_official_source_targets
from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.official_source_catalog import load_source_targets_from_file
from legal.data_boundaries import StoreName, default_external_data_root, ensure_external_authority_root


def _merge_manifest_records(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge authority manifest records while preserving first-seen order.

    Second-wave direct authority ingestion must not erase first-wave index
    snapshots.  Source IDs are stable per source URL/class, so newer records for
    the same source ID replace older records, while unique first-wave and
    follow-up records remain in one manifest for downstream parsing/indexing.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []
    for index, record in enumerate(existing + incoming):
        if not isinstance(record, dict):
            continue
        key = str(
            record.get("source_id")
            or record.get("snapshot_path")
            or record.get("source_url_or_path")
            or f"manifest-row-{index}"
        )
        if key not in merged:
            order.append(key)
        merged[key] = record
    return [merged[key] for key in order]


_FIXTURE_BY_SOURCE_CLASS = {
    "statute_title_index": "mrs-title-19a-domestic-relations.html",
    "statute_title_pdf": "mrs-title-19a-domestic-relations.html",
    "court_rules_index": "maine-rules-civil-family-division.html",
    "court_policy_index": "maine-rules-civil-family-division.html",
    "court_forms_index": "maine-court-forms-family.html",
    "law_court_opinion_index": "maine-judicial-branch-appeals.html",
    "law_court_opinion_file": "maine-judicial-branch-appeals.html",
    "child_support_guidance": "maine-child-support-services.html",
    "secondary": "sample-secondary-family-law-overview.html",
}


class _FixtureFetcher:
    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        fixture_name = _FIXTURE_BY_SOURCE_CLASS.get(target.source_class)
        if not fixture_name:
            raise FileNotFoundError(f"fixture missing for source class {target.source_class}")
        path = self.fixtures_dir / fixture_name
        if not path.is_file():
            raise FileNotFoundError(path)
        content = path.read_bytes()
        content_type = "application/pdf" if target.expected_content_type.lower() == "application/pdf" else "text/html"
        return RetrievedSource(
            target=target,
            content=content,
            retrieved_at=datetime.now(timezone.utc),
            content_type=content_type,
            status_code=200,
            final_url=target.url,
            fetch_metadata={
                "fixture_mode": True,
                "fixture_name": fixture_name,
                "byte_count": len(content),
                "retry_count": 0,
                "robots_policy_result": "fixture_mode",
            },
        )


def _human_report(result: dict[str, object]) -> str:
    lines = [
        f"Status: {result.get('status', 'unknown')}",
        f"Targets: {result.get('target_count', 0)}",
        f"Ingested: {result.get('ingested_count', 0)}",
        f"Failed: {result.get('failed_count', 0)}",
        f"Manifest: {result.get('manifest_path', '')}",
        f"Failure report: {result.get('failure_report_path', '')}",
    ]
    failures = result.get("failures") or []
    if isinstance(failures, list) and failures:
        lines.append("Failures:")
        for failure in failures:
            if isinstance(failure, dict):
                lines.append(f"  - {failure.get('target_id', 'unknown')}: {failure.get('failure_code', 'unknown')} - {failure.get('message', '')}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official Maine authority snapshots.")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=default_external_data_root(ROOT),
        help="External data root. Defaults outside the source repository.",
    )
    parser.add_argument(
        "--target-id",
        action="append",
        default=[],
        help="Limit ingestion to one or more target IDs from the selected source target catalog.",
    )
    parser.add_argument(
        "--target-catalog",
        type=Path,
        default=None,
        help="Optional JSON source-target catalog, for example official_authority_store/derived_authority_targets.json.",
    )
    parser.add_argument(
        "--source-class",
        action="append",
        default=[],
        help="Limit ingestion to one or more source_class values from the selected catalog.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=1.5)
    parser.add_argument(
        "--ignore-robots-txt",
        action="store_true",
        help="Do not check robots.txt. Intended only for controlled/internal mirrors.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Abort on first failed target instead of writing failed_sources.json and continuing.",
    )
    parser.add_argument(
        "--strict-content-type",
        action="store_true",
        help="Fail targets whose response content type/body does not match expected_content_type.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate target catalog and external data root without network fetches or snapshots.",
    )
    parser.add_argument(
        "--fixture-mode",
        action="store_true",
        help="Use committed offline fixtures instead of live network fetches.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Refresh snapshots even when an existing manifest is present.",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="Emit the machine-readable summary JSON (default on stdout).",
    )
    parser.add_argument(
        "--human-report",
        action="store_true",
        help="Emit a readable report after the JSON summary.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Optional cap for smoke runs. Production builds should omit this.",
    )
    parser.add_argument(
        "--append-existing-manifest",
        action="store_true",
        help=(
            "Merge newly ingested sources into an existing official_authority_store/source_manifest.json "
            "instead of replacing it. Use for second-wave direct authority target ingests."
        ),
    )
    args = parser.parse_args()

    project_root = ROOT.resolve()
    try:
        data_root = ensure_external_authority_root(args.data_root, project_root=project_root)
    except ValueError as exc:
        raise SystemExit(
            "Refusing to ingest official authority into the source repository: "
            f"{exc}"
        ) from exc

    targets = load_source_targets_from_file(args.target_catalog) if args.target_catalog else load_official_source_targets()
    if args.target_id:
        wanted = set(args.target_id)
        targets = [target for target in targets if target.target_id in wanted]
        missing = wanted - {target.target_id for target in targets}
        if missing:
            raise SystemExit(f"Unknown target IDs: {sorted(missing)}")
    if args.source_class:
        wanted_classes = {value.strip() for value in args.source_class if value.strip()}
        targets = [target for target in targets if target.source_class in wanted_classes]
    if args.max_targets is not None:
        targets = targets[: max(0, args.max_targets)]

    target_problems = {target.target_id: target.validate() for target in targets if target.validate()}
    if args.dry_run:
        result = {
            "status": "pass" if not target_problems else "blocked",
            "mode": "dry_run",
            "target_count": len(targets),
            "target_ids": [target.target_id for target in targets],
            "source_classes": sorted({target.source_class for target in targets}),
            "target_problems": target_problems,
            "data_root": str(data_root),
            "official_store": str(data_root / StoreName.OFFICIAL_AUTHORITY.value),
            "fixture_mode": bool(args.fixture_mode),
            "force_refresh": bool(args.force_refresh),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not target_problems else 1
    if target_problems:
        raise SystemExit(f"Invalid source targets: {target_problems}")

    official_store = data_root / StoreName.OFFICIAL_AUTHORITY.value
    fetcher = _FixtureFetcher(ROOT / "data" / "fixtures") if args.fixture_mode else OfficialSourceFetcher(
        timeout_seconds=args.timeout,
        min_delay_seconds=args.delay,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff,
        respect_robots_txt=not args.ignore_robots_txt,
        strict_content_type=args.strict_content_type,
    )
    ingestor = OfficialAuthorityIngestor(fetcher=fetcher, snapshot_base_dir=official_store)
    ingested = ingestor.ingest_all(targets, continue_on_error=not args.fail_fast)
    manifest_records = [item.to_dict() for item in ingested]
    prior_manifest_count = 0
    if args.append_existing_manifest:
        manifest_path_candidate = official_store / "source_manifest.json"
        if manifest_path_candidate.exists():
            loaded = json.loads(manifest_path_candidate.read_text(encoding="utf-8"))
            if not isinstance(loaded, list):
                raise SystemExit("Existing source_manifest.json must be a JSON array before append.")
            prior_manifest_count = len(loaded)
            manifest_records = _merge_manifest_records(loaded, manifest_records)
    manifest_path = ingestor.write_manifest(manifest_records)
    failure_report_path = ingestor.write_failure_report()
    run_report_path = ingestor.write_ingest_run_report(ingested=ingested, manifest_path=manifest_path)

    result = {
        "status": "pass" if not ingestor.failed else "partial",
        "target_count": len(targets),
        "ingested_count": len(ingested),
        "failed_count": len(ingestor.failed),
        "target_ids": [target.target_id for target in targets],
        "source_classes": sorted({target.source_class for target in targets}),
        "fixture_mode": bool(args.fixture_mode),
        "force_refresh": bool(args.force_refresh),
        "manifest_path": str(manifest_path),
        "prior_manifest_count": prior_manifest_count,
        "manifest_record_count": len(manifest_records),
        "append_existing_manifest": bool(args.append_existing_manifest),
        "failure_report_path": str(failure_report_path),
        "run_report_path": str(run_report_path),
        "official_store": str(official_store),
        "sources": [item.to_dict() for item in ingested],
        "failures": [failure.to_dict() for failure in ingestor.failed],
    }
    if args.json_summary or not args.human_report:
        print(json.dumps(result, indent=2, sort_keys=True))
    if args.human_report:
        print(_human_report(result))
    return 0 if not ingestor.failed else 2


if __name__ == "__main__":
    raise SystemExit(main())

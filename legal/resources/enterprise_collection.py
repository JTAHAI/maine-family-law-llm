from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.data_boundaries.storage_layout import is_inside_project_repo


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_enterprise_resource_catalog(project_root: str | Path = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    return json.loads(
        (root / "configs" / "maine_enterprise_resource_catalog.json").read_text(encoding="utf-8")
    )


def sanitize_filename(value: str, *, default: str = "resource") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-_")
    return cleaned[:160] or default


def extension_for(url: str, content_type: str | None) -> str:
    path_suffix = Path(urllib.parse.urlparse(url).path).suffix
    if path_suffix and len(path_suffix) <= 8:
        return path_suffix
    if content_type:
        ctype = content_type.split(";", 1)[0].strip().lower()
        if ctype == "text/html":
            return ".html"
        if ctype == "application/pdf":
            return ".pdf"
        guessed = mimetypes.guess_extension(ctype)
        if guessed:
            return guessed
    return ".bin"


@dataclass(frozen=True)
class ResourceFetchAttempt:
    attempt_number: int
    status: str
    message: str
    elapsed_seconds: float = 0.0
    status_code: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "status": self.status,
            "message": self.message,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "status_code": self.status_code,
        }


@dataclass(frozen=True)
class EnterpriseResourceRecord:
    resource_id: str
    source_class: str
    jurisdiction: str
    authority_level: str
    title: str
    url: str
    required_for_enterprise: bool
    status: str
    snapshot_path: str | None = None
    sha256: str | None = None
    bytes: int = 0
    content_type: str | None = None
    retrieved_at: str | None = None
    parser_name: str | None = None
    expected_content_type: str | None = None
    final_url: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    attempts: list[ResourceFetchAttempt] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "source_class": self.source_class,
            "jurisdiction": self.jurisdiction,
            "authority_level": self.authority_level,
            "title": self.title,
            "url": self.url,
            "required_for_enterprise": self.required_for_enterprise,
            "status": self.status,
            "snapshot_path": self.snapshot_path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "content_type": self.content_type,
            "retrieved_at": self.retrieved_at,
            "parser_name": self.parser_name,
            "expected_content_type": self.expected_content_type,
            "final_url": self.final_url,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "attempts": [attempt.as_dict() for attempt in self.attempts],
        }


@dataclass(frozen=True)
class SourceClassCoverage:
    source_class: str
    required: int
    successful: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class,
            "required": self.required,
            "successful": self.successful,
            "status": self.status,
        }


@dataclass
class EnterpriseResourceReport:
    status: str
    production_ready: bool
    catalog_version: str
    data_root: str
    resource_root: str
    manifest_path: str
    failed_resources_path: str
    collection_report_path: str
    total_resources: int
    successful_resources: int
    failed_resources: int
    required_failures: int
    coverage: list[SourceClassCoverage]
    blockers: list[str]
    dry_run: bool = False
    generated_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "production_ready": self.production_ready,
            "dry_run": self.dry_run,
            "catalog_version": self.catalog_version,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "resource_root": self.resource_root,
            "manifest_path": self.manifest_path,
            "failed_resources_path": self.failed_resources_path,
            "collection_report_path": self.collection_report_path,
            "total_resources": self.total_resources,
            "successful_resources": self.successful_resources,
            "failed_resources": self.failed_resources,
            "required_failures": self.required_failures,
            "coverage": [item.as_dict() for item in self.coverage],
            "blockers": sorted(set(self.blockers)),
        }


class EnterpriseResourceCollector:
    """Collect official/review resources into an external local data root.

    This collector is intentionally separate from source packaging. It downloads
    raw research/legal resources to ``<data-root>/research_resources`` and emits
    manifest/evidence JSON files that can later feed parsers, index builders,
    and enterprise readiness gates.
    """

    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path,
        catalog: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        delay_seconds: float | None = None,
        max_retries: int | None = None,
        respect_robots_txt: bool | None = None,
        user_agent: str | None = None,
        allow_repo_data_root: bool = False,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.catalog = catalog or load_enterprise_resource_catalog(self.project_root)
        network_policy = self.catalog.get("network_policy", {})
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else network_policy.get("default_timeout_seconds", 45)
        )
        self.delay_seconds = float(
            delay_seconds if delay_seconds is not None else network_policy.get("default_delay_seconds", 1.0)
        )
        self.max_retries = int(
            max_retries if max_retries is not None else network_policy.get("default_max_retries", 3)
        )
        self.respect_robots_txt = bool(
            respect_robots_txt
            if respect_robots_txt is not None
            else network_policy.get("respect_robots_txt", True)
        )
        self.user_agent = str(
            user_agent or network_policy.get("user_agent", "MaineFamilyLawLLM-EnterpriseResourceCollector/1.0")
        )
        self.allow_repo_data_root = allow_repo_data_root
        self.resource_root = self.data_root / "research_resources"
        self.snapshot_root = self.resource_root / "snapshots"
        self.manifest_path = self.resource_root / "resource_manifest.json"
        self.failed_resources_path = self.resource_root / "failed_resources.json"
        self.collection_report_path = self.resource_root / "collection_report.json"
        self._last_fetch_by_host: dict[str, float] = {}
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _validate_external_data_root(self) -> None:
        if not self.allow_repo_data_root and is_inside_project_repo(self.data_root, self.project_root):
            raise ValueError(
                f"Refusing to collect enterprise resources inside source repo: {self.data_root}. "
                "Use an external data root such as C:\\dev\\ME_FM_LLM_data."
            )

    def _resources(self, *, resource_ids: set[str] | None = None, source_classes: set[str] | None = None) -> list[dict[str, Any]]:
        resources = [dict(item) for item in self.catalog.get("resources", []) if item.get("url")]
        if resource_ids:
            resources = [item for item in resources if str(item.get("resource_id")) in resource_ids]
        if source_classes:
            resources = [item for item in resources if str(item.get("source_class")) in source_classes]
        return resources

    def collect(
        self,
        *,
        resource_ids: Iterable[str] | None = None,
        source_classes: Iterable[str] | None = None,
        max_resources: int | None = None,
        dry_run: bool = False,
        continue_on_error: bool = True,
    ) -> EnterpriseResourceReport:
        self._validate_external_data_root()
        resource_id_set = set(resource_ids or []) or None
        source_class_set = set(source_classes or []) or None
        resources = self._resources(resource_ids=resource_id_set, source_classes=source_class_set)
        if max_resources is not None:
            resources = resources[: max(0, max_resources)]
        self.resource_root.mkdir(parents=True, exist_ok=True)
        records: list[EnterpriseResourceRecord] = []
        for resource in resources:
            if dry_run:
                records.append(self._planned_record(resource))
                continue
            record = self._fetch_resource(resource)
            records.append(record)
            if record.status == "failed" and not continue_on_error:
                break
        report = self._write_outputs(records, dry_run=dry_run)
        return report

    def _planned_record(self, resource: dict[str, Any]) -> EnterpriseResourceRecord:
        return EnterpriseResourceRecord(
            resource_id=str(resource.get("resource_id")),
            source_class=str(resource.get("source_class")),
            jurisdiction=str(resource.get("jurisdiction", "unknown")),
            authority_level=str(resource.get("authority_level", "unknown")),
            title=str(resource.get("title", resource.get("resource_id"))),
            url=str(resource.get("url")),
            required_for_enterprise=bool(resource.get("required_for_enterprise", False)),
            status="planned",
            parser_name=resource.get("parser_name"),
            expected_content_type=resource.get("expected_content_type"),
        )

    def _request_for(self, url: str, expected_content_type: str | None) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": expected_content_type or "*/*",
            },
        )

    def _robots_url(self, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))

    def _robots_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        robots_url = self._robots_url(url)
        if robots_url in self._robots_cache:
            return self._robots_cache[robots_url]
        parser = urllib.robotparser.RobotFileParser(robots_url)
        try:
            with urllib.request.urlopen(
                self._request_for(robots_url, "text/plain"), timeout=self.timeout_seconds
            ) as response:
                parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
        except Exception:
            parser.parse([])
        self._robots_cache[robots_url] = parser
        return parser

    def _rate_limit(self, url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        host = parsed.netloc.lower()
        last = self._last_fetch_by_host.get(host)
        if last is not None:
            remaining = self.delay_seconds - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_fetch_by_host[host] = time.monotonic()

    def _target_path(self, resource: dict[str, Any], content_type: str | None) -> Path:
        source_class = sanitize_filename(str(resource.get("source_class", "unknown")))
        resource_id = sanitize_filename(str(resource.get("resource_id", "resource")))
        ext = extension_for(str(resource.get("url")), content_type or resource.get("expected_content_type"))
        return self.snapshot_root / source_class / resource_id / f"snapshot{ext}"

    def _fetch_resource(self, resource: dict[str, Any]) -> EnterpriseResourceRecord:
        attempts: list[ResourceFetchAttempt] = []
        url = str(resource.get("url"))
        expected = resource.get("expected_content_type")
        if self.respect_robots_txt and not self._robots_parser(url).can_fetch(self.user_agent, url):
            return self._failure_record(resource, "robots_disallow", "robots.txt disallows this URL", attempts)
        last_message = "not attempted"
        for attempt_number in range(1, self.max_retries + 2):
            started = time.monotonic()
            try:
                self._rate_limit(url)
                request = self._request_for(url, expected)
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    content = response.read()
                    elapsed = time.monotonic() - started
                    content_type = response.headers.get("Content-Type")
                    status_code = getattr(response, "status", None)
                    attempts.append(
                        ResourceFetchAttempt(
                            attempt_number=attempt_number,
                            status="success",
                            message="fetched",
                            elapsed_seconds=elapsed,
                            status_code=status_code,
                        )
                    )
                    snapshot_path = self._target_path(resource, content_type)
                    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                    snapshot_path.write_bytes(content)
                    digest = hashlib.sha256(content).hexdigest()
                    return EnterpriseResourceRecord(
                        resource_id=str(resource.get("resource_id")),
                        source_class=str(resource.get("source_class")),
                        jurisdiction=str(resource.get("jurisdiction", "unknown")),
                        authority_level=str(resource.get("authority_level", "unknown")),
                        title=str(resource.get("title", resource.get("resource_id"))),
                        url=url,
                        required_for_enterprise=bool(resource.get("required_for_enterprise", False)),
                        status="downloaded",
                        snapshot_path=str(snapshot_path),
                        sha256=digest,
                        bytes=len(content),
                        content_type=content_type,
                        retrieved_at=utc_now_iso(),
                        parser_name=resource.get("parser_name"),
                        expected_content_type=expected,
                        final_url=response.geturl(),
                        attempts=attempts,
                    )
            except urllib.error.HTTPError as exc:
                elapsed = time.monotonic() - started
                last_message = f"HTTP {exc.code}: {exc.reason}"
                attempts.append(
                    ResourceFetchAttempt(
                        attempt_number=attempt_number,
                        status="http_error",
                        message=last_message,
                        elapsed_seconds=elapsed,
                        status_code=exc.code,
                    )
                )
                if 400 <= exc.code < 500 and exc.code not in {408, 425, 429}:
                    break
            except Exception as exc:
                elapsed = time.monotonic() - started
                last_message = f"{type(exc).__name__}: {exc}"
                attempts.append(
                    ResourceFetchAttempt(
                        attempt_number=attempt_number,
                        status="network_error",
                        message=last_message,
                        elapsed_seconds=elapsed,
                    )
                )
            if attempt_number <= self.max_retries:
                time.sleep(min(30.0, max(0.0, self.delay_seconds) * (attempt_number + 1)))
        return self._failure_record(resource, "fetch_failed", last_message, attempts)

    def _failure_record(
        self,
        resource: dict[str, Any],
        failure_code: str,
        failure_message: str,
        attempts: list[ResourceFetchAttempt],
    ) -> EnterpriseResourceRecord:
        return EnterpriseResourceRecord(
            resource_id=str(resource.get("resource_id")),
            source_class=str(resource.get("source_class")),
            jurisdiction=str(resource.get("jurisdiction", "unknown")),
            authority_level=str(resource.get("authority_level", "unknown")),
            title=str(resource.get("title", resource.get("resource_id"))),
            url=str(resource.get("url")),
            required_for_enterprise=bool(resource.get("required_for_enterprise", False)),
            status="failed",
            parser_name=resource.get("parser_name"),
            expected_content_type=resource.get("expected_content_type"),
            failure_code=failure_code,
            failure_message=failure_message,
            attempts=attempts,
        )

    def _coverage_for(self, records: list[EnterpriseResourceRecord]) -> list[SourceClassCoverage]:
        required_classes = self.catalog.get("required_source_classes", {})
        success_counts: dict[str, int] = {}
        for record in records:
            if record.status == "downloaded":
                success_counts[record.source_class] = success_counts.get(record.source_class, 0) + 1
        coverage: list[SourceClassCoverage] = []
        for source_class, required in sorted(required_classes.items()):
            successful = success_counts.get(source_class, 0)
            coverage.append(
                SourceClassCoverage(
                    source_class=source_class,
                    required=int(required),
                    successful=successful,
                    status="pass" if successful >= int(required) else "fail",
                )
            )
        return coverage

    def _write_outputs(self, records: list[EnterpriseResourceRecord], *, dry_run: bool) -> EnterpriseResourceReport:
        manifest = [record.as_dict() for record in records]
        failures = [record.as_dict() for record in records if record.status == "failed"]
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        self.failed_resources_path.write_text(json.dumps(failures, indent=2, sort_keys=True), encoding="utf-8")
        required_failures = sum(1 for record in records if record.required_for_enterprise and record.status == "failed")
        coverage = self._coverage_for(records)
        blockers: list[str] = []
        if dry_run:
            blockers.append("dry_run_no_resources_downloaded")
        if required_failures:
            blockers.append("required_resource_download_failures")
        for item in coverage:
            if item.status != "pass" and not dry_run:
                blockers.append(f"source_class_minimum_not_met:{item.source_class}")
        production_ready = not blockers
        report = EnterpriseResourceReport(
            status="pass" if records else "fail",
            production_ready=production_ready,
            dry_run=dry_run,
            catalog_version=str(self.catalog.get("version", "unknown")),
            data_root=str(self.data_root),
            resource_root=str(self.resource_root),
            manifest_path=str(self.manifest_path),
            failed_resources_path=str(self.failed_resources_path),
            collection_report_path=str(self.collection_report_path),
            total_resources=len(records),
            successful_resources=sum(1 for record in records if record.status == "downloaded"),
            failed_resources=len(failures),
            required_failures=required_failures,
            coverage=coverage,
            blockers=blockers,
        )
        self.collection_report_path.write_text(
            json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return report


class EnterpriseResourceAuditor:
    def __init__(
        self,
        *,
        project_root: str | Path = ".",
        data_root: str | Path,
        catalog: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_root = Path(data_root).expanduser().resolve()
        self.catalog = catalog or load_enterprise_resource_catalog(self.project_root)
        self.resource_root = self.data_root / "research_resources"
        self.manifest_path = self.resource_root / "resource_manifest.json"

    def audit(self) -> EnterpriseResourceReport:
        blockers: list[str] = []
        records: list[EnterpriseResourceRecord] = []
        if is_inside_project_repo(self.data_root, self.project_root):
            blockers.append("resource_data_root_inside_repo")
        if not self.manifest_path.exists():
            blockers.append("resource_manifest_missing")
        else:
            try:
                raw_records = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                for raw in raw_records:
                    status = str(raw.get("status", "unknown"))
                    snapshot_path = raw.get("snapshot_path")
                    if status == "downloaded":
                        if not snapshot_path or not Path(snapshot_path).exists():
                            blockers.append(f"snapshot_missing:{raw.get('resource_id')}")
                            status = "failed"
                        elif raw.get("sha256"):
                            actual = hashlib.sha256(Path(snapshot_path).read_bytes()).hexdigest()
                            if actual != raw.get("sha256"):
                                blockers.append(f"snapshot_hash_mismatch:{raw.get('resource_id')}")
                                status = "failed"
                    records.append(
                        EnterpriseResourceRecord(
                            resource_id=str(raw.get("resource_id")),
                            source_class=str(raw.get("source_class")),
                            jurisdiction=str(raw.get("jurisdiction", "unknown")),
                            authority_level=str(raw.get("authority_level", "unknown")),
                            title=str(raw.get("title", raw.get("resource_id"))),
                            url=str(raw.get("url")),
                            required_for_enterprise=bool(raw.get("required_for_enterprise", False)),
                            status=status,
                            snapshot_path=snapshot_path,
                            sha256=raw.get("sha256"),
                            bytes=int(raw.get("bytes", 0) or 0),
                            content_type=raw.get("content_type"),
                            retrieved_at=raw.get("retrieved_at"),
                            parser_name=raw.get("parser_name"),
                            expected_content_type=raw.get("expected_content_type"),
                            final_url=raw.get("final_url"),
                            failure_code=raw.get("failure_code"),
                            failure_message=raw.get("failure_message"),
                        )
                    )
            except Exception as exc:
                blockers.append(f"resource_manifest_unreadable:{type(exc).__name__}")
        collector = EnterpriseResourceCollector(
            project_root=self.project_root,
            data_root=self.data_root,
            catalog=self.catalog,
            allow_repo_data_root=True,
        )
        coverage = collector._coverage_for(records)
        for item in coverage:
            if item.status != "pass":
                blockers.append(f"source_class_minimum_not_met:{item.source_class}")
        failed = [record for record in records if record.status == "failed"]
        required_failures = sum(1 for record in failed if record.required_for_enterprise)
        if required_failures:
            blockers.append("required_resource_download_failures")
        production_ready = not blockers
        report = EnterpriseResourceReport(
            status="pass",
            production_ready=production_ready,
            catalog_version=str(self.catalog.get("version", "unknown")),
            data_root=str(self.data_root),
            resource_root=str(self.resource_root),
            manifest_path=str(self.manifest_path),
            failed_resources_path=str(self.resource_root / "failed_resources.json"),
            collection_report_path=str(self.resource_root / "collection_report.json"),
            total_resources=len(records),
            successful_resources=sum(1 for record in records if record.status == "downloaded"),
            failed_resources=len(failed),
            required_failures=required_failures,
            coverage=coverage,
            blockers=blockers,
        )
        return report


class EnterpriseResourcePlanBuilder:
    def __init__(self, *, project_root: str | Path = ".", catalog: dict[str, Any] | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.catalog = catalog or load_enterprise_resource_catalog(self.project_root)

    def build(self, *, repo_root: str | Path | None = None, data_root: str | Path | None = None) -> dict[str, Any]:
        repo = Path(repo_root or self.catalog.get("default_windows_repo_root", "C:/dev/ME_FM_LLM"))
        data = Path(data_root or self.catalog.get("default_windows_data_root", "C:/dev/ME_FM_LLM_data"))
        resources = self.catalog.get("resources", [])
        required = [item for item in resources if item.get("required_for_enterprise")]
        repo_s = str(repo)
        data_s = str(data)
        sep = "\\" if ":" in data_s or "\\" in data_s else "/"
        eval_store_s = data_s.rstrip("\\/") + sep + "eval_store"
        resource_root_s = data_s.rstrip("\\/") + sep + "research_resources"
        return {
            "status": "pass",
            "catalog_version": self.catalog.get("version"),
            "repo_root": repo_s,
            "data_root": data_s,
            "resource_count": len(resources),
            "required_resource_count": len(required),
            "required_source_classes": self.catalog.get("required_source_classes", {}),
            "external_resource_root": resource_root_s,
            "commands": [
                f"cd {repo_s}",
                f"powershell -ExecutionPolicy Bypass -File .\\scripts\\harden-enterprise-local.ps1 -RepoRoot {repo_s} -DataRoot {data_s}",
                f"python .\\scripts\\collect-enterprise-resources.py --data-root {data_s}",
                f"python .\\scripts\\audit-enterprise-resource-collection.py --data-root {data_s}",
                f"python .\\scripts\\ingest-maine-authority.py --data-root {data_s}",
                f"python .\\scripts\\build-parsed-authority-store.py --data-root {data_s}",
                f"python .\\scripts\\build-authority-layer.py --data-root {data_s}",
                f"python .\\scripts\\build-retrieval-indexes.py --data-root {data_s}",
                f"python .\\scripts\\audit-enterprise-readiness.py --data-root {data_s} --eval-root {eval_store_s}",
            ],
            "data_boundary": "Downloaded research/legal resources are external runtime data. Do not commit them to the repository.",
        }

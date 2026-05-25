"""External corpus data-product scaffolding and official-source fetch helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .corpus_registry import (
    REQUIRED_ATTORNEY_REVIEWED_EVALS,
    REQUIRED_INDEXES,
    corpus_summary,
    full_corpus_manifest_entries,
)
from .fetch import is_official_url, safe_file_stem
from .normalize import normalize_text
from .source_manifest import SourceManifestEntry, write_manifest


DATA_ROOT_ENV = "ME_FM_LLM_DATA_ROOT"
DEFAULT_DATA_ROOT_NAME = "ME_FM_LLM_data"
REQUIRED_DATA_DIRS = (
    "manifests",
    "raw",
    "normalized",
    "parsed",
    "indexes",
    "evals",
    "audit",
    "logs",
)


@dataclass(frozen=True)
class CorpusFetchArtifact:
    source_id: str
    ok: bool
    raw_path: str = ""
    metadata_path: str = ""
    bytes_written: int = 0
    sha256: str = ""
    failure_class: str = "none"
    recovery_hint: str = ""

    def to_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def default_data_root(repo_root: str | Path | None = None) -> Path:
    configured = os.environ.get(DATA_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()
    return (root.parent / DEFAULT_DATA_ROOT_NAME).resolve()


def ensure_external_data_root(data_root: str | Path) -> Path:
    root = Path(data_root).expanduser().resolve()
    for name in REQUIRED_DATA_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def write_full_corpus_manifest(data_root: str | Path) -> Path:
    root = ensure_external_data_root(data_root)
    manifest_path = root / "manifests" / "full_corpus_manifest.json"
    write_manifest(manifest_path, full_corpus_manifest_entries())
    (root / "manifests" / "full_corpus_summary.json").write_text(
        json.dumps(corpus_summary(), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def audit_external_corpus(data_root: str | Path) -> dict[str, object]:
    root = ensure_external_data_root(data_root)
    entries = full_corpus_manifest_entries()
    missing_dirs = [name for name in REQUIRED_DATA_DIRS if not (root / name).is_dir()]
    manifest_path = root / "manifests" / "full_corpus_manifest.json"
    raw_metadata_count = len(list((root / "raw").glob("*/metadata.json")))
    normalized_count = len(list((root / "normalized").rglob("*.md")))
    parsed_count = len(list((root / "parsed").rglob("*.json")))
    index_status = {
        name: (root / "indexes" / f"{name}.json").is_file()
        for name in REQUIRED_INDEXES
        if name != "vector_index_optional"
    }
    eval_status: dict[str, dict[str, object]] = {}
    for filename, minimum in REQUIRED_ATTORNEY_REVIEWED_EVALS.items():
        path = root / "evals" / filename
        rows = _count_jsonl_rows(path)
        eval_status[filename] = {
            "path": str(path),
            "rows": rows,
            "minimum_rows": minimum,
            "pass": rows >= minimum,
        }
    blockers: list[str] = []
    if missing_dirs:
        blockers.append("external_data_root_layout_incomplete")
    if not manifest_path.is_file():
        blockers.append("full_corpus_manifest_missing")
    if raw_metadata_count < len(entries):
        blockers.append("official_source_raw_fetch_incomplete")
    if normalized_count < len(entries):
        blockers.append("normalization_incomplete")
    if parsed_count < len(entries):
        blockers.append("structured_parse_incomplete")
    if not all(index_status.values()):
        blockers.append("required_indexes_incomplete")
    if not all(item["pass"] for item in eval_status.values()):
        blockers.append("attorney_reviewed_eval_pack_incomplete")
    return {
        "schema": "maine_family_law_llm.external_corpus_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not blockers else "blocked",
        "data_root": str(root),
        "manifest_path": str(manifest_path),
        "required_source_count": len(entries),
        "raw_metadata_count": raw_metadata_count,
        "normalized_count": normalized_count,
        "parsed_count": parsed_count,
        "index_status": index_status,
        "eval_status": eval_status,
        "blockers": blockers,
        "recovery_hint": (
            "Run corpus fetch-live, normalize/parse/index builders, then attach attorney-reviewed "
            "gold eval rows before claiming enterprise GA legal-data readiness."
            if blockers
            else ""
        ),
    }


def normalize_external_corpus(data_root: str | Path) -> dict[str, object]:
    root = ensure_external_data_root(data_root)
    normalized_dir = root / "normalized"
    failures: list[dict[str, str]] = []
    count = 0
    for metadata_path in sorted((root / "raw").glob("*/metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source_id = str(metadata["id"])
        raw_path = Path(str(metadata["raw_path"]))
        try:
            raw_text = _read_raw_text(raw_path)
            text = normalize_text(raw_text)
            out_path = normalized_dir / f"{safe_file_stem(source_id)}.md"
            out_path.write_text(
                _normalized_header(metadata) + "\n\n" + text.strip() + "\n",
                encoding="utf-8",
            )
            count += 1
        except Exception as exc:
            failures.append(
                {
                    "source_id": source_id,
                    "failure_class": "normalization_failed",
                    "recovery_hint": f"Inspect raw source and parser dependency. detail={type(exc).__name__}: {exc}",
                }
            )
    return {
        "schema": "maine_family_law_llm.external_normalize.v1",
        "status": "pass" if not failures else "blocked",
        "normalized": count,
        "failures": failures,
        "output_dir": str(normalized_dir),
    }


def parse_external_corpus(data_root: str | Path) -> dict[str, object]:
    root = ensure_external_data_root(data_root)
    manifest_by_id = {entry.id: entry for entry in full_corpus_manifest_entries()}
    parsed_dir = root / "parsed"
    failures: list[dict[str, str]] = []
    count = 0
    for path in sorted((root / "normalized").glob("*.md")):
        source_id = path.stem
        entry = manifest_by_id.get(source_id)
        if entry is None:
            failures.append(
                {
                    "source_id": source_id,
                    "failure_class": "manifest_entry_missing",
                    "recovery_hint": "Rebuild the full corpus manifest before parsing.",
                }
            )
            continue
        text = path.read_text(encoding="utf-8")
        record = _structured_record(entry, text)
        (parsed_dir / f"{safe_file_stem(source_id)}.json").write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
        )
        count += 1
    return {
        "schema": "maine_family_law_llm.external_parse.v1",
        "status": "pass" if not failures else "blocked",
        "parsed": count,
        "failures": failures,
        "output_dir": str(parsed_dir),
    }


def build_required_indexes(data_root: str | Path) -> dict[str, object]:
    root = ensure_external_data_root(data_root)
    index_dir = root / "indexes"
    records = []
    for path in sorted((root / "parsed").glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    indexes = {
        "exact_citation_index": _citation_index(records),
        "statute_section_lookup": _type_lookup(records, {"statute"}),
        "rule_lookup": _type_lookup(
            records,
            {
                "court_rule",
                "standing_order",
                "evidence_rule",
                "appellate_rule",
                "ecourts_rule",
                "professional_conduct_rule",
                "bar_rule",
                "judicial_conduct_rule",
                "federal_rule",
                "federal_court_rule",
            },
        ),
        "case_name_lookup": _type_lookup(
            records,
            {"law_court_opinion_index", "law_court_opinion", "federal_case_law", "first_circuit_opinion", "us_supreme_court_opinion"},
        ),
        "case_citation_lookup": _citation_index(
            [
                record
                for record in records
                if record["source_type"]
                in {"law_court_opinion_index", "law_court_opinion", "federal_case_law", "first_circuit_opinion", "us_supreme_court_opinion"}
            ]
        ),
        "form_id_lookup": _type_lookup(records, {"court_form", "federal_court_form"}),
        "bm25_lexical_index": _lexical_index(records),
        "hybrid_retrieval_index": _hybrid_index(records),
        "source_card_index": _source_cards(records),
        "authority_graph": _authority_graph(records),
        "freshness_index": _freshness_index(records),
    }
    for name, payload in indexes.items():
        (index_dir / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "schema": "maine_family_law_llm.external_indexes.v1",
        "status": "pass",
        "record_count": len(records),
        "indexes_built": sorted(indexes),
        "output_dir": str(index_dir),
    }


def scaffold_attorney_review_eval_pack(data_root: str | Path) -> dict[str, object]:
    root = ensure_external_data_root(data_root)
    eval_dir = root / "evals"
    created: list[str] = []
    existing: list[str] = []
    for filename in REQUIRED_ATTORNEY_REVIEWED_EVALS:
        path = eval_dir / filename
        if path.exists():
            existing.append(str(path))
        else:
            path.write_text("", encoding="utf-8")
            created.append(str(path))
    readme = eval_dir / "README.md"
    lines = [
        "# Attorney-Reviewed Evaluation Pack",
        "",
        "These JSONL files must be filled and reviewed by qualified Maine/federal-court legal reviewers.",
        "Do not synthesize passing rows and do not include private client facts.",
        "",
        "Required minimum rows:",
        "",
    ]
    for filename, minimum in REQUIRED_ATTORNEY_REVIEWED_EVALS.items():
        lines.append(f"- `{filename}`: {minimum}")
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "schema": "maine_family_law_llm.eval_pack_scaffold.v1",
        "status": "blocked",
        "failure_class": "attorney_review_required",
        "created": created,
        "existing": existing,
        "readme": str(readme),
        "recovery_hint": "Populate these JSONL files with attorney-reviewed rows before GA legal-data release.",
    }


def fetch_live_official_corpus(
    data_root: str | Path,
    entries: list[SourceManifestEntry] | None = None,
    *,
    allow_live: bool = False,
    max_sources: int | None = None,
    force: bool = False,
) -> list[CorpusFetchArtifact]:
    if not allow_live:
        raise ValueError("live fetch requires allow_live=True")
    root = ensure_external_data_root(data_root)
    selected = entries or full_corpus_manifest_entries()
    if max_sources is not None:
        selected = selected[: max(0, max_sources)]
    artifacts: list[CorpusFetchArtifact] = []
    for entry in selected:
        artifacts.append(_fetch_one(root, entry, force=force))
    audit_path = root / "audit" / f"live_fetch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    audit_path.write_text(
        json.dumps([artifact.to_dict() for artifact in artifacts], indent=2) + "\n",
        encoding="utf-8",
    )
    return artifacts


def _fetch_one(root: Path, entry: SourceManifestEntry, *, force: bool) -> CorpusFetchArtifact:
    if not is_official_url(entry.url):
        return CorpusFetchArtifact(
            source_id=entry.id,
            ok=False,
            failure_class="non_official_url_rejected",
            recovery_hint=f"Replace {entry.url} with an official .gov/.uscourts/Maine source URL.",
        )
    source_dir = root / "raw" / safe_file_stem(entry.id)
    source_dir.mkdir(parents=True, exist_ok=True)
    ext = _extension_for_url(entry.url)
    raw_path = source_dir / f"source{ext}"
    metadata_path = source_dir / "metadata.json"
    if raw_path.exists() and metadata_path.exists() and not force:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return CorpusFetchArtifact(
            source_id=entry.id,
            ok=True,
            raw_path=str(raw_path),
            metadata_path=str(metadata_path),
            bytes_written=int(metadata.get("bytes", raw_path.stat().st_size)),
            sha256=str(metadata.get("sha256", "")),
        )
    try:
        request = Request(entry.url, headers={"User-Agent": "ME-FM-LLM-official-corpus-fetch/1.0"})
        with urlopen(request, timeout=30) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        return CorpusFetchArtifact(
            source_id=entry.id,
            ok=False,
            failure_class="fetch_failed",
            recovery_hint=f"Retry the official source later or inspect URL manually. detail={type(exc).__name__}: {exc}",
        )
    digest = hashlib.sha256(body).hexdigest()
    raw_path.write_bytes(body)
    metadata = {
        **entry.to_dict(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "raw_path": str(raw_path),
        "bytes": len(body),
        "sha256": digest,
        "content_type": content_type,
        "fetched_by": "maine_family_law_llm.corpus_build",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return CorpusFetchArtifact(
        source_id=entry.id,
        ok=True,
        raw_path=str(raw_path),
        metadata_path=str(metadata_path),
        bytes_written=len(body),
        sha256=digest,
    )


def _extension_for_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".html", ".htm", ".pdf", ".txt", ".json", ".xml"}:
        return suffix
    return ".raw"


def _read_raw_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError("pypdf is required to normalize PDF sources") from exc
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_bytes().decode("utf-8", errors="replace")


def _normalized_header(metadata: dict[str, object]) -> str:
    return "\n".join(
        [
            f"# {metadata.get('title', metadata.get('id', 'source'))}",
            f"Source ID: {metadata.get('id')}",
            f"Authority Class: {metadata.get('authority_class', '')}",
            f"Corpus Lane: {metadata.get('corpus_lane', '')}",
            f"Source Type: {metadata.get('source_type', '')}",
            f"Jurisdiction: {metadata.get('jurisdiction', '')}",
            f"Official URL: {metadata.get('url', '')}",
            f"Effective Date: {metadata.get('effective_date', '')}",
            f"Retrieved At: {metadata.get('retrieved_at', '')}",
            f"SHA256: {metadata.get('sha256', '')}",
        ]
    )


def _structured_record(entry: SourceManifestEntry, text: str) -> dict[str, object]:
    headings = [
        line.lstrip("#").strip()
        for line in text.splitlines()
        if line.startswith("#") and line.lstrip("#").strip()
    ]
    tokens = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9.-]{2,}", text.lower())))
    return {
        "schema": "maine_family_law_llm.parsed_authority_record.v1",
        "source_id": entry.id,
        "title": entry.title,
        "source_type": entry.source_type,
        "jurisdiction": entry.jurisdiction,
        "official": entry.official,
        "authority_class": entry.authority_class,
        "corpus_lane": entry.corpus_lane,
        "url": entry.url,
        "citation_hint": entry.citation_hint,
        "citation_aliases": list(entry.citation_aliases),
        "effective_date": entry.effective_date,
        "version_label": entry.version_label,
        "source_priority": entry.source_priority,
        "parser": entry.parser,
        "parser_status": "parsed_basic_text_record",
        "freshness_status": "fetched_needs_legal_review",
        "headings": headings[:200],
        "text_preview": text[:4000],
        "token_count": len(tokens),
        "tokens": tokens[:500],
    }


def _citation_index(records: list[dict[str, object]]) -> dict[str, object]:
    index: dict[str, list[str]] = {}
    for record in records:
        aliases = [str(record.get("citation_hint", "")), *[str(item) for item in record.get("citation_aliases", [])]]
        for alias in aliases:
            if alias:
                index.setdefault(alias, []).append(str(record["source_id"]))
    return {"schema": "exact_citation_index.v1", "entries": index}


def _type_lookup(records: list[dict[str, object]], source_types: set[str]) -> dict[str, object]:
    return {
        "schema": "type_lookup_index.v1",
        "entries": [
            _source_card(record)
            for record in records
            if str(record.get("source_type")) in source_types
        ],
    }


def _lexical_index(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "bm25_lexical_index_stub.v1",
        "entries": [
            {
                "source_id": record["source_id"],
                "title": record["title"],
                "tokens": record.get("tokens", []),
                "authority_class": record.get("authority_class", ""),
            }
            for record in records
        ],
    }


def _hybrid_index(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "hybrid_retrieval_index.v1",
        "lexical_index": "bm25_lexical_index.json",
        "vector_index": "optional_not_required_for_offline_ga_gate",
        "source_count": len(records),
    }


def _source_cards(records: list[dict[str, object]]) -> dict[str, object]:
    return {"schema": "source_card_index.v1", "entries": [_source_card(record) for record in records]}


def _source_card(record: dict[str, object]) -> dict[str, object]:
    return {
        "source_id": record["source_id"],
        "title": record["title"],
        "source_type": record["source_type"],
        "jurisdiction": record["jurisdiction"],
        "official": record["official"],
        "authority_class": record["authority_class"],
        "corpus_lane": record["corpus_lane"],
        "citation_hint": record["citation_hint"],
        "url": record["url"],
        "effective_date": record["effective_date"],
        "freshness_status": record["freshness_status"],
    }


def _authority_graph(records: list[dict[str, object]]) -> dict[str, object]:
    lanes: dict[str, list[str]] = {}
    for record in records:
        lanes.setdefault(str(record.get("corpus_lane", "")), []).append(str(record["source_id"]))
    return {"schema": "authority_graph.v1", "lanes": lanes}


def _freshness_index(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "freshness_index.v1",
        "entries": {
            str(record["source_id"]): {
                "effective_date": record.get("effective_date", ""),
                "version_label": record.get("version_label", ""),
                "freshness_status": record.get("freshness_status", ""),
            }
            for record in records
        },
    }


def _count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())

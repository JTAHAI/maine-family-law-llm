from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maine_family_law_llm.version import VERSION


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AttributionKitReport:
    status: str
    project_root: str
    generated_at: str
    license_path: str
    notice_path: str
    attribution_path: str
    citation_path: str
    resource_count: int
    official_source_count: int
    production_legal_ready: bool = False
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "project_root": self.project_root,
            "generated_at": self.generated_at,
            "license_path": self.license_path,
            "notice_path": self.notice_path,
            "attribution_path": self.attribution_path,
            "citation_path": self.citation_path,
            "resource_count": self.resource_count,
            "official_source_count": self.official_source_count,
            "production_legal_ready": self.production_legal_ready,
            "blockers": list(self.blockers),
        }


class AttributionKitBuilder:
    """Generate public-repo attribution/license scaffold without bundling legal corpora."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.catalog_path = self.project_root / "configs" / "maine_enterprise_resource_catalog.json"

    def _catalog(self) -> dict[str, Any]:
        if not self.catalog_path.is_file():
            return {"resources": []}
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def build(self, *, write: bool = True) -> AttributionKitReport:
        catalog = self._catalog()
        resources = list(catalog.get("resources", []))
        official_resources = [
            item for item in resources if str(item.get("authority_level", "")).startswith("official") or item.get("required_for_enterprise")
        ]
        license_path = self.project_root / "LICENSE.md"
        notice_path = self.project_root / "NOTICE.md"
        attribution_path = self.project_root / "ATTRIBUTION.md"
        citation_path = self.project_root / "CITATION.cff"
        blockers: list[str] = []
        license_text = """# Maine Family Law LLM Source Attribution License — Draft v0.1

Copyright (c) project contributors.

Permission is granted to use, copy, modify, and distribute the source code in this repository for lawful research, development, evaluation, and deployment, provided that redistributions preserve attribution to the Maine Family Law LLM project and retain this notice.

This repository does **not** license or convey ownership rights in Maine statutes, court rules, forms, opinions, third-party materials, private matter files, model weights, embeddings, vector databases, or attorney-reviewed evaluation data collected outside the source tree. Those materials must be obtained under their own terms from official or licensed sources.

No warranty is provided. This source tree is not legal advice, is not a filing-ready legal service, and is not production legal authority evidence. Production use requires official-source ingestion, attorney-reviewed evaluation data, verified release metrics, security/pilot evidence, and owner signoffs.

This draft license should be reviewed by counsel before publishing or commercial use.
"""
        notice_text = """# Notice

Maine Family Law LLM is a standalone source-code project for building Maine-family-law research, drafting-review, retrieval, verification, and evidence workflows.

The source code is intentionally separated from external legal corpora, private matter data, model weights, runtime stores, embeddings, and attorney-reviewed gold data. Official Maine and federal legal resources must be downloaded from their official sources into an external data root by the collection scripts.

Attribution should include the project name, repository URL, version or commit, and a clear statement that outputs require attorney review and verified source evidence before legal use.
"""
        lines = [
            "# Attribution and Source Resource Map",
            "",
            "This file lists resource targets used by collection scripts. It does not bundle the resource text, PDFs, corpora, or proprietary materials.",
            "",
            f"Catalog version: `{catalog.get('catalog_version') or catalog.get('version') or 'unknown'}`",
            "",
            "| Resource ID | Class | Jurisdiction | Required | URL |",
            "|---|---|---|---:|---|",
        ]
        for item in resources:
            url = str(item.get("url", "")).replace("|", "%7C")
            lines.append(
                f"| `{item.get('resource_id', '')}` | `{item.get('source_class', '')}` | `{item.get('jurisdiction', '')}` | {str(bool(item.get('required_for_enterprise'))).lower()} | {url} |"
            )
        lines.extend(
            [
                "",
                "## v5.1.0 permissive open-source adaptations",
                "",
                "The following projects informed or supplied permissively licensed components in v5.1.0:",
                "",
                "- **zeweihan/A-market-ecm-lawyer-plugin** — MIT License. Credited for the legal skill-contract architecture, role separation, many-to-many file classification pattern, QC triage concepts, folder scanner, DOCX embedded-media extractor, and skill-packaging convention. Maine-specific adaptations were rewritten and security-hardened. No Chinese ECM legal rule is represented as Maine authority.",
                "- **GoogleCloudPlatform/knowledge-catalog / Open Knowledge Format** — Apache License 2.0. Credited for the portable Markdown-plus-frontmatter knowledge-bundle concept, stable path-derived concept IDs, progressive indexes, and version-controllable graph-like source packs. The Maine implementation is a modified strict subset and does not include Google ADK, Gemini, BigQuery, cloud crawling, or external telemetry.",
                "",
                "Full notices and license copies are in `THIRD_PARTY_NOTICES.md` and `licenses/`.",
                "",
                "",
                "## v5.2.0 document handling and tracked Word editing",
                "",
                "- **Paparusi/legal-ai-agent** — MIT License, Copyright (c) 2026 Lê Minh Hiếu (Paparusi). Credited for document-workspace, structured action, revision-history, audit-schema, and inline-diff architecture patterns. The Maine implementation was independently rewritten and hardened; no Vietnamese legal rule, authentication code, unsafe Docker default, autonomous destructive permission, crawler, or billing/admin code was imported.",
                "- **pablospe/docx-editor** — MIT License, Copyright (c) 2026 Pablo Speciale. Used as the tracked Word editing engine for hash-anchored paragraph targeting, tracked changes, comments, and revision-aware new-copy output. Maine Family Law LLM adds explicit confirmation, path containment, file and operation limits, immutable originals, and review-required labeling.",
                "",
                "Full MIT license copies are retained in `licenses/` and the combined notices are in `THIRD_PARTY_NOTICES.md`.",
            ]
        )
        attribution_text = "\n".join(lines) + "\n"
        citation_text = f"""cff-version: 1.2.0
title: Maine Family Law LLM
message: Cite this source repository by project name, version or commit, and repository URL. Do not cite this repository as legal authority.
type: software
version: {VERSION}
date-released: 2026-08-23
authors:
  - name: Maine Family Law LLM contributors
license: other
repository-code: https://github.com/JTAHAI/maine-family-law-llm
url: https://github.com/JTAHAI/maine-family-law-llm
abstract: Local-first Maine family-law legal-information workbench for official-source research, exact citation and quote verification, privacy-aware record review, OCR derivatives, corpus organization, fail-closed filing gates, and review-required drafting support.
keywords:
  - Maine
  - family law
  - legal AI
  - local-first software
  - retrieval augmented generation
  - citation verification
  - evidence mapping
  - legal workflow
  - access to justice
"""
        if not resources:
            blockers.append("resource_catalog_empty_or_missing")
        if write:
            license_path.write_text(license_text, encoding="utf-8")
            notice_path.write_text(notice_text, encoding="utf-8")
            attribution_path.write_text(attribution_text, encoding="utf-8")
            citation_path.write_text(citation_text, encoding="utf-8")
        expected = [license_path, notice_path, attribution_path, citation_path]
        for path in expected:
            if write and not path.is_file():
                blockers.append(f"missing_generated_file:{path.name}")
        return AttributionKitReport(
            status="pass" if not blockers else "fail",
            project_root=str(self.project_root),
            generated_at=_utc_now(),
            license_path=str(license_path),
            notice_path=str(notice_path),
            attribution_path=str(attribution_path),
            citation_path=str(citation_path),
            resource_count=len(resources),
            official_source_count=len(official_resources),
            blockers=blockers,
        )

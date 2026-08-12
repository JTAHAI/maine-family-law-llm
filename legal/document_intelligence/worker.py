from __future__ import annotations

import argparse
import json
import os
import sys
import socket
from importlib import metadata
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_OUTPUT_BLOCKS = 20_000
MAX_OUTPUT_CHARS = 8_000_000


def _deny_network() -> None:
    def denied(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("document_intelligence_network_denied")

    socket.create_connection = denied  # type: ignore[assignment]
    socket.getaddrinfo = denied  # type: ignore[assignment]
    socket.socket.connect = denied  # type: ignore[assignment]
    socket.socket.connect_ex = denied  # type: ignore[assignment]


def _write(payload: dict[str, Any], output_path: str = "") -> int:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    if output_path:
        Path(output_path).write_text(serialized, encoding="utf-8")
    else:
        sys.stdout.write(serialized)
    return 0 if payload.get("status") == "pass" else 2


def _safe_version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not_installed"


def _docling(path: Path) -> dict[str, Any]:
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter
        from docling.document_converter import PdfFormatOption
    except Exception as exc:
        return {"status": "unavailable", "adapter": "docling", "error": f"{exc.__class__.__name__}: {exc}"[:500]}
    try:
        artifacts_path = str(os.environ.get("DOCLING_ARTIFACTS_PATH") or "").strip()
        format_options = None
        if artifacts_path:
            pipeline_options = PdfPipelineOptions(artifacts_path=Path(artifacts_path))
            format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        converter = DocumentConverter(format_options=format_options) if format_options else DocumentConverter()
        result = converter.convert(str(path))
        document = result.document
        markdown = document.export_to_markdown() if hasattr(document, "export_to_markdown") else ""
        raw: Any = document.export_to_dict() if hasattr(document, "export_to_dict") else {}
        blocks: list[dict[str, Any]] = []
        texts = raw.get("texts") if isinstance(raw, dict) else None
        if isinstance(texts, list):
            for index, item in enumerate(texts[:MAX_OUTPUT_BLOCKS], start=1):
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "")[:20_000]
                if not text.strip():
                    continue
                prov = item.get("prov") if isinstance(item.get("prov"), list) else []
                page = 0
                bbox = None
                if prov and isinstance(prov[0], dict):
                    page = int(prov[0].get("page_no") or 0)
                    raw_bbox = prov[0].get("bbox")
                    if isinstance(raw_bbox, dict):
                        bbox = [float(raw_bbox.get(k) or 0.0) for k in ("l", "t", "r", "b")]
                blocks.append({
                    "block_id": f"docling_{index:06d}",
                    "kind": str(item.get("label") or "text"),
                    "text": text,
                    "page_number": page,
                    "order": index,
                    "bbox": bbox,
                    "metadata": {"extractor": "docling"},
                })
        if not blocks and markdown:
            for index, paragraph in enumerate((part.strip() for part in markdown.split("\n\n") if part.strip()), start=1):
                blocks.append({
                    "block_id": f"docling_{index:06d}",
                    "kind": "markdown_block",
                    "text": paragraph[:20_000],
                    "page_number": 0,
                    "order": index,
                    "metadata": {"extractor": "docling_markdown_fallback"},
                })
                if len(blocks) >= MAX_OUTPUT_BLOCKS:
                    break
        return {
            "status": "pass",
            "adapter": "docling",
            "version": _safe_version("docling"),
            "blocks": blocks,
            "block_count": len(blocks),
            "markdown_preview": markdown[:MAX_OUTPUT_CHARS],
            "review_required": True,
        }
    except Exception as exc:
        return {"status": "failed", "adapter": "docling", "version": _safe_version("docling"), "error": f"{exc.__class__.__name__}: {exc}"[:500], "review_required": True}


def _presidio(path: Path) -> dict[str, Any]:
    try:
        import tldextract

        # Presidio's email recognizer otherwise lets tldextract refresh the
        # public-suffix list on first use. The bundled PSL snapshot is adequate
        # for this secondary detector and keeps the worker strictly offline.
        tldextract.extract = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_analyzer import AnalyzerEngine
    except Exception as exc:
        return {"status": "unavailable", "adapter": "presidio", "error": f"{exc.__class__.__name__}: {exc}"[:500]}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=nlp_configuration).create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        findings = []
        for item in analyzer.analyze(text=text, language="en")[:5000]:
            findings.append({
                "entity_type": str(item.entity_type),
                "start": int(item.start),
                "end": int(item.end),
                "score": round(float(item.score), 6),
                "recognizer": "presidio",
                "replacement": f"[REDACTED_{str(item.entity_type).upper()}]",
            })
        return {
            "status": "pass",
            "adapter": "presidio",
            "version": _safe_version("presidio-analyzer"),
            "findings": findings,
            "finding_count": len(findings),
            "review_required": True,
        }
    except Exception as exc:
        return {"status": "failed", "adapter": "presidio", "version": _safe_version("presidio-analyzer"), "error": f"{exc.__class__.__name__}: {exc}"[:500], "review_required": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("adapter", choices=("docling", "presidio"))
    parser.add_argument("input")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    _deny_network()
    path = Path(args.input).resolve()
    if path.is_symlink() or not path.is_file():
        return _write({"status": "blocked", "error": "input_not_regular_file"}, args.output)
    if path.stat().st_size > MAX_INPUT_BYTES:
        return _write({"status": "blocked", "error": "input_size_limit"}, args.output)
    return _write(_docling(path) if args.adapter == "docling" else _presidio(path), args.output)


if __name__ == "__main__":
    raise SystemExit(main())

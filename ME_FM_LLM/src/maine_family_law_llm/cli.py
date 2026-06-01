"""Command-line interface for the local Maine Family Law LLM workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .answer import compose_answer
from .chat_library import expand_query_for_library
from .corpus_build import (
    audit_external_corpus,
    build_required_indexes,
    default_data_root,
    fetch_live_official_corpus,
    normalize_external_corpus,
    parse_external_corpus,
    write_full_corpus_manifest,
)
from .corpus_registry import corpus_summary, full_corpus_manifest_entries
from .draft import draft_from_sources
from .fetch import SourceFetcher
from .index import save_index
from .normalize import normalize_fetch_result
from .safety import classify_prompt
from .source_manifest import ManifestValidationError
from .sources import DEFAULT_CACHE_DIR, DEFAULT_FIXTURES_DIR, DEFAULT_INDEX_PATH, DEFAULT_MANIFEST_PATH, get_source, load_seed_manifest
from .workbench import build_fixture_chunks, retrieve_fixture_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mfl", description="Maine Family Law LLM local workbench")
    sub = parser.add_subparsers(dest="command")

    sources = sub.add_parser("sources")
    sources_sub = sources.add_subparsers(dest="sources_command")
    sources_sub.add_parser("list")
    sources_sub.add_parser("validate")
    fetch_cmd = sources_sub.add_parser("fetch")
    fetch_cmd.add_argument("--fixtures", action="store_true")
    normalize_cmd = sources_sub.add_parser("normalize")
    normalize_cmd.add_argument("--fixtures", action="store_true")

    index_cmd = sub.add_parser("index")
    index_sub = index_cmd.add_subparsers(dest="index_command")
    build_cmd = index_sub.add_parser("build")
    build_cmd.add_argument("--fixtures", action="store_true")

    ask = sub.add_parser("ask")
    ask.add_argument("question")
    draft = sub.add_parser("draft")
    draft.add_argument("request")
    draft.add_argument("--mode", default="checklist")
    inspect = sub.add_parser("inspect-source")
    inspect.add_argument("source_id")
    corpus = sub.add_parser("corpus")
    corpus_sub = corpus.add_subparsers(dest="corpus_command")
    corpus_sub.add_parser("requirements")
    manifest_cmd = corpus_sub.add_parser("build-manifest")
    manifest_cmd.add_argument("--data-root", default=None)
    audit_cmd = corpus_sub.add_parser("audit")
    audit_cmd.add_argument("--data-root", default=None)
    normalize_live_cmd = corpus_sub.add_parser("normalize")
    normalize_live_cmd.add_argument("--data-root", default=None)
    parse_live_cmd = corpus_sub.add_parser("parse")
    parse_live_cmd.add_argument("--data-root", default=None)
    index_live_cmd = corpus_sub.add_parser("build-indexes")
    index_live_cmd.add_argument("--data-root", default=None)
    fetch_live_cmd = corpus_sub.add_parser("fetch-live")
    fetch_live_cmd.add_argument("--data-root", default=None)
    fetch_live_cmd.add_argument("--allow-live", action="store_true")
    fetch_live_cmd.add_argument("--force", action="store_true")
    fetch_live_cmd.add_argument("--max-sources", type=int, default=None)
    sub.add_parser("doctor")

    args = parser.parse_args(argv)
    try:
        if args.command == "sources":
            return _sources(args)
        if args.command == "index":
            return _index(args)
        if args.command == "ask":
            return _ask(args.question)
        if args.command == "draft":
            return _draft(args.request, args.mode)
        if args.command == "inspect-source":
            return _inspect(args.source_id)
        if args.command == "corpus":
            return _corpus(args)
        if args.command == "doctor":
            return _doctor()
        parser.print_help()
        return 2
    except ManifestValidationError as exc:
        print(json.dumps({"status": "failed", "failure_class": "manifest_invalid", "recovery_hint": str(exc)}))
        return 2


def _sources(args: argparse.Namespace) -> int:
    entries = load_seed_manifest()
    if args.sources_command == "list":
        for entry in entries:
            print(f"{entry.id}\t{entry.source_type}\tofficial={entry.official}\t{entry.url}")
        return 0
    if args.sources_command == "validate":
        print(json.dumps({"status": "pass", "source_count": len(entries), "manifest": str(DEFAULT_MANIFEST_PATH)}))
        return 0
    if args.sources_command == "fetch":
        fetcher = SourceFetcher(DEFAULT_FIXTURES_DIR, DEFAULT_CACHE_DIR, allow_live=False)
        results = [fetcher.fetch(entry, fixtures=bool(args.fixtures), force=True) for entry in entries]
        print(json.dumps({"status": "pass" if all(item.ok for item in results) else "failed", "fetched": sum(1 for item in results if item.ok)}))
        return 0 if all(item.ok for item in results) else 2
    if args.sources_command == "normalize":
        fetcher = SourceFetcher(DEFAULT_FIXTURES_DIR, DEFAULT_CACHE_DIR, allow_live=False)
        out_dir = Path(DEFAULT_CACHE_DIR) / "normalized"
        count = 0
        for entry in entries:
            result = fetcher.fetch(entry, fixtures=bool(args.fixtures), force=True)
            if result.ok:
                normalize_fetch_result(result, output_dir=out_dir)
                count += 1
        print(json.dumps({"status": "pass", "normalized": count, "output_dir": str(out_dir)}))
        return 0
    return 2


def _index(args: argparse.Namespace) -> int:
    if args.index_command == "build":
        chunks = build_fixture_chunks()
        proxy_chunks = [type("_ChunkProxy", (), {"to_dict": lambda self, payload=chunk: payload})() for chunk in chunks]
        path = save_index(DEFAULT_INDEX_PATH, proxy_chunks)
        print(json.dumps({"status": "pass", "chunk_count": len(chunks), "index_path": str(path)}))
        return 0
    return 2


def _ask(question: str) -> int:
    safety = classify_prompt(question)
    response = retrieve_fixture_sources(expand_query_for_library(question))
    answer = compose_answer(question, response.results, safety)
    print(answer.answer)
    return 0 if answer.failure_class == "none" else 1


def _draft(request: str, mode: str) -> int:
    response = retrieve_fixture_sources(request)
    draft = draft_from_sources(request, response.results, mode=mode)
    print(draft.text)
    return 0 if draft.failure_class == "none" else 1


def _inspect(source_id: str) -> int:
    entries = load_seed_manifest() + full_corpus_manifest_entries()
    entry = get_source(entries, source_id)
    if entry is None:
        print(json.dumps({"status": "failed", "failure_class": "source_not_found", "source_id": source_id}))
        return 1
    print(json.dumps(entry.to_dict(), indent=2))
    return 0


def _corpus(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root).resolve() if getattr(args, "data_root", None) else default_data_root()
    if args.corpus_command == "requirements":
        print(json.dumps(corpus_summary(), indent=2))
        return 0
    if args.corpus_command == "build-manifest":
        path = write_full_corpus_manifest(data_root)
        print(json.dumps({"status": "pass", "manifest_path": str(path), "data_root": str(data_root)}))
        return 0
    if args.corpus_command == "audit":
        report = audit_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "normalize":
        report = normalize_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "parse":
        report = parse_external_corpus(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "build-indexes":
        report = build_required_indexes(data_root)
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "pass" else 1
    if args.corpus_command == "fetch-live":
        try:
            artifacts = fetch_live_official_corpus(
                data_root,
                allow_live=bool(args.allow_live),
                max_sources=args.max_sources,
                force=bool(args.force),
            )
        except ValueError as exc:
            print(json.dumps({"status": "blocked", "failure_class": "live_fetch_not_confirmed", "recovery_hint": str(exc)}))
            return 2
        ok_count = sum(1 for item in artifacts if item.ok)
        print(
            json.dumps(
                {
                    "status": "pass" if ok_count == len(artifacts) else "blocked",
                    "fetched": ok_count,
                    "attempted": len(artifacts),
                    "data_root": str(data_root),
                    "failures": [item.to_dict() for item in artifacts if not item.ok],
                },
                indent=2,
            )
        )
        return 0 if ok_count == len(artifacts) else 1
    return 2


def _doctor() -> int:
    repo = Path(__file__).resolve().parents[2]
    forbidden = []
    for name in (".local_tmp", ".pytest_cache", "__pycache__", "ME_FM_LLM_data", "vector_store"):
        forbidden.extend(str(path.relative_to(repo)) for path in repo.rglob(name) if path.exists())
    forbidden = [item for item in forbidden if not item.startswith((".venv\\", ".venv/"))]
    status = "pass" if not forbidden else "fail"
    print(json.dumps({"status": status, "forbidden_paths": forbidden, "repo": str(repo)}))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

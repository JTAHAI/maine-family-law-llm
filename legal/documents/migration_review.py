"""Bounded, non-mutating legacy draft inventory; not a migration executor."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from pathlib import Path

from legal.documents import storage
from legal.documents import workspace as ws
from legal.security.durable_io import read_bounded_regular_file

MAX_FILES = 256
MAX_BYTES = 16 * 1024 * 1024
ID = re.compile(r"[a-f0-9]{32}")


def _entries(folder: Path):
    entries = list(itertools.islice(folder.iterdir(), MAX_FILES + 1))
    if len(entries) > MAX_FILES:
        raise ValueError("inventory_limit")
    return sorted(entries)


def review(case_root: Path) -> dict:
    """Return hashes/IDs only, never text, local paths or an activation grant."""
    try:
        with ws._LOCK:
            paths = ws.workspace_paths(case_root, create=False)
            if not storage.policy(paths.root)["legacy_read_only"]:
                raise ValueError("legacy_workspace_required")
            before: dict[Path, bytes] = {}
            rows = []
            total = 0

            def capture(path: Path) -> bytes:
                nonlocal total
                storage._location(path)  # Refuse reparse components before reading.
                raw = read_bounded_regular_file(path, max_bytes=storage.MAX_PLAINTEXT)
                total += len(raw)
                if len(before) >= MAX_FILES or total > MAX_BYTES:
                    raise ValueError("inventory_limit")
                before[path] = raw
                return raw

            index = json.loads(capture(paths.index))
            if index.get("schema_version") != ws.SCHEMA_VERSION:
                raise ValueError("index_schema")
            documents = index.get("documents")
            if not isinstance(documents, dict) or len(documents) > MAX_FILES:
                raise ValueError("index_shape")
            present = set()
            storage._location(paths.documents / "probe")
            for folder in _entries(paths.documents):
                if not ID.fullmatch(folder.name) or not folder.is_dir():
                    raise ValueError("unexpected_document_entry")
                if folder.name not in documents or not isinstance(documents[folder.name], dict):
                    raise ValueError("unindexed_document")
                revisions = folder / "revisions"
                storage._location(revisions / "probe")
                revision_ids = set()
                for path in _entries(revisions):
                    if path.suffix != ".json" or not ID.fullmatch(path.stem):
                        raise ValueError("unexpected_revision_entry")
                    raw = capture(path)
                    revision = ws.read_document_revision(case_root, folder.name, path.stem)
                    if (
                        revision.get("document_id") != folder.name
                        or revision.get("revision_id") != path.stem
                    ):
                        raise ValueError("revision_identity")
                    if revision.get("status") not in {"committed", "proposed", "rejected"}:
                        raise ValueError("revision_status")
                    revision_ids.add(path.stem)
                    rows.append(
                        {
                            "document_id": folder.name,
                            "revision_id": path.stem,
                            "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "content_sha256": revision["content_sha256"],
                            "status": revision["status"],
                        }
                    )
                document = documents[folder.name]
                refs = [
                    document.get("current_revision_id"),
                    *(document.get("pending_revision_ids") or []),
                ]
                if any(ref not in revision_ids for ref in refs):
                    raise ValueError("revision_reference_missing")
                present.add(folder.name)
            if present != set(documents):
                raise ValueError("document_missing")
            current_paths = {paths.index}
            for folder in _entries(paths.documents):
                storage._location(folder / "revisions" / "probe")
                current_paths.update(_entries(folder / "revisions"))
            if current_paths != set(before):
                raise ValueError("snapshot_changed")
            # A preview is a snapshot, not a lock held across user deliberation.
            for path, raw in before.items():
                if read_bounded_regular_file(path, max_bytes=storage.MAX_PLAINTEXT) != raw:
                    raise ValueError("snapshot_changed")
            result = {
                "schema_version": "document_migration_review_v1",
                "status": "review_required_json_migration_available",
                "document_count": len(documents),
                "revision_count": len(rows),
                "json_bytes": total,
                "index_sha256": hashlib.sha256(before[paths.index]).hexdigest(),
                "revisions": rows,
                "originals_changed": False,
                "migration_performed": False,
                "ready_to_migrate": True,
                "review_required": True,
                "filing_ready": False,
                "blockers": [
                    "explicit_confirmation_required",
                ],
                "scope_limits": ["private_review_sidecar_inventory_required"],
                "scope_notice": (
                    "Draft index and revision JSON only. Originals, exports and review sidecars "
                    "are not qualified by this inventory."
                ),
            }
            result["manifest_sha256"] = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            return result
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OSError,
        ws.DocumentWorkspaceError,
    ) as exc:
        raise ws.DocumentWorkspaceError(
            "workspace_migration_review_unavailable",
            "The legacy draft inventory could not be verified. No documents were changed. "
            "Keep the complete workspace; review missing, changed or oversized revision files.",
            status_code=409,
        ) from exc

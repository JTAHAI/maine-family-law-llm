"""Official-source fetch and cache layer with offline fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .source_manifest import SourceManifestEntry


OFFICIAL_HOST_SUFFIXES = (
    "ca1.uscourts.gov",
    "maine.gov",
    "courts.maine.gov",
    "mainelegislature.org",
    "legis.maine.gov",
    "med.uscourts.gov",
    "supremecourt.gov",
    "uscourts.gov",
    "uscode.house.gov",
)


@dataclass(frozen=True)
class FetchResult:
    ok: bool
    source_id: str
    raw_text: str = ""
    raw_path: str = ""
    metadata_path: str = ""
    metadata: dict[str, object] | None = None
    failure_class: str = "none"
    recovery_hint: str = ""


class SourceFetcher:
    def __init__(
        self,
        fixtures_dir: str | Path,
        cache_dir: str | Path,
        *,
        allow_live: bool = False,
    ) -> None:
        self.fixtures_dir = Path(fixtures_dir)
        self.cache_dir = Path(cache_dir)
        self.allow_live = allow_live

    def fetch(
        self,
        entry: SourceManifestEntry,
        *,
        fixtures: bool = True,
        force: bool = False,
        persist_cache: bool = True,
    ) -> FetchResult:
        if fixtures:
            fixture = self._find_fixture(entry.id)
            if fixture is None:
                return FetchResult(
                    ok=False,
                    source_id=entry.id,
                    failure_class="fixture_missing",
                    recovery_hint=f"Add a small offline fixture for source id {entry.id}.",
                )
            raw_text = fixture.read_text(encoding="utf-8", errors="replace")
            retrieved_at = datetime.fromtimestamp(fixture.stat().st_mtime, timezone.utc).isoformat()
        else:
            if not self.allow_live:
                return FetchResult(
                    ok=False,
                    source_id=entry.id,
                    failure_class="live_fetch_disabled",
                    recovery_hint="Rerun with allow_live=True, or use --fixtures for offline tests.",
                )
            if not is_official_url(entry.url):
                return FetchResult(
                    ok=False,
                    source_id=entry.id,
                    failure_class="non_official_url_rejected",
                    recovery_hint="Only official Maine source URLs are allowed for live fetch.",
                )
            try:
                request = Request(entry.url, headers={"User-Agent": "ME-FM-LLM-local-source-fetch/1.0"})
                with urlopen(request, timeout=20) as response:
                    raw_text = response.read().decode("utf-8", errors="replace")
                retrieved_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                return FetchResult(
                    ok=False,
                    source_id=entry.id,
                    failure_class="fetch_failed",
                    recovery_hint=f"Fetch failed for official URL; retry later or use fixtures. detail={exc}",
                )

        if not persist_cache:
            return FetchResult(
                ok=True,
                source_id=entry.id,
                raw_text=raw_text,
                metadata=self._metadata(entry, retrieved_at, fixtures=fixtures),
            )
        return self._write_cache(entry, raw_text, retrieved_at, fixtures=fixtures, force=force)

    @staticmethod
    def _metadata(
        entry: SourceManifestEntry,
        retrieved_at: str,
        *,
        fixtures: bool,
    ) -> dict[str, object]:
        return {
            "source_id": entry.id,
            "title": entry.title,
            "url": entry.url,
            "official": entry.official,
            "source_type": entry.source_type,
            "retrieved_at": retrieved_at,
            "fixture_mode": fixtures,
            "effective_date": entry.effective_date,
            "version_label": entry.version_label,
            "citation_hint": entry.citation_hint,
            "source_priority": entry.source_priority,
        }

    def _find_fixture(self, source_id: str) -> Path | None:
        for suffix in (".html", ".md", ".json"):
            path = self.fixtures_dir / f"{safe_file_stem(source_id)}{suffix}"
            if path.exists():
                return path
        return None

    def _write_cache(
        self,
        entry: SourceManifestEntry,
        raw_text: str,
        retrieved_at: str,
        *,
        fixtures: bool,
        force: bool,
    ) -> FetchResult:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        stem = safe_file_stem(entry.id)
        raw_path = self.cache_dir / f"{stem}.raw"
        metadata_path = self.cache_dir / f"{stem}.metadata.json"
        if raw_path.exists() and not metadata_path.exists() and not force:
            return FetchResult(
                ok=False,
                source_id=entry.id,
                failure_class="cache_metadata_missing",
                recovery_hint="Use force=True after inspecting the orphan cache file.",
            )
        raw_path.write_text(raw_text, encoding="utf-8")
        metadata = self._metadata(entry, retrieved_at, fixtures=fixtures)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return FetchResult(
            ok=True,
            source_id=entry.id,
            raw_text=raw_text,
            raw_path=str(raw_path),
            metadata_path=str(metadata_path),
            metadata=metadata,
        )


def is_official_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in OFFICIAL_HOST_SUFFIXES)


def safe_file_stem(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value).strip("_")

from datetime import datetime, timezone
import json
import runpy
from pathlib import Path

import pytest

from legal.connectors.base import RetrievedSource, SourceTarget
from legal.connectors.ingest_pipeline import OfficialAuthorityIngestor
from legal.corpus.source_snapshotter import SourceSnapshotter


class StaticFetcher:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def fetch(self, target: SourceTarget) -> RetrievedSource:
        return RetrievedSource(
            target=target,
            content=self.body,
            retrieved_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
            content_type="text/html",
            status_code=200,
            final_url=target.url,
        )


def test_ingest_pipeline_snapshots_and_manifests_official_source(tmp_path):
    target = SourceTarget(
        target_id="fixture-title-19a",
        source_class="statute_title_index",
        jurisdiction="maine",
        url="https://legislature.maine.gov/statutes/19-a/title19-Ach0sec0.html",
        parser_name="maine_revisor_title_index",
    )
    body = b"""
    <html><body><h1>Title 19-A: DOMESTIC RELATIONS</h1>
    <a href="title19-Asec1653.html">\xc2\xa71653. Parental rights and responsibilities</a>
    <p>Data for this page extracted on 10/20/2025 14:32:56.</p></body></html>
    """
    ingestor = OfficialAuthorityIngestor(fetcher=StaticFetcher(body), snapshot_base_dir=tmp_path)

    result = ingestor.ingest_target(target)
    manifest_path = ingestor.write_manifest([result])

    assert result.source_record.source_class == "statute_title_index"
    assert result.source_record.freshness_status == "known_extracted_timestamp"
    assert result.parser_audit.status == "parsed"
    assert result.canonical_count == 1
    assert manifest_path.exists()
    assert Path(result.snapshot_path).exists() is True
    assert "official_authority_store" not in result.snapshot_path


@pytest.mark.parametrize("name", ["../outside.json", "C:stream.json", "NUL.json", "", "bad.json:ads", "nested/manifest.json"])
def test_snapshot_manifest_filename_cannot_escape_or_name_a_device(tmp_path, name):
    root = tmp_path / "snapshots"
    with pytest.raises(ValueError, match="authority_manifest_filename_invalid"):
        SourceSnapshotter(root).write_manifest([], filename=name)
    assert not root.exists()
    assert not (tmp_path / "outside.json").exists()


def test_atomic_manifest_write_keeps_prior_data_on_replace_failure(tmp_path, monkeypatch):
    snapshotter = SourceSnapshotter(tmp_path)
    manifest = snapshotter.write_manifest([{"source_id": "prior"}])
    prior = manifest.read_bytes()

    def fail(*args):
        raise OSError("fictional replace failure")

    monkeypatch.setattr("legal.security.durable_io.os.replace", fail)
    with pytest.raises(OSError, match="fictional replace failure"):
        snapshotter.write_manifest([{"source_id": "replacement"}])
    assert manifest.read_bytes() == prior
    assert sorted(path.name for path in tmp_path.iterdir() if path.is_file()) == [manifest.name]


def test_cli_failed_refresh_preserves_existing_manifest(tmp_path, monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "ingest-maine-authority.py"
    root = tmp_path / "authority"
    manifest = root / "official_authority_store" / "source_manifest.json"
    manifest.parent.mkdir(parents=True)
    prior = b'[{"source_id": "prior", "hash": "example"}]'
    manifest.write_bytes(prior)
    monkeypatch.setattr("sys.argv", [str(script), "--data-root", str(root), "--fixture-mode", "--max-targets", "0"])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(script), run_name="__main__")
    assert result.value.code == 2
    assert manifest.read_bytes() == prior
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "partial"
    assert report["manifest_changed"] is False
    assert report["manifest_record_count"] == 1

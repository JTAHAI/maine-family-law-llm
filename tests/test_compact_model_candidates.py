from __future__ import annotations

import hashlib

import pytest

from scripts import acquire_compact_model_candidates as acquisition


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/a",
        "https://huggingface.co.evil.test/a",
        "https://127.0.0.1/a",
        "https://huggingface.co:444/a",
        "https://secret@huggingface.co/a",
        "file:///x",
        "https://evil-hf.co/a",
    ],
)
def test_acquisition_rejects_wrong_origin(url):
    with pytest.raises(ValueError, match="origin_forbidden"):
        acquisition.safe_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://huggingface.co/Qwen/x",
        "https://cas-bridge.xethub.hf.co/a",
        "https://release-assets.githubusercontent.com/a",
    ],
)
def test_public_download_hosts(url):
    acquisition.safe_url(url)


@pytest.mark.parametrize("name", ["../model", "x/y", "x\\y", "D:evil", "..", ".", "x:stream"])
def test_acquisition_path_traversal_rejected(tmp_path, monkeypatch, name):
    monkeypatch.setattr(acquisition, "ROOT", tmp_path)
    with pytest.raises(ValueError):
        acquisition.local_path(tmp_path / "dist", name)


def test_reuse_hashes_existing_model_and_does_not_download(tmp_path):
    data = b"fictional weights"
    path = tmp_path / "model.safetensors"
    path.write_bytes(data)
    row = {"size": len(data), "lfs": {"sha256": hashlib.sha256(data).hexdigest()}}
    assert acquisition.download(None, "https://huggingface.co/x", path, row) == row["lfs"]["sha256"]
    path.write_bytes(b"corrupted weights")
    with pytest.raises(ValueError):
        acquisition.download(None, "https://huggingface.co/x", path, row)


@pytest.mark.parametrize("size", [True, -1, 0, 1_500_000_000, 1_500_000_001])
def test_download_budget_checked_before_network(tmp_path, size):
    with pytest.raises(ValueError, match="budget_exceeded"):
        acquisition.download(None, "https://huggingface.co/x", tmp_path / "file", {"size": size})


class Response:
    status_code = 200
    headers = {}

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, size):
        yield self.data


def test_overflow_never_publishes_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(acquisition, "ROOT", tmp_path)
    folder = tmp_path / "dist"
    folder.mkdir()
    monkeypatch.setattr(acquisition, "get", lambda *a, **k: Response(b"too much"))
    target = folder / "model.gguf"
    with pytest.raises(ValueError, match="overflow"):
        acquisition.download(
            None, "https://huggingface.co/x", target, {"size": 2, "lfs": {"sha256": "a" * 64}}
        )
    assert not target.exists()


def test_resume_cannot_append_full_response(tmp_path, monkeypatch):
    monkeypatch.setattr(acquisition, "ROOT", tmp_path)
    folder = tmp_path / "dist"
    folder.mkdir()
    (folder / "model.gguf.partial").write_bytes(b"a")
    monkeypatch.setattr(acquisition, "get", lambda *a, **k: Response(b"ab"))
    with pytest.raises(ValueError, match="resume_not_supported"):
        acquisition.download(
            None,
            "https://huggingface.co/x",
            folder / "model.gguf",
            {"size": 2, "lfs": {"sha256": "a" * 64}},
        )
    assert (folder / "model.gguf.partial").read_bytes() == b"a"


def test_metadata_files_are_git_blob_verified(tmp_path):
    path = tmp_path / "LICENSE"
    path.write_bytes(b"license")
    row = {"size": 7, "blobId": hashlib.sha1(b"blob 7\0license").hexdigest()}
    assert acquisition.verify_file(path, row) == hashlib.sha256(b"license").hexdigest()
    row["blobId"] = "0" * 40
    with pytest.raises(ValueError, match="metadata_hash_mismatch"):
        acquisition.verify_file(path, row)


def test_unbounded_metadata_is_rejected():
    with pytest.raises(ValueError, match="metadata_size_exceeded"):
        acquisition.bounded_json(Response(b"a" * 100), maximum=20)


@pytest.mark.parametrize("declared", ["apache-2.0", "unknown", None])
def test_span_reader_requires_its_actual_cc_by_license(monkeypatch, declared):
    import json

    candidate = acquisition.CATALOG["minilm-span-reader"]
    monkeypatch.setattr(
        acquisition,
        "get",
        lambda *a, **k: Response(
            json.dumps(
                {
                    "sha": candidate["revision"],
                    "cardData": {"license": declared},
                }
            ).encode()
        ),
    )
    with pytest.raises(ValueError, match="revision_or_license_mismatch"):
        acquisition.acquire("minilm-span-reader")


def test_duplicate_metadata_keys_are_rejected():
    with pytest.raises(ValueError):
        acquisition.bounded_json(Response(b'{"sha":"first","sha":"second"}'))


@pytest.mark.parametrize(
    "name",
    [
        "llama-cli.exe",
        "llama-cli-impl.dll",
        "ggml-rpc.dll",
        "llama-bench-impl.dll",
        "unknown.dll",
        "ggml-cpu-../bad.dll",
    ],
)
def test_native_examples_and_rpc_are_not_deployed(name):
    from scripts.acquire_compact_cpu_runtime import engine_member

    assert not engine_member(name)


@pytest.mark.parametrize(
    "name",
    [
        "llama-server.exe",
        "llama-server-impl.dll",
        "libomp.dll",
        "ggml-cpu-sse42.dll",
        "ggml-cpu-zen4.dll",
    ],
)
def test_native_cpu_runtime_members(name):
    from scripts.acquire_compact_cpu_runtime import engine_member

    assert engine_member(name)

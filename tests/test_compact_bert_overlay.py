import base64
import hashlib
import importlib.metadata as metadata
import json
from types import SimpleNamespace

import pytest

from scripts import prepare_compact_bert_overlay as overlay


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source, target = tmp_path / "installed", tmp_path / "overlay"
    names = [
        "transformers/__init__.py",
        "transformers/models/__init__.py",
        "transformers/models/bert/modeling_bert.py",
        "transformers/models/bert/tokenization_bert.py",
        "transformers/models/auto/modeling_auto.py",
        "transformers/models/encoder_decoder/__init__.py",
        "transformers/models/unselected/__init__.py",
        "transformers-5.14.1.dist-info/LICENSE",
    ]
    entries = []
    for name in names:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = b"# fictional Python or notice fixture\n"
        path.write_bytes(raw)
        entry = metadata.PackagePath(name)
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        entry.hash = metadata.FileHash("sha256=" + digest)
        entry.size = len(raw)
        entries.append(entry)
    dist = SimpleNamespace(
        metadata={"Name": "transformers"},
        version=overlay.VERSION,
        files=entries,
        locate_file=lambda name: source / str(name),
    )
    monkeypatch.setattr(overlay, "license_paths", lambda *_: ([names[-1]], []))
    # The actual pytest fixture remains under repo dist; no external writes.
    return dist, source, target


def test_copy_and_verify_exact_selection_without_admission(fixture):
    dist, source, target = fixture
    report = overlay.prepare(build=True, dist=dist, directory=target)
    assert overlay.verify(target, dist=dist) == report
    assert not report["ga_ready"] and not report["production_admitted"]
    assert not (target / "transformers/models/unselected").exists()
    assert len(report["files"]) == 7
    assert overlay.prepare(build=True, dist=dist, directory=target) == report


@pytest.mark.parametrize("fault", ["source", "destination", "manifest", "extra", "version"])
def test_modified_or_unlisted_input_fails_closed(fixture, fault):
    dist, source, target = fixture
    overlay.prepare(build=True, dist=dist, directory=target)
    if fault == "source":
        (source / "transformers/__init__.py").write_text("changed")
    elif fault == "destination":
        (target / "transformers/__init__.py").write_text("changed")
    elif fault == "manifest":
        path = target / overlay.MANIFEST_NAME
        report = json.loads(path.read_text())
        report["ga_ready"] = True
        path.write_text(json.dumps(report))
    elif fault == "extra":
        (target / "rogue.py").write_text("bad")
    else:
        dist.version = "0.0"
    with pytest.raises(ValueError):
        overlay.verify(target, dist=dist)


@pytest.mark.parametrize("name", ["../escape.py", "/escape.py", "a//b.py", "a\\b.py", "C:/a.py"])
def test_paths_cannot_escape(tmp_path, name):
    with pytest.raises(ValueError):
        overlay.overlay_path(tmp_path, name)


def test_file_budget_checked_before_copy(fixture, monkeypatch):
    dist, _, target = fixture
    monkeypatch.setattr(overlay, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="size_budget"):
        overlay.prepare(build=True, dist=dist, directory=target)
    assert not target.exists()

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from legal.security.secure_temp import SecureTempBroker, SecureTempError


def test_private_workspace_uses_local_root_cleans_and_records_no_content(tmp_path: Path) -> None:
    broker = SecureTempBroker(tmp_path / "fictional-matter")
    with broker.workspace("ocrmypdf") as workspace:
        assert workspace.is_dir()
        sample = workspace / "fictional.txt"
        sample.write_text("fictional private record text", encoding="utf-8")
        if os.name != "nt":
            assert (workspace.stat().st_mode & 0o077) == 0
    assert not workspace.exists()
    rows = [json.loads(line) for line in broker.receipts.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["status"] == "cleaned"
    assert "fictional private record text" not in broker.receipts.read_text(encoding="utf-8")
    assert rows[-1]["file_count"] == 1
    assert broker.status()["content_logged"] is False


def test_symlink_and_invalid_workspace_labels_fail_closed(tmp_path: Path) -> None:
    broker = SecureTempBroker(tmp_path / "fictional-matter")
    with pytest.raises(SecureTempError):
        with broker.workspace("../unsafe"):
            pass
    if hasattr(Path, "symlink_to"):
        with broker.workspace("presidio") as workspace:
            target = workspace / "target.txt"; target.write_text("x", encoding="utf-8")
            link = workspace / "link.txt"
            try:
                link.symlink_to(target)
            except OSError:
                pytest.skip("symlink creation unavailable on this test host")
        rows = [json.loads(line) for line in broker.receipts.read_text(encoding="utf-8").splitlines()]
        assert rows[-1]["status"] == "cleanup_blocked"


def test_stale_workspace_recovery_uses_receipt_without_content(tmp_path: Path) -> None:
    broker = SecureTempBroker(tmp_path / "fictional-matter")
    broker._ensure_root()
    stale = broker.root / "presidio-tmp-stale"; stale.mkdir(); (stale / "x.txt").write_text("fictional", encoding="utf-8")
    old = time.time() - 7200; __import__("os").utime(stale, (old, old))
    report = broker.recover_stale(minimum_age_seconds=3600)
    assert report["status"] == "pass"
    assert report["recovered_workspace_count"] == 1
    assert not stale.exists()

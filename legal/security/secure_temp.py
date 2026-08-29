"""Private, non-repository temporary-workspace broker with cleanup receipts."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .durable_io import atomic_write_bytes, durable_append_text, exclusive_file_lock, read_bounded_regular_file


class SecureTempError(ValueError): pass

_MAX_RECEIPT_BYTES = 1024 * 1024

def _safe_label(value: str) -> str:
    value = str(value or "").strip().lower()
    if not value or len(value) > 48 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value):
        raise SecureTempError("secure_temp_label_invalid")
    return value

class SecureTempBroker:
    """Own bounded 0700 workspaces and never retain their content in receipts."""
    def __init__(self, matter_root: str | Path) -> None:
        self.root = Path(matter_root).resolve() / ".mfl-secure-temp"
        self.receipts = self.root / "cleanup-receipts.jsonl"

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try: os.chmod(self.root, stat.S_IRWXU)
        except OSError: pass

    def _receipt(self, *, session_id: str, purpose: str, status: str, file_count: int, byte_count: int) -> dict:
        record = {"session_id": session_id, "purpose": purpose, "status": status, "file_count": file_count, "byte_count": byte_count, "timestamp": time.time()}
        record["receipt_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        durable_append_text(self.receipts, json.dumps(record, sort_keys=True)+"\n")
        return record

    @staticmethod
    def _safe_remove(path: Path) -> tuple[int, int]:
        if path.is_symlink() or not path.is_dir(): raise SecureTempError("secure_temp_workspace_invalid")
        files = bytes_ = 0
        for child in path.rglob("*"):
            if child.is_symlink(): raise SecureTempError("secure_temp_symlink_detected")
            if child.is_file(): files += 1; bytes_ += child.stat().st_size
        shutil.rmtree(path)
        return files, bytes_

    @contextmanager
    def workspace(self, purpose: str) -> Iterator[Path]:
        purpose = _safe_label(purpose); self._ensure_root()
        session_id = f"tmp-{secrets.token_hex(12)}"; path = self.root / f"{purpose}-{session_id}"
        path.mkdir(mode=0o700)
        try:
            yield path
        finally:
            try:
                files, size = self._safe_remove(path) if path.exists() else (0, 0)
                self._receipt(session_id=session_id, purpose=purpose, status="cleaned", file_count=files, byte_count=size)
            except Exception:
                self._receipt(session_id=session_id, purpose=purpose, status="cleanup_blocked", file_count=0, byte_count=0)

    def recover_stale(self, *, minimum_age_seconds: int = 3600) -> dict:
        self._ensure_root(); cleaned = blocked = 0
        now = time.time()
        for path in self.root.iterdir():
            if path.name in {self.receipts.name, self.receipts.with_suffix(".lock").name} or not path.is_dir(): continue
            if now - path.stat().st_mtime < max(60, minimum_age_seconds): continue
            try:
                files, size = self._safe_remove(path); self._receipt(session_id=path.name[-28:], purpose=path.name.split("-",1)[0], status="crash_recovered", file_count=files, byte_count=size); cleaned += 1
            except Exception: blocked += 1
        return {"status": "pass" if not blocked else "blocked", "recovered_workspace_count": cleaned, "blocked_workspace_count": blocked, "review_required": True}

    def status(self) -> dict:
        pending = 0
        if self.root.is_dir(): pending = sum(1 for p in self.root.iterdir() if p.is_dir() and not p.is_symlink())
        return {"status": "pass", "root_created": self.root.is_dir(), "pending_workspace_count": pending, "content_logged": False, "permissions": "owner_only_when_supported", "review_required": True}

__all__ = ["SecureTempBroker", "SecureTempError"]

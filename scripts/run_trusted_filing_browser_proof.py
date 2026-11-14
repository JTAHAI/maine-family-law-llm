"""Exercise the production workbench over loopback with a fresh fictional matter."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    # A nested test worktree must keep its simulated external authority outside
    # the source checkout, but still inside the owning checkout's dist/qa.
    scratch = Path(sys.argv[1]).resolve()
    if not scratch.is_dir():
        raise SystemExit("Provide an existing dedicated QA scratch directory.")
    with tempfile.TemporaryDirectory(prefix="trusted-filing-", dir=scratch) as run:
        root = Path(run)
        os.environ.update({
            "APPDATA": str(root / "profile"),
            "LOCALAPPDATA": str(root / "profile"),
            "MFL_CASE_LIBRARY_PATH": str(root / "case-library.json"),
            "MFL_IDEMPOTENCY_STATE_ROOT": str(root / "replay"),
            "MAINE_MATTER_STORE_KEY": secrets.token_hex(32),
            "TEMP": run, "TMP": run,
        })
        sys.path[:0] = [str(repo / "src"), str(repo), str(repo / "tests")]
        import uvicorn
        from app.api.production import app
        from maine_family_law_llm.case_library import register_case_root
        from test_trusted_filing_review import build_filing_fixture

        authority, case, doc, _source, fact, phrase, cite, source_id = build_filing_fixture(root)
        register_case_root(case)
        credential = secrets.token_hex(32)
        os.environ.update({
            "MFL_AUTHORITY_DATA_ROOT": str(authority),
            "MAINE_FAMILY_LAW_DATA_ROOT": str(authority),
            "MFL_FILING_REVIEWER_ID": "fixture-reviewer",
            "MFL_FILING_REVIEWER_TENANT": "local-desktop",
            "MFL_FILING_REVIEWER_MATTER_ID": hashlib.sha256(str(case.resolve()).encode()).hexdigest()[:16],
            "MFL_FILING_REVIEWER_BEARER_SHA256": hashlib.sha256(credential.encode()).hexdigest(),
        })
        fixture = root / "browser-input.json"
        fixture.write_text(json.dumps({
            "credential": credential, "draft": doc["content"], "fact": fact, "quote": phrase,
            "claims": [cite + ".", phrase], "source_id": source_id,
        }), encoding="utf-8")
        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            origin = f"http://127.0.0.1:{bound.getsockname()[1]}"
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
            worker = threading.Thread(target=server.run, kwargs={"sockets": [bound]}, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 15
                while worker.is_alive() and not server.started and time.monotonic() < deadline:
                    time.sleep(0.05)
                if not server.started:
                    raise RuntimeError("Fictional loopback fixture did not start.")
                return subprocess.run(
                    ["node", str(repo / "scripts" / "verify_trusted_filing.mjs"), origin, str(fixture)],
                    cwd=repo, timeout=150, check=False,
                ).returncode
            finally:
                server.should_exit = True
                worker.join(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())

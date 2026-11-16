"""Exercise the production workbench over loopback with a fresh fictional matter."""

from __future__ import annotations

import argparse
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
import urllib.request
from pathlib import Path


def _run_frozen(executable: Path, sha256: str, repo: Path, input_path: Path, browser_environment: dict[str, str]) -> int:
    if not executable.is_file() or executable.name != "MaineFamilyLawLLM.exe":
        raise SystemExit("Select the exact frozen MaineFamilyLawLLM.exe.")
    with executable.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != sha256:
            raise SystemExit("Frozen executable SHA-256 does not match.")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    instance = secrets.token_hex(32)
    child_env = {
        **os.environ, "MFL_LOCAL_API_INSTANCE_ID": instance, "MFL_RUNTIME_MODE": "store",
        "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9", "NO_PROXY": "127.0.0.1,localhost,::1",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    }
    process = subprocess.Popen(
        [str(executable), "--serve-local-api", "--port", str(port)],
        cwd=executable.parent, env=child_env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        deadline = time.monotonic() + 150
        while process.poll() is None and time.monotonic() < deadline:
            try:
                with opener.open(origin + "/api/health", timeout=3) as response:
                    if response.headers.get("X-MFL-Service-Instance") == instance:
                        break
            except OSError:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("Exact frozen runtime did not become healthy.")
        result = subprocess.run(
            ["node", str(repo / "scripts" / "verify_trusted_filing.mjs"), origin, str(input_path), sha256],
            cwd=repo, env=browser_environment, timeout=150, check=False,
        )
        with opener.open(origin + "/api/health", timeout=5) as response:
            if response.headers.get("X-MFL-Service-Instance") != instance:
                raise RuntimeError("Frozen runtime identity changed during the browser test.")
        return result.returncode
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--runtime-executable", type=Path)
    parser.add_argument("--runtime-sha256")
    args = parser.parse_args()
    if bool(args.runtime_executable) != bool(args.runtime_sha256):
        parser.error("Provide both --runtime-executable and --runtime-sha256 for frozen proof.")
    # A nested test worktree must keep its simulated external authority outside
    # the source checkout, but still inside the owning checkout's dist/qa.
    scratch = args.scratch.resolve()
    if not scratch.is_dir():
        raise SystemExit("Provide an existing dedicated QA scratch directory.")
    with tempfile.TemporaryDirectory(prefix="trusted-filing-", dir=scratch) as run:
        root = Path(run)
        profile = root / "profile"
        profile.mkdir()
        actual_windows_profile = os.environ.get("USERPROFILE")
        proof_node_modules = os.environ.get("MFL_PROOF_NODE_MODULES", "")
        for key in tuple(os.environ):
            if key.startswith(("MFL_", "MAINE_")):
                del os.environ[key]
        os.environ.update({
            "APPDATA": str(profile),
            "LOCALAPPDATA": str(profile),
            "USERPROFILE": str(profile),
            # The Store launcher sets its canonical profile location regardless
            # of the inherited case-library env var. Seed that same location.
            "MFL_CASE_LIBRARY_PATH": str(profile / "MaineFamilyLawLLM" / "case_library.json"),
            "MFL_RUNTIME_STATE_ROOT": str(root / "state"),
            "MFL_VAULT_KEY_ROOT": str(root / "vault"),
            "MFL_IDEMPOTENCY_STATE_ROOT": str(root / "replay"),
            "MFL_PROOF_NODE_MODULES": proof_node_modules,
            "MAINE_MATTER_STORE_KEY": secrets.token_hex(32),
            "TEMP": run, "TMP": run,
        })
        browser_environment = os.environ.copy()
        if actual_windows_profile:
            # Edge uses the registered OS profile to find its installer. Its
            # disposable browser user-data directory is still owned by Playwright.
            browser_environment["USERPROFILE"] = actual_windows_profile
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
        if args.runtime_executable:
            return _run_frozen(args.runtime_executable.resolve(), args.runtime_sha256, repo, fixture, browser_environment)
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
                    cwd=repo, env=browser_environment, timeout=150, check=False,
                ).returncode
            finally:
                server.should_exit = True
                worker.join(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())

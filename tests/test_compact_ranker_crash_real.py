"""Opt-in real-weight host-crash proof for the private ranker process."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from queue import Queue
from threading import Thread

import psutil
import pytest

from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("MFL_RUN_RANKER_PROCESS_PROOF") != "1",
    reason="Opt-in Windows real-weight ranker crash drill; requires 4 GiB free RAM",
)
def test_ranker_job_exits_when_its_actual_host_is_terminated():
    run_id = os.environ.get("MFL_RANKER_PROOF_RUN_ID", "01")
    assert re.fullmatch(r"[a-z0-9-]{1,24}", run_id)
    output = OUTPUT / f"ranker-process-crash-{run_id}.json"
    assert not output.exists(), "Preserve the earlier crash receipt"
    script = """
import json, os
from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from scripts.acquire_compact_model_candidates import OUTPUT
worker = IsolatedCompactRanker(
    pinned_inventory(OUTPUT/'legal-passage-reranker','acquisition.json'),
    scratch=OUTPUT/'scratch',research_only=True)
try:
    worker.warm()
    print(json.dumps({'worker_pid':worker._process.pid,'host_pid':os.getpid(),
                      'kernel_job_active':worker._job is not None}),flush=True)
    input()
finally:
    worker.close()
"""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC"}
    }
    environment.update(
        {
            "PATH": str(Path(sys.executable).parent),
            "PYTHONDONTWRITEBYTECODE": "1",
            "USERNAME": "mfl-ranker-worker",
            "USERPROFILE": str(OUTPUT / "scratch"),
            "TEMP": str(OUTPUT / "scratch"),
            "TMP": str(OUTPUT / "scratch"),
        }
    )
    host = subprocess.Popen(
        [sys.executable, "-B", "-c", script],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    report = {
        "fictional_only": True,
        "level": "actual_ranker_host_termination",
        "production_admitted": False,
        "ga_ready": False,
    }
    lines = Queue()
    reader = Thread(target=lambda: lines.put(host.stdout.readline()), daemon=True)
    reader.start()
    actual_host = owned = None
    helpers = []
    try:
        row = json.loads(lines.get(timeout=90))
        actual_host, owned = psutil.Process(row["host_pid"]), psutil.Process(row["worker_pid"])
        assert actual_host.pid == host.pid or host.pid in {p.pid for p in actual_host.parents()}
        assert owned.ppid() == actual_host.pid and row["kernel_job_active"] is True
        assert owned.exe().casefold() == psutil.Process().exe().casefold()
        assert any("compact_ranker_worker" in value for value in owned.cmdline())
        helpers = owned.children(recursive=True)
        for helper in helpers:
            assert (
                Path(helper.exe()).resolve()
                == Path(os.environ["SYSTEMROOT"]) / "System32" / "conhost.exe"
            )
        started = time.monotonic()
        actual_host.terminate()  # Only the disposable interpreter created above.
        actual_host.wait(timeout=5)
        host.wait(timeout=5)
        owned.wait(timeout=5)
        for helper in helpers:
            helper.wait(timeout=5)
        report.update(
            kernel_job_active=True,
            host_crash_exit_passed=True,
            console_helpers_exited=True,
            shutdown_seconds=round(time.monotonic() - started, 3),
        )
    finally:
        for process in [actual_host, owned, *helpers]:
            if process is not None and process.is_running():
                process.terminate()
                process.wait(timeout=5)
        if host.poll() is None:
            host.terminate()
            host.wait(timeout=5)
        reader.join(timeout=2)
        host.stdin.close()
        host.stdout.close()
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

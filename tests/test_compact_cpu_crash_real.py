"""Opt-in Windows kernel containment proof with the actual repo-local model."""

import json
import os
import subprocess
import sys
import time
from queue import Queue
from threading import Thread

import psutil
import pytest

from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


@pytest.mark.skipif(
    os.name != "nt" or os.environ.get("MFL_RUN_COMPACT_CPU_API_PROOF") != "1",
    reason=(
        "Explicit Windows real-model crash drill; requires repo-local artifacts "
        "and 4 GiB available RAM"
    ),
)
def test_windows_stops_owned_native_worker_when_host_is_terminated():
    script = """
import json, os
from legal.fast_interchange.compact_cpu import CompactCpuWorker, pinned_inventory
from scripts.acquire_compact_model_candidates import OUTPUT
files=pinned_inventory(OUTPUT/'qwen3-compact-comparison','acquisition.json')
model=next(r for r in files if r.path.suffix=='.gguf')
engine=pinned_inventory(OUTPUT/'cpu-runtime','engine-inventory.json')
worker=CompactCpuWorker(model=model,engine=engine,
    scratch=OUTPUT/'scratch',research_only=True)
try:
    worker.start()
    row={'pid':worker._process.pid,'host_pid':os.getpid(),
         'kernel_job_active':worker._job is not None}
    print(json.dumps(row),flush=True)
    input()
finally:
    worker.close()
"""
    report = {"fictional_only": True, "test": "actual_host_termination", "ga_ready": False}
    environment = dict(os.environ)
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        environment[key] = str(OUTPUT / "scratch")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    host = subprocess.Popen(
        [sys.executable, "-B", "-c", script],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    lines = Queue()
    reader = Thread(target=lambda: lines.put(host.stdout.readline()), daemon=True)
    reader.start()
    owned_model = None
    actual_host = None
    try:
        row = json.loads(lines.get(timeout=70))
        assert row["kernel_job_active"] is True
        owned_model = psutil.Process(row["pid"])
        actual_host = psutil.Process(row["host_pid"])
        assert actual_host.pid == host.pid or host.pid in {p.pid for p in actual_host.parents()}
        assert owned_model.ppid() == actual_host.pid
        assert (
            owned_model.exe().casefold() == str(OUTPUT / "cpu-runtime/llama-server.exe").casefold()
        )
        started = time.monotonic()
        # Kill only the disposable host just created by this test. Unlike a
        # graceful close, this cannot run the worker's Python finally block.
        # Windows venv python.exe can be a redirector with a child interpreter.
        # Terminate the verified interpreter that owns the kernel job, not just
        # its launcher. Both identities come from this test's private stdout.
        actual_host.terminate()
        actual_host.wait(timeout=5)
        host.wait(timeout=5)
        owned_model.wait(timeout=5)
        report.update(
            kernel_job_active=True,
            owned_worker_exited=True,
            shutdown_seconds=round(time.monotonic() - started, 3),
        )
    finally:
        if actual_host is not None and actual_host.is_running():
            actual_host.terminate()
            actual_host.wait(timeout=5)
        if host.poll() is None:
            host.terminate()
            host.wait(timeout=5)
        if owned_model is not None and owned_model.is_running():
            # Same psutil process identity, never a broad name/PID search.
            owned_model.terminate()
            owned_model.wait(timeout=5)
        reader.join(timeout=2)
        for stream in (host.stdin, host.stdout, host.stderr):
            stream.close()
        (OUTPUT / "native-crash-containment-01.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )

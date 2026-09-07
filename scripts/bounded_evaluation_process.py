"""Run one owned evaluator with a timeout and bounded, in-memory output tail."""

from __future__ import annotations

import os
import signal
import subprocess
import threading


def run_bounded(command, *, cwd, env, timeout_seconds, tail_bytes=8192):
    if timeout_seconds <= 0 or not 1 <= tail_bytes <= 65536:
        raise ValueError("evaluation_process_limits_invalid")
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **options
    )
    tail = bytearray()
    lock = threading.Lock()

    def drain():
        while chunk := process.stdout.read(4096):
            with lock:
                tail.extend(chunk)
                del tail[:-tail_bytes]

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = False
    cleanup_failed = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        if process.poll() is None:
            try:
                if os.name == "nt":
                    killed = subprocess.run(
                        ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        env=env,
                    )
                    cleanup_failed = killed.returncode != 0
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except (OSError, subprocess.TimeoutExpired):
                cleanup_failed = True
                process.kill()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cleanup_failed = True
        reader.join(timeout=2)
        if reader.is_alive():
            cleanup_failed = True
        else:
            process.stdout.close()
    with lock:
        output = bytes(tail).decode("utf-8", errors="replace")
    return {
        "returncode": process.returncode,
        "timed_out": timed_out,
        "cleanup_failed": cleanup_failed,
        "output_tail": output,
    }

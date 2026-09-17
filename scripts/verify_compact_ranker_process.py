"""Real resident-ranker lifecycle proof; not legal quality or desktop acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from threading import Event, Thread

import psutil

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


def data(matter="fictional-ranker-a"):
    return [
        {
            "source_id": f"fictional-{index}",
            "matter_id": matter,
            "lane": "private_record",
            "text": text,
        }
        for index, text in enumerate(
            [
                "The fictional message says the promised invoice attachment is missing.",
                "A fictional register records a meeting on Friday.",
                "The fictional envelope has a green border.",
            ]
        )
    ]


def execute(name):
    if re.fullmatch(r"ranker-process-real-[a-z0-9-]+\.json", name) is None:
        raise ValueError("repository_evidence_path_required")
    output = OUTPUT / name
    if output.exists():
        raise ValueError("preserve_prior_evidence")
    worker = IsolatedCompactRanker(
        pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    report = {
        "schema_version": "compact_ranker_process_proof_v1",
        "fictional_only": True,
        "level": "actual_isolated_research_weights",
        "production_admitted": False,
        "canonical_api_tested": False,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "ga_ready": False,
        "quality_qualified": False,
        "errors": [],
        "actions": [],
        "implementation": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in (
                "legal/fast_interchange/compact_ranker_process.py",
                "legal/fast_interchange/compact_ranker_worker.py",
                "legal/fast_interchange/compact_reranker.py",
                "scripts/verify_compact_ranker_process.py",
            )
        },
    }
    try:
        started = time.monotonic()
        report["warm"] = worker.warm()
        report["warm_seconds"] = round(time.monotonic() - started, 3)
        identity = psutil.Process(worker._process.pid)
        report["kernel_job_active"] = worker._job is not None
        report["ownership"] = {
            "worker_pid": identity.pid,
            "reported_parent_pid": identity.ppid(),
            "host_pid": psutil.Process().pid,
            "children": [
                {"pid": p.pid, "status": p.status(), "name": p.name()}
                for p in identity.children(recursive=True)
            ],
        }
        assert identity.ppid() == psutil.Process().pid
        import win32job

        report["job_processes"] = win32job.QueryInformationJobObject(
            worker._job.handle, win32job.JobObjectBasicProcessIdList
        )
        helpers = identity.children(recursive=True)
        # Windows may place its headless console host in the job as a system
        # helper. It is not another model worker; verify its exact system path.
        for helper in helpers:
            assert (
                Path(helper.exe()).resolve()
                == Path(os.environ["SYSTEMROOT"]) / "System32" / "conhost.exe"
            )
        assert set(report["job_processes"]) == {identity.pid, *(p.pid for p in helpers)}
        print(
            json.dumps({"warm_seconds": report["warm_seconds"], "kernel_job_active": True}),
            flush=True,
        )
        query = "Where does the record describe the missing invoice attachment?"
        first = None
        for label, matter, question in (
            ("A", "fictional-ranker-a", query),
            ("B", "fictional-ranker-b", "Which passage records the meeting date?"),
            ("A-again", "fictional-ranker-a", query),
        ):
            started = time.monotonic()
            rows = worker.rank(query=question, passages=data(matter), matter_id=matter)
            assert rows[0]["source_index"] == (1 if label == "B" else 0)
            if first is None:
                first = rows
            if label == "A-again":
                assert rows == first
            report["actions"].append(
                {"label": label, "rankings": rows, "seconds": round(time.monotonic() - started, 3)}
            )
        assert worker.worker_starts == 1
        # No mutation is attempted: requesting a write handle must be refused
        # while the real artifact is held under the model's read-only lock.
        import win32con
        import win32file

        weights = next(row.path for row in worker.files if row.path.suffix == ".safetensors")
        try:
            handle = win32file.CreateFile(
                str(weights),
                win32con.GENERIC_WRITE,
                win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
                None,
                win32con.OPEN_EXISTING,
                0,
                None,
            )
        except Exception as exc:
            assert getattr(exc, "winerror", None) == 32
            report["live_model_write_handle_denied"] = True
        else:
            handle.Close()
            raise AssertionError("live model was not locked")

        # Cancel a real ranking request after CPU work is observed in its child.
        entries = [
            {
                "source_id": f"fictional-long-{i}",
                "matter_id": "fictional-ranker-a",
                "lane": "private_record",
                "text": "A fictional invoice is missing its attachment. " * 28,
            }
            for i in range(32)
        ]
        outcome, started = [], time.monotonic()
        cpu_before = sum(identity.cpu_times()[:2])

        def invoke():
            try:
                worker.rank(query=query, passages=entries, matter_id="fictional-ranker-a")
                outcome.append("completed_before_cancel")
            except LocalModelError as exc:
                outcome.append(exc.code)

        thread = Thread(target=invoke, daemon=True)
        thread.start()
        observed = False
        while thread.is_alive() and time.monotonic() - started < 5:
            if sum(identity.cpu_times()[:2]) - cpu_before >= 0.06:
                observed = True
                break
            Event().wait(0.01)
        worker.cancel()
        thread.join(timeout=8)
        report["cancel"] = {
            "outcome": outcome,
            "ranking_cpu_observed": observed,
            "thread_drained": not thread.is_alive(),
            "worker_stopped": worker._process is None,
        }
        assert observed and outcome == ["fast_interchange_generation_canceled"]
        assert not thread.is_alive() and worker._process is None
        identity.wait(timeout=5)
        for helper in helpers:
            helper.wait(timeout=5)
        report["cancel"]["worker_and_console_exit_wait_passed"] = True
        worker.rank(query=query, passages=data(), matter_id="fictional-ranker-a")
        assert worker.worker_starts == 2
        report["restart_passed"] = True
        report["lifecycle_passed"] = True
    except Exception as exc:
        report["errors"].append(
            {"type": type(exc).__name__, "code": getattr(exc, "code", "proof_failed")}
        )
    finally:
        worker.close()
        report["clean_shutdown"] = worker._process is None
        report["peak_resident_bytes"] = worker.peak_resident_bytes
        report["peak_private_bytes"] = worker.peak_private_bytes
        report["completed_requests"] = worker.completed_requests
        report["last_exit_code"] = worker.last_exit_code
        report["worker_failure"] = worker.last_failure
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report), flush=True)
    return not report["errors"] and report.get("lifecycle_passed") is True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-name", required=True)
    raise SystemExit(0 if execute(parser.parse_args().output_name) else 1)

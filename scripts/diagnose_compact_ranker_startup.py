"""Bounded, serial research cold-start measurements using the real isolated worker.

The opt-in child instrumentation writes only fixed phase names and elapsed time.
No records, prompts, arbitrary exception messages or import paths are logged.
No runtime/model copy, factory registration, admission or timeout change occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import psutil

from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranker_process import ERROR_PHASES, IsolatedCompactRanker
from legal.security.strict_json import strict_json_loads
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT, local_path

TRACE_PHASES = ERROR_PHASES | {
    "import_torch_begin",
    "import_torch_end",
    "import_transformers_begin",
    "import_transformers_end",
}


def phase_instrumentation(path, overlay=None):
    # A constant-owned QA filename, never a client-supplied path or record name.
    path = local_path(path.parent, path.name)
    prefix = ""
    if overlay is not None:
        prefix = (
            f"sys.path.insert(0, {str(overlay)!r})\n"
            "import importlib.util\n"
            "assert importlib.util.find_spec('transformers').origin == "
            f"{str(overlay / 'transformers/__init__.py')!r}\n"
        )
    return prefix + (
        "import builtins,json,re,time\n"
        "from legal.fast_interchange.compact_ranker_worker import CompactPassageReranker\n"
        f"_phase_file = open({str(path)!r}, 'x', encoding='utf-8')\n"
        "_phase_start = time.perf_counter()\n"
        "_phase_count = 0\n"
        "def _emit_phase(value):\n"
        "    global _phase_count\n"
        f"    if value in {tuple(sorted(TRACE_PHASES))!r} and _phase_count < 64:\n"
        "        _phase_count += 1\n"
        "        row = {'phase':value,'seconds':round(time.perf_counter()-_phase_start,6)}\n"
        "        _phase_file.write(json.dumps(row)+'\\n')\n"
        "        _phase_file.flush()\n"
        "_original_setattr = CompactPassageReranker.__setattr__\n"
        "def _measured_setattr(self, name, value):\n"
        "    _original_setattr(self, name, value)\n"
        "    if name == 'phase': _emit_phase(value)\n"
        "CompactPassageReranker.__setattr__ = _measured_setattr\n"
        "_original_warm = CompactPassageReranker.warm\n"
        "def _measured_warm(self):\n"
        "    try: return _original_warm(self)\n"
        "    except Exception as error:\n"
        "        detail = {}\n"
        "        for _ in range(6):\n"
        "            module = getattr(error, 'name', None)\n"
        "            if isinstance(module, str) and "
        "re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,159}', module):\n"
        "                detail = {'import_symbol':'unspecified', 'import_module':module}\n"
        "            error = error.__cause__\n"
        "            if error is None: break\n"
        "        if detail:\n"
        "            detail.update(phase='runtime_import',"
        "seconds=round(time.perf_counter()-_phase_start,6))\n"
        "            _phase_file.write(json.dumps(detail)+'\\n'); _phase_file.flush()\n"
        "        raise\n"
        "CompactPassageReranker.warm = _measured_warm\n"
        "_original_import = builtins.__import__\n"
        "def _measured_import(name, globals=None, locals=None, fromlist=(), level=0):\n"
        "    caller = (globals or {}).get('__name__')\n"
        "    selected = caller == 'legal.fast_interchange.compact_reranker'\n"
        "    selected = selected and name in {'torch', 'transformers'}\n"
        "    if selected: _emit_phase('import_' + name + '_begin')\n"
        "    try: return _original_import(name, globals, locals, fromlist, level)\n"
        "    finally:\n"
        "        if selected: _emit_phase('import_' + name + '_end')\n"
        "builtins.__import__ = _measured_import\n"
    )


@contextmanager
def measured_child(path, overlay=None):
    original = subprocess.Popen
    marker = "from legal.fast_interchange.compact_ranker_worker import main;"

    def launch(command, *args, **kwargs):
        index = command.index("-c") + 1 if isinstance(command, list) and "-c" in command else -1
        if 0 <= index < len(command) and marker in command[index]:
            command = list(command)
            command[index] = command[index].replace(
                "raise SystemExit(main())",
                f"exec({phase_instrumentation(path, overlay)!r});raise SystemExit(main())",
            )
        return original(command, *args, **kwargs)

    subprocess.Popen = launch
    try:
        yield
    finally:
        subprocess.Popen = original


def read_phases(path):
    path = local_path(path.parent, path.name)
    if not path.exists():
        return []
    if path.stat().st_size > 16384:
        raise ValueError("startup_trace_budget_exceeded")
    rows = [
        strict_json_loads(line, max_bytes=1024, require_object=True)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    if len(rows) > 64:
        raise ValueError("startup_trace_budget_exceeded")
    previous = 0
    for row in rows:
        if (
            set(row)
            not in ({"phase", "seconds"}, {"phase", "seconds", "import_symbol", "import_module"})
            or row["phase"] not in TRACE_PHASES
            or type(row["seconds"]) not in (int, float)
            or not previous <= row["seconds"] <= 600
        ):
            raise ValueError("startup_trace_invalid")
        if "import_symbol" in row and any(
            not isinstance(row[key], str)
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,159}", row[key]) is None
            for key in ("import_symbol", "import_module")
        ):
            raise ValueError("startup_trace_invalid")
        previous = row["seconds"]
    return rows


def execute(run_id, repeats=2, *, bert_overlay=False):
    if (
        not isinstance(run_id, str)
        or re.fullmatch(r"[a-z0-9-]{1,24}", run_id) is None
        or type(repeats) is not int
        or not 1 <= repeats <= 3
    ):
        raise ValueError("startup_diagnostic_bounds_invalid")
    target = local_path(OUTPUT, f"ranker-startup-{run_id}.json")
    traces = [local_path(OUTPUT, f"ranker-startup-{run_id}-{i}.jsonl") for i in range(repeats)]
    if target.exists() or any(p.exists() for p in traces):
        raise ValueError("preserve_prior_evidence")
    report = {
        "schema": "compact_ranker_serial_startup_v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "diagnostic_child_instrumentation": True,
        "fixture": "fictional_only",
        "production_admitted": False,
        "ga_ready": False,
        "frozen_tested": False,
        "os_disk_cache_flushed": False,
        "cold_load_deadline_seconds": 90,
        "timer": "perf_counter",
        "timer_resolution_seconds": time.get_clock_info("perf_counter").resolution,
        "implementation": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_reranker.py",
                "legal/fast_interchange/compact_ranker_process.py",
                "legal/fast_interchange/compact_ranker_worker.py",
                "scripts/diagnose_compact_ranker_startup.py",
            )
        },
        "runs": [],
    }
    files = pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json")
    overlay = None
    if bert_overlay:
        from scripts.prepare_compact_bert_overlay import DIRECTORY, MANIFEST_NAME, verify

        verified_at = time.perf_counter()
        selection = verify()
        overlay = DIRECTORY
        report["research_overlay"] = {
            "bytes": selection["bytes"],
            "manifest_sha256": hashlib.sha256((DIRECTORY / MANIFEST_NAME).read_bytes()).hexdigest(),
            "not_production_admitted": True,
            "preflight_verification_seconds": round(time.perf_counter() - verified_at, 6),
        }
    report["model_inventory"] = [
        {"name": f.path.name, "bytes": f.bytes, "sha256": f.sha256} for f in files
    ]
    for trace in traces:
        worker = IsolatedCompactRanker(files, scratch=OUTPUT / "scratch", research_only=True)
        row = {"available_ram_before_bytes": psutil.virtual_memory().available}
        started = time.perf_counter()
        try:
            with measured_child(trace, overlay):
                worker.warm()
                row["warm_seconds"] = round(time.perf_counter() - started, 6)
                ranked_at = time.perf_counter()
                ranks = worker.rank(
                    query="Which passage reports a missing attachment?",
                    matter_id="fictional-startup",
                    passages=[
                        {
                            "source_id": "fictional-one",
                            "matter_id": "fictional-startup",
                            "lane": "private_record",
                            "text": "The fictional message reports a missing invoice attachment.",
                        }
                    ],
                )
                row["rank_seconds"] = round(time.perf_counter() - ranked_at, 6)
                assert ranks[0]["source_index"] == 0
                row["completed"] = True
        except Exception as error:
            row["failure_code"] = getattr(error, "code", "diagnostic_failed")
            row["worker_failure"] = worker.last_failure
            row["completed"] = False
        finally:
            try:
                worker.close()
            except Exception:
                row.update(completed=False, cleanup_failed=True)
            try:
                phases = read_phases(trace)
                if not phases:
                    raise ValueError("startup_trace_missing")
            except (OSError, ValueError, TypeError, KeyError):
                phases = []
                row.update(completed=False, trace_invalid=True)
            row.update(
                duration_seconds=round(time.perf_counter() - started, 6),
                peak_resident_bytes=worker.peak_resident_bytes,
                owned_worker_stopped=worker._process is None,
                trace=trace.name,
                phases=phases,
            )
            report["runs"].append(row)
            # Final report is written only once after all bounded runs.
            print(json.dumps(row), flush=True)
        if not row["completed"]:
            break
    report["all_completed"] = len(report["runs"]) == repeats and all(
        r["completed"] and r["owned_worker_stopped"] for r in report["runs"]
    )
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report["all_completed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--bert-overlay", action="store_true")
    options = parser.parse_args()
    raise SystemExit(
        0 if execute(options.run_id, options.repeats, bert_overlay=options.bert_overlay) else 1
    )

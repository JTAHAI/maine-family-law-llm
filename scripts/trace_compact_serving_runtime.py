"""Observe the fixed research reader's actual imports/data/native mappings.

Tracing is not enforcement, a complete dependency closure, or release admission.
Only fictional requests are sent, through the existing owned isolated worker.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
sys.path.insert(0, str(ROOT))

import psutil  # noqa: E402

from legal.fast_interchange.compact_cpu import pinned_inventory  # noqa: E402
from legal.fast_interchange.compact_span_process import IsolatedSpanReader  # noqa: E402
from legal.fast_interchange.compact_span_reader import CompactSpanReader  # noqa: E402


def logical_file(path, roots):
    if not isinstance(path, str) or not path or path.startswith("<"):
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    for label, root in sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True):
        try:
            return label + "/" + candidate.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return "unmapped/" + hashlib.sha256(str(candidate).encode()).hexdigest()


class TracingReader(CompactSpanReader):
    run_id = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._opened = set()
        self._recording = True
        self._trace_stage = 0
        sys.addaudithook(self._capture_open)

    def _capture_open(self, event, arguments):
        if self._recording and event == "open" and arguments and isinstance(arguments[0], str):
            if len(self._opened) >= 16_384:
                raise ValueError("compact_trace_file_budget")
            self._opened.add(arguments[0])

    def extract(self, **kwargs):
        rows = super().extract(**kwargs)
        self._recording = False
        try:
            self._trace_stage += 1
            import os

            roots = dict(
                package_runtime=Path(sys.argv[1]).parents[1],
                python_runtime=Path(sys.base_prefix),
                repository=ROOT,
                model=OUT / "minilm-span-reader",
                windows=Path(os.environ["SYSTEMROOT"]),
            )
            modules = sorted(
                {
                    logical_file(getattr(module, "__file__", None), roots)
                    for module in tuple(sys.modules.values())
                }
                - {None}
            )
            opened = sorted({logical_file(p, roots) for p in self._opened} - {None})
            native = sorted(
                {logical_file(m.path, roots) for m in psutil.Process().memory_maps()} - {None}
            )
            target = OUT / f"serving-trace-{self.run_id}-{self._trace_stage}.json"
            with target.open("x", encoding="utf-8") as stream:
                json.dump(
                    dict(
                        schema="compact_observed_runtime_trace_v1",
                        stage=self._trace_stage,
                        modules=modules,
                        opened=opened,
                        native_mappings=native,
                        observed_only=True,
                        native_closure_qualified=False,
                        production_admitted=False,
                    ),
                    stream,
                    indent=2,
                )
        finally:
            self._recording = True
        return rows


class TraceWorker(IsolatedSpanReader):
    def __init__(self, *args, run_id, **kwargs):
        self.run_id = run_id
        super().__init__(*args, **kwargs)

    def _bootstrap(self):
        # Keep the existing isolation/bootstrap; replace only the fixed engine.
        bootstrap = super()._bootstrap()
        return bootstrap.replace(
            "from legal.fast_interchange.compact_span_reader import CompactSpanReader;",
            "from scripts.trace_compact_serving_runtime import TracingReader as CompactSpanReader;"
            + f"CompactSpanReader.run_id={self.run_id!r};",
        )


def execute(run_id):
    if re.fullmatch(r"[a-z0-9]{1,16}", run_id) is None:
        raise ValueError("invalid_run_id")
    target = OUT / f"serving-trace-{run_id}-summary.json"
    if target.exists() or list(OUT.glob(f"serving-trace-{run_id}-*.json")):
        raise ValueError("preserve_prior_evidence")
    worker = TraceWorker(
        pinned_inventory(OUT / "minilm-span-reader", "acquisition.json"),
        scratch=OUT / "runtime-trace-scratch",
        research_only=True,
        run_id=run_id,
    )
    start = time.monotonic()
    report = dict(
        schema="compact_runtime_trace_run_v1",
        passed=False,
        observed_only=True,
        ga_ready=False,
        production_admitted=False,
        model_copy_bytes=0,
        downloads=0,
        cases=[],
    )
    try:
        for question, text in (
            ("What time did the meeting begin?", "The fictional meeting began at 09:25."),
            ("How much was paid?", "The fictional receipt records that 92 dollars was paid."),
        ):
            rows = worker.extract(
                query=question,
                matter_id="fictional-runtime-trace",
                passages=[
                    dict(
                        source_id="fictional-source",
                        lane="private_record",
                        matter_id="fictional-runtime-trace",
                        text=text,
                    )
                ],
            )
            report["cases"].append(dict(question=question, result=rows))
        traces = sorted(OUT.glob(f"serving-trace-{run_id}-[123].json"))
        if len(traces) != 3:
            raise ValueError("trace_stages_missing")
        report.update(
            passed=True,
            real_requests=2,
            warm_forward_passes=1,
            trace_files=[p.name for p in traces],
            peak_resident_bytes=worker.peak_resident_bytes,
            worker_starts=worker.worker_starts,
        )
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        report["failure_code"] = getattr(exc, "code", "runtime_trace_failed")
    finally:
        worker.close()
        report["worker_stopped"] = worker._process is None
        report["duration_seconds"] = round(time.monotonic() - start, 3)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    raise SystemExit(execute(parser.parse_args().run_id))

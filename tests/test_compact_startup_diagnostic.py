import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import diagnose_compact_ranker_startup as diagnostic
from scripts import acquire_compact_model_candidates as candidates


@pytest.fixture
def synthetic_repository(tmp_path, monkeypatch):
    """Give the diagnostic a disposable repository whose only output is dist.

    Production helpers deliberately reject arbitrary output folders.  These
    tests need to exercise that same guard with a purpose-built fixture root,
    not bypass it by pointing a guarded writer at pytest's raw temporary root.
    """
    monkeypatch.setattr(candidates, "ROOT", tmp_path)
    output = tmp_path / "dist" / "diagnostic"
    monkeypatch.setattr(diagnostic, "OUTPUT", output)
    return output


@pytest.mark.parametrize(
    "run_id,repeats", [("../escape", 1), ("ok", 0), ("ok", 4), ("ok", True), (None, 1)]
)
def test_invalid_bounds_do_not_start_a_worker(run_id, repeats):
    with pytest.raises(ValueError, match="startup_diagnostic_bounds_invalid"):
        diagnostic.execute(run_id, repeats)


def test_prior_trace_is_preserved_without_launch(synthetic_repository):
    target = synthetic_repository / "ranker-startup-old-0.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("old evidence")
    with pytest.raises(ValueError, match="preserve_prior_evidence"):
        diagnostic.execute("old")
    assert target.read_text() == "old evidence"


@pytest.mark.parametrize(
    "raw",
    [
        '{"phase":"secret-record-text","seconds":1}',
        '{"phase":"warm","seconds":-1}',
        '{"phase":"warm","seconds":NaN}',
        '{"phase":"warm","seconds":1,"seconds":2}',
        '{"phase":"warm","seconds":true}',
        '{"phase":"warm","seconds":1,"extra":"private"}',
        '{"phase":"warm","seconds":1}\n{"phase":"warm","seconds":0}',
    ],
)
def test_trace_refuses_unbounded_or_untrusted_fields(tmp_path, raw):
    path = tmp_path / "trace.jsonl"
    path.write_text(raw)
    with pytest.raises(ValueError):
        diagnostic.read_phases(path)


@pytest.mark.parametrize("site_flag", [[], ["-S"]])
def test_instrumentation_changes_only_owned_worker_and_restores_on_error(
    synthetic_repository, monkeypatch, site_flag
):
    synthetic_repository.mkdir(parents=True)
    calls = []

    def original(command, *args, **kwargs):
        calls.append(command)
        return "child"

    monkeypatch.setattr(subprocess, "Popen", original)
    command = [
        "python",
        "-I",
        *site_flag,
        "-B",
        "-c",
        "from legal.fast_interchange.compact_ranker_worker import main;raise SystemExit(main())",
    ]
    with pytest.raises(RuntimeError):
        with diagnostic.measured_child(synthetic_repository / "trace.jsonl"):
            subprocess.Popen(["unrelated-program"])
            subprocess.Popen(command)
            raise RuntimeError("fixture failure")
    assert subprocess.Popen is original
    assert calls[0] == ["unrelated-program"]
    index = command.index("-c") + 1
    assert "_measured_setattr" in calls[1][index]
    assert "_measured_setattr" not in command[index]
    compile(calls[1][index], "fixture", "exec")


@pytest.mark.parametrize("fault", [None, "load", "close", "trace"])
def test_evidence_remains_non_ga_and_survives_failure(synthetic_repository, monkeypatch, fault):
    monkeypatch.setattr(diagnostic, "pinned_inventory", lambda *args: ())
    original_phase = [{"phase": "warm", "seconds": 0.012}]
    synthetic_repository.mkdir(parents=True)
    (synthetic_repository / "pending.json").write_text("fixture")

    class Worker:
        _process = None
        peak_resident_bytes = 1
        last_failure = None

        def __init__(self, *args, **kwargs):
            pass

        def warm(self):
            trace = synthetic_repository / "ranker-startup-test-0.jsonl"
            trace.write_text("bad" if fault == "trace" else json.dumps(original_phase[0]) + "\n")
            if fault == "load":
                raise ValueError("private exception must not be reported")

        def rank(self, **kwargs):
            return [{"source_index": 0}]

        def close(self):
            if fault == "close":
                raise ValueError("private cleanup error")

    monkeypatch.setattr(diagnostic, "IsolatedCompactRanker", Worker)
    monkeypatch.setattr(diagnostic.psutil, "virtual_memory", lambda: SimpleNamespace(available=10))
    assert diagnostic.execute("test", 1) is (fault is None)
    result = json.loads((synthetic_repository / "ranker-startup-test.json").read_text())
    assert result["ga_ready"] is result["production_admitted"] is False
    assert result["cold_load_deadline_seconds"] == 90
    assert "private exception" not in json.dumps(result)
    assert "private cleanup" not in json.dumps(result)
    assert len(result["runs"]) == 1

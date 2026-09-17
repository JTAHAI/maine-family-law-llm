"""Python audit-event denial only; these tests cannot establish an OS sandbox."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_compact_ranker_process import exchange_fixture, response, worker

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.admission import canonical

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "action",
    [
        "socket.socket()",
        "socket.getaddrinfo('fictional.invalid', 443)",
        "socket.gethostbyname('fictional.invalid')",
        "socket.gethostbyaddr('192.0.2.1')",
        "socket.getnameinfo(('192.0.2.1', 443), 0)",
        "prior.connect(('127.0.0.1', 1))",
        "prior.sendto(b'fictional canary', ('192.0.2.1', 443))",
        "urllib.request.urlopen('https://fictional.invalid/private-canary')",
        "http.client.HTTPConnection('fictional.invalid').connect()",
    ],
)
def test_actual_python_network_calls_denied_without_private_details(tmp_path, action):
    code = f"""
import sys,socket,urllib.request,http.client,json
sys.path.insert(0,{str(ROOT)!r})
from legal.fast_interchange.compact_network_guard import PythonNetworkGuard,PythonNetworkDenied
prior=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
guard=PythonNetworkGuard()
try:
    {action}
except PythonNetworkDenied as error:
    assert str(error)=='compact_python_network_denied'
else:
    raise AssertionError('network operation was not denied')
finally:
    prior.close()
assert guard.denied
try:
    guard.check()
except PythonNetworkDenied:
    print(json.dumps({{'denied':True,'sticky':True,'os_isolation_proven':False}}))
else:
    raise AssertionError('caught denial must still discard the run')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=ROOT,
        env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "denied": True,
        "sticky": True,
        "os_isolation_proven": False,
    }
    assert "fictional.invalid" not in result.stdout + result.stderr
    assert "private-canary" not in result.stdout + result.stderr


def test_silently_refused_hook_fails_closed(tmp_path):
    code = f"""
import sys
sys.path.insert(0,{str(ROOT)!r})
from legal.fast_interchange.compact_network_guard import PythonNetworkGuard
def existing(event,args):
    if event=='sys.addaudithook': raise RuntimeError('refused')
sys.addaudithook(existing)
try:
    PythonNetworkGuard()
except RuntimeError as error:
    assert str(error)=='compact_network_guard_unavailable'
else:
    raise AssertionError('missing hook must fail closed')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=ROOT,
        env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_pipe_denial_maps_to_safe_error_and_stops_worker(tmp_path, monkeypatch):
    error = {
        "phase": "warm",
        "kind": "PythonNetworkDenied",
        "winerror": None,
        "module": "private-canary",
    }
    engine, stops = exchange_fixture(
        tmp_path, monkeypatch, canonical(response(ok=False, result=error)) + b"\n"
    )
    with pytest.raises(LocalModelError) as caught:
        engine._exchange("rank", {})
    assert caught.value.code == "fast_interchange_compact_python_network_denied"
    assert stops and engine.last_failure["module"] == "unspecified"


@pytest.mark.parametrize("guard", [None, "os_sandbox_verified", "old_guard"])
def test_warm_ack_must_confirm_exact_python_tripwire(tmp_path, monkeypatch, guard):
    engine = worker(tmp_path)
    result = {
        "status": "warm",
        "forward_passes": 1,
        "model_sha256": "a" * 64,
        "review_required": True,
        "production_admitted": False,
        "source_import_policy": "compact_source_only_v1",
    }
    if guard is not None:
        result["network_guard"] = guard
    stops = []
    monkeypatch.setattr(engine, "_start", lambda: None)
    monkeypatch.setattr(engine, "_exchange", lambda *args, **kw: result)
    monkeypatch.setattr(engine, "_stop", lambda: stops.append(True))
    with pytest.raises(LocalModelError) as caught:
        engine._ensure_warm()
    assert caught.value.code == "fast_interchange_reranker_warm_invalid"
    assert stops and not engine._warm


def inject_caught_worker_network_attempt(monkeypatch):
    """Test-only dependency fault inside the real isolated child; never production.

    The first warm substitutes a caught DNS call for the model's rank method.
    Guard/protocol/parent/API remain real. Disable the fault before actual model
    inference; never describe the fault response as a model forward pass.
    """
    state = {"enabled": True, "injections": 0}
    original = subprocess.Popen
    fault = (
        "import socket\n"
        "from legal.fast_interchange.compact_ranker_worker import CompactPassageReranker\n"
        "def faulty_rank(self, **kwargs):\n"
        "    try: socket.getaddrinfo('fictional.invalid', 443)\n"
        "    except RuntimeError: pass\n"
        "    return []\n"
        "CompactPassageReranker.rank = faulty_rank\n"
    )

    def launch(command, *args, **kwargs):
        index = command.index("-c") + 1 if isinstance(command, list) and "-c" in command else -1
        if (
            state["enabled"]
            and 0 <= index < len(command)
            and "from legal.fast_interchange.compact_ranker_worker import main;" in command[index]
        ):
            command = list(command)
            command[index] = command[index].replace(
                "raise SystemExit(main())", f"exec({fault!r});raise SystemExit(main())"
            )
            state["injections"] += 1
        return original(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    return state

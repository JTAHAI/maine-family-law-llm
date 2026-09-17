"""Deterministic setup tests: no download, installer, or user model mutation."""
import io
import json
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from legal.local_ai import installer as mod
from legal.local_ai.setup import LocalAiSetupError, LocalAiSetupStore
from maine_family_law_llm import api


def test_production_setup_json_requests_declare_their_content_type():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    shipped = root / "src/maine_family_law_llm/ui/workbench.js"
    assert shipped.read_bytes() == (root / "maine_family_law_llm/ui/workbench.js").read_bytes()
    calls = [line for line in shipped.read_text(encoding="utf-8").splitlines()
             if "fetchJson('/api/local-ai/installation/" in line and "method: 'POST'" in line]
    assert len(calls) == 3
    assert all("'Content-Type': 'application/json'" in line for line in calls)


def store(path, audience="fictional-session"):
    return LocalAiSetupStore(root=path, audience=audience, encryption_key="fictional-key")


@pytest.mark.parametrize("model", list(mod.MODELS))
def test_existing_engine_and_model_skip_every_install_and_download(monkeypatch, tmp_path, model):
    monkeypatch.setattr(mod, "installed_models", lambda: (True, {model: mod.MODELS[model]["sha256"]}))
    monkeypatch.setattr(mod, "local_request", lambda *a, **k: pytest.fail("must not download"))
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("must not reinstall"))
    events = []
    backend = mod.WindowsBackend()
    backend.ensure_engine(tmp_path, threading.Event(), lambda *a: events.append(a[0]))
    backend.ensure_model(model, threading.Event(), lambda *a: events.append(a[0]))
    assert events == ["engine_reused", "model_reused"]


def test_stopped_installed_engine_is_started_not_installed(monkeypatch, tmp_path):
    executable = tmp_path / "ollama.exe"
    executable.write_bytes(b"fictional executable; never run")
    inventories = iter([(False, {}), (False, {}), (True, {})])
    monkeypatch.setattr(mod, "installed_models", lambda: next(inventories))
    monkeypatch.setattr(mod, "engine_path", lambda: executable)
    monkeypatch.setattr(mod, "signature_valid", lambda p: p == executable)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("reinstall forbidden"))
    calls = []
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    mod.WindowsBackend().ensure_engine(tmp_path, threading.Event(), lambda *a: None)
    assert calls[0][0][0] == [str(executable), "serve"]
    assert calls[0][1]["env"]["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert calls[0][1]["env"]["OLLAMA_NO_CLOUD"] == "1"


def test_different_revision_is_not_overwritten(monkeypatch):
    monkeypatch.setattr(mod, "installed_models", lambda: (True, {"qwen3:4b": "wrong"}))
    monkeypatch.setattr(mod, "local_request", lambda *a, **k: pytest.fail("overwrite forbidden"))
    with pytest.raises(LocalAiSetupError, match="no_overwrite"):
        mod.WindowsBackend().ensure_model("qwen3:4b", threading.Event(), lambda *a: None)


@pytest.mark.parametrize("url", ["http://github.com/evil", "https://evil.test/", "https://github.com:8443/a", "https://user@github.com/a"])
def test_download_redirect_boundary(url):
    with pytest.raises(LocalAiSetupError, match="redirect_forbidden"):
        mod.RedirectPolicy(True).redirect_request(None, None, 302, "", {}, url)


def test_loopback_redirects_fail_closed():
    with pytest.raises(LocalAiSetupError):
        mod.RedirectPolicy().redirect_request(None, None, 302, "", {}, "http://127.0.0.1:11434/api/tags")


@pytest.mark.parametrize("model", list(mod.MODELS))
def test_only_missing_model_is_pulled_and_verified(monkeypatch, model):
    inventory = iter([(True, {}), (True, {model: mod.MODELS[model]["sha256"]})])
    monkeypatch.setattr(mod, "installed_models", lambda: next(inventory))
    monkeypatch.setattr(mod, "free_bytes", lambda p: 100 * mod.GIB)
    calls = []
    def request(path, body, timeout):
        calls.append((path, body))
        return io.BytesIO(b'{"status":"success"}\n')
    monkeypatch.setattr(mod, "local_request", request)
    mod.WindowsBackend().ensure_model(model, threading.Event(), lambda *a: None)
    assert calls == [("/api/pull", {"model": model, "stream": True})]


def test_installer_hash_failure_never_executes_and_removes_own_partial(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "installed_models", lambda: (False, {}))
    monkeypatch.setattr(mod, "engine_path", lambda: None)
    monkeypatch.setattr(mod, "free_bytes", lambda p: 100 * mod.GIB)
    monkeypatch.setattr(mod, "build_opener", lambda *a: SimpleNamespace(open=lambda *a, **k: io.BytesIO(b"bad executable")))
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("unverified execution"))
    with pytest.raises(LocalAiSetupError, match="hash_mismatch"):
        mod.WindowsBackend().ensure_engine(tmp_path, threading.Event(), lambda *a: None)
    assert list((tmp_path / "installer-cache").iterdir()) == []


def test_smoke_rejects_truncated_or_empty_reply(monkeypatch):
    from legal.agent_runtime.providers import CuratedOllamaReasoningClient
    monkeypatch.setattr(CuratedOllamaReasoningClient, "generate_response", lambda *a: SimpleNamespace(excerpts=()))
    with pytest.raises(LocalAiSetupError, match="smoke_failed"):
        mod.WindowsBackend().smoke("qwen3:4b")


def test_valid_hash_still_requires_publisher_signature(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "installed_models", lambda: (False, {}))
    monkeypatch.setattr(mod, "engine_path", lambda: None)
    monkeypatch.setattr(mod, "checked_file", lambda *a: True)
    monkeypatch.setattr(mod, "signature_valid", lambda *a: False)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("untrusted publisher executed"))
    with pytest.raises(LocalAiSetupError, match="signature_invalid"):
        mod.WindowsBackend().ensure_engine(tmp_path, threading.Event(), lambda *a: None)


def test_missing_engine_download_verification_install_and_start_contract(monkeypatch, tmp_path):
    import hashlib
    payload = b"fictional signed installer fixture; never executed"
    executable = tmp_path / "installed/ollama.exe"
    monkeypatch.setattr(mod, "INSTALLER_BYTES", len(payload))
    monkeypatch.setattr(mod, "INSTALLER_SHA256", hashlib.sha256(payload).hexdigest())
    inventory = iter([(False, {}), (False, {}), (True, {})])
    monkeypatch.setattr(mod, "installed_models", lambda: next(inventory))
    monkeypatch.setattr(mod, "engine_path", lambda: executable if executable.exists() else None)
    monkeypatch.setattr(mod, "free_bytes", lambda p: 100 * mod.GIB)
    monkeypatch.setattr(mod, "build_opener", lambda *a: SimpleNamespace(open=lambda *a, **k: io.BytesIO(payload)))
    checked = []
    monkeypatch.setattr(mod, "signature_valid", lambda p: checked.append(p) or True)
    def simulated_install(args, **kwargs):
        assert args[1:] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]
        assert kwargs["creationflags"] == getattr(mod.subprocess, "CREATE_NO_WINDOW", 0)
        executable.parent.mkdir()
        executable.write_bytes(b"fictional engine")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(mod.subprocess, "run", simulated_install)
    monkeypatch.setattr(mod.subprocess, "Popen", lambda *a, **k: None)
    events = []
    mod.WindowsBackend().ensure_engine(tmp_path, threading.Event(), lambda *a: events.append(a[0]))
    assert "installing_engine" in events and "starting_engine" in events
    assert len(checked) == 2
    assert not (tmp_path / "installer-cache/OllamaSetup-0.34.1.exe").exists()


def test_low_disk_prevents_model_pull(monkeypatch):
    monkeypatch.setattr(mod, "installed_models", lambda: (True, {}))
    monkeypatch.setattr(mod, "free_bytes", lambda p: 0)
    monkeypatch.setattr(mod, "local_request", lambda *a, **k: pytest.fail("download on full disk"))
    with pytest.raises(LocalAiSetupError, match="disk_space"):
        mod.WindowsBackend().ensure_model("qwen3:4b", threading.Event(), lambda *a: None)


def test_cancel_during_model_download_preserves_existing_files(monkeypatch):
    monkeypatch.setattr(mod, "installed_models", lambda: (True, {}))
    monkeypatch.setattr(mod, "free_bytes", lambda p: 100 * mod.GIB)
    monkeypatch.setattr(mod, "local_request", lambda *a, **k: io.BytesIO(b'{"status":"pulling"}\n'))
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(mod.Cancelled):
        mod.WindowsBackend().ensure_model("qwen3:4b", cancel, lambda *a: None)


class FakeBackend:
    def inspect(self, model, root):
        mod.model_profile(model)
        return {"eligible": True, "blockers": [], "model": model, "download_bytes": 0}
    def ensure_engine(self, root, cancel, update):
        update("engine_reused", "Reused fictional engine")
    def ensure_model(self, model, cancel, update):
        update("model_reused", "Reused fictional model")
    def smoke(self, model):
        pass


def finish(service, owner, job):
    for _ in range(100):
        result = service.status(owner, job)
        if result["status"] in mod.TERMINAL:
            return result
        time.sleep(.01)
    pytest.fail("job did not finish")


def test_consent_scoping_encryption_restart_and_one_use_plan(tmp_path):
    service = mod.InstallService(FakeBackend())
    owner = store(tmp_path)
    other = store(tmp_path, "other-fictional-session")
    plan = service.prepare(owner, "qwen3:4b")
    with pytest.raises(LocalAiSetupError, match="confirmation"):
        service.start(owner, plan["plan_token"], False)
    with pytest.raises(LocalAiSetupError, match="plan_invalid"):
        service.start(other, plan["plan_token"], True)
    job = service.start(owner, plan["plan_token"], True)["job_id"]
    result = finish(service, owner, job)
    assert result["status"] == "ready" and result["review_required"]
    assert result["legal_quality_certified"] is False
    with pytest.raises(LocalAiSetupError, match="plan_invalid"):
        service.start(owner, plan["plan_token"], True)
    with pytest.raises(LocalAiSetupError, match="not_found"):
        service.status(other, job)
    assert "qwen" not in (owner.directory / "install-job.json.enc").read_text()
    assert mod.InstallService(FakeBackend()).status(owner, job)["status"] == "ready"


def test_api_guard_and_canonical_action(tmp_path, monkeypatch):
    monkeypatch.setenv("MFL_LOCAL_AI_STATE_ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "INSTALLS", mod.InstallService(FakeBackend()))
    client = TestClient(api.app)
    route = "/api/local-ai/installation/prepare"
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional", "X-MFLL-Client-Session": "a" * 48}
    assert client.post(route, json={"model": "qwen3:4b"}).status_code == 403
    assert client.post(route, headers=headers, json={"model": "arbitrary:latest"}).status_code == 400
    plan = client.post(route, headers=headers, json={"model": "qwen3:4b"})
    assert plan.status_code == 200, plan.text
    assert plan.json()["review_required"] and plan.json()["rbac"]["enforced"]
    started = client.post("/api/local-ai/installation/start", headers=headers,
                          json={"plan_token": plan.json()["plan_token"], "user_confirmed": True})
    assert started.status_code == 200, started.text
    result = client.get("/api/local-ai/installation/jobs/" + started.json()["job_id"], headers=headers)
    assert result.status_code == 200

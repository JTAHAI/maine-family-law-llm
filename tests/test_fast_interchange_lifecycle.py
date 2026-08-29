"""Real process/HTTP lifecycle with synthetic backends, not legal inference."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from test_fast_interchange_worker import _FakeBackend, _registry

from legal.agent_runtime.providers import FastInterchangeLocalClient, LocalModelError
from legal.fast_interchange.process_backend import IsolatedAdapterBackend
from legal.fast_interchange.worker import FastInterchangeError, HotSwapManager, create_worker_app


class SyntheticStuckBackend:
    """Importable spawn fixture: deliberately ignores cancellation during work."""

    def __init__(self, **_options):
        self.last = None

    def activate(self, *, release, **_kwargs):
        return {
            "release_id": release.release_id,
            "model_id": release.model_id,
            "release_fingerprint": release.release_fingerprint,
        }

    def complete(self, *, release, messages):
        if messages[0]["content"] == "stuck":
            time.sleep(15)  # Parent must actually terminate this owned child.
        if self.last is not None:
            raise AssertionError("prior request leaked")
        self.last = messages[0]["content"]
        return {
            "model": release.model_id,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Fictional output. Review required.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    def clear_context(self):
        self.last = None

    def close(self):
        self.last = None


def _release(registry):
    return registry.select("family-evidence-small-r1", allow_test_only=True)


def test_owned_process_is_killed_on_cancel_then_restarts_without_context(tmp_path):
    registry = _registry(tmp_path)
    release = _release(registry)
    backend = IsolatedAdapterBackend(factory=SyntheticStuckBackend, cancellation_grace_seconds=0.15)
    cancel = Event()
    backend.set_cancellation(cancel, time.monotonic() + 20)
    try:
        backend.activate(
            root=registry.root, binding=registry.bindings[release.release_id], release=release
        )
        first_pid = backend._process.pid
        with ThreadPoolExecutor(max_workers=1) as pool:
            work = pool.submit(
                backend.complete, release=release, messages=[{"role": "user", "content": "stuck"}]
            )
            cancel.set()
            started = time.monotonic()
            with pytest.raises(FastInterchangeError, match="generation_canceled"):
                work.result(timeout=5)
            assert time.monotonic() - started < 4
        assert backend._process is None
        backend.set_cancellation(Event(), time.monotonic() + 20)
        backend.activate(
            root=registry.root, binding=registry.bindings[release.release_id], release=release
        )
        assert backend._process.pid != first_pid
        for content in ("fictional-matter-A", "fictional-matter-B"):
            assert (
                backend.complete(release=release, messages=[{"role": "user", "content": content}])[
                    "model"
                ]
                == release.model_id
            )
    finally:
        backend.close()


def test_owned_process_has_hard_deadline_even_when_backend_ignores_it(tmp_path):
    registry = _registry(tmp_path)
    release = _release(registry)
    backend = IsolatedAdapterBackend(factory=SyntheticStuckBackend)
    try:
        backend.set_cancellation(Event(), time.monotonic() + 15)
        backend.activate(
            root=registry.root, binding=registry.bindings[release.release_id], release=release
        )
        backend.set_cancellation(Event(), time.monotonic() + 0.2)
        started = time.monotonic()
        with pytest.raises(FastInterchangeError, match="generation_timeout"):
            backend.complete(release=release, messages=[{"role": "user", "content": "stuck"}])
        assert time.monotonic() - started < 4
        assert backend._process is None
    finally:
        backend.close()


@pytest.fixture
def worker(tmp_path):
    registry = _registry(tmp_path)
    backend = _FakeBackend()
    manager = HotSwapManager(registry=registry, backend=backend, allow_test_only=True)
    token = uuid.uuid4().hex + uuid.uuid4().hex
    with TestClient(
        create_worker_app(
            manager=manager, registry=registry, worker_token=token, allow_test_only=True
        )
    ) as client:
        client.headers["Authorization"] = "Bearer " + token
        yield client, registry, manager, backend
    assert backend.closed


def fixed_request(registry):
    release = _release(registry)
    return {
        "model": release.model_id,
        "request_id": uuid.uuid4().hex,
        "capability": release.capability,
        "release_fingerprint": release.release_fingerprint,
    }


def generation(request):
    return {
        **request,
        "messages": [{"role": "user", "content": "Fictional source only."}],
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 1024,
    }


def test_reservation_cancel_replay_and_capability_binding(worker):
    client, registry, manager, _ = worker
    request = fixed_request(registry)
    assert client.post("/v1/requests/prepare", json=request).json()["status"] == "reserved"
    assert client.post("/v1/requests/prepare", json=request).status_code == 409
    assert (
        client.post("/v1/requests/cancel", json={"request_id": request["request_id"]}).json()[
            "status"
        ]
        == "canceled"
    )
    response = client.post("/v1/chat/completions", json=generation(request))
    assert response.status_code == 409
    assert "generation_canceled" in response.text
    assert manager.status()["requests"] == 0
    wrong = fixed_request(registry)
    wrong["capability"] = "drafting"
    assert client.post("/v1/requests/prepare", json=wrong).status_code == 400
    for _ in range(4):
        assert client.post("/v1/requests/prepare", json=fixed_request(registry)).status_code == 200
    assert client.post("/v1/requests/prepare", json=fixed_request(registry)).status_code == 429


def test_health_and_cancel_remain_responsive_during_generation(tmp_path):
    registry = _registry(tmp_path)
    entered = Event()

    class CooperativeBackend(_FakeBackend):
        def set_cancellation(self, event, deadline):
            self.cancel = event

        def complete(self, **kwargs):
            entered.set()
            assert self.cancel.wait(timeout=5)
            raise FastInterchangeError("fast_interchange_generation_canceled")

    manager = HotSwapManager(registry=registry, backend=CooperativeBackend(), allow_test_only=True)
    token = uuid.uuid4().hex
    with TestClient(
        create_worker_app(
            manager=manager, registry=registry, worker_token=token, allow_test_only=True
        )
    ) as client:
        client.headers["Authorization"] = "Bearer " + token
        request = fixed_request(registry)
        assert client.post("/v1/requests/prepare", json=request).status_code == 200
        with ThreadPoolExecutor(max_workers=1) as pool:
            work = pool.submit(client.post, "/v1/chat/completions", json=generation(request))
            assert entered.wait(timeout=3)
            started = time.monotonic()
            assert client.get("/healthz").json()["status"] == "running"
            other = fixed_request(registry)
            assert client.post("/v1/requests/prepare", json=other).status_code == 200
            assert client.post("/v1/chat/completions", json=generation(other)).status_code == 429
            assert (
                client.post(
                    "/v1/requests/cancel", json={"request_id": request["request_id"]}
                ).status_code
                == 200
            )
            assert time.monotonic() - started < 2
            assert work.result(timeout=3).status_code == 409
        assert client.get("/healthz").json()["status"] == "canceled"
        assert not manager.status()["quarantined"]


@pytest.mark.parametrize(
    "content,headers,expected",
    [
        (b'{"model":"a","model":"b"}', {"Content-Type": "application/json"}, 400),
        (b'{"model":NaN}', {"Content-Type": "application/json"}, 400),
        (b"{}", {"Content-Type": "text/plain"}, 400),
        (b"{}", {"Content-Type": "application/json", "Origin": "https://untrusted.invalid"}, 403),
        (b"x" * (161 * 1024), {"Content-Type": "application/json", "Content-Length": "1"}, 413),
    ],
    ids=["duplicate-json", "nonfinite-json", "content-type", "origin", "false-content-length"],
)
def test_untrusted_http_inputs_fail_closed(worker, content, headers, expected):
    client, _, _, _ = worker
    response = client.post("/v1/chat/completions", content=content, headers=headers)
    assert response.status_code == expected
    assert response.headers["Cache-Control"] == "no-store"


def test_streamed_body_limit_and_docs_not_exposed(worker):
    client, _, _, _ = worker
    response = client.post(
        "/v1/chat/completions",
        content=iter([b"x" * 100000, b"y" * 100000]),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert client.get("/openapi.json").status_code == 404


def test_client_requires_trusted_admission_without_network(monkeypatch):
    monkeypatch.delenv("MFL_FAST_INTERCHANGE_ADMISSION_CATALOG", raising=False)
    seen = []
    with pytest.raises(LocalModelError, match="trusted model admission"):
        FastInterchangeLocalClient(
            model_name="fictional-model",
            worker_token=uuid.uuid4().hex,
            opener=lambda *args, **kwargs: seen.append(args),
        )
    assert not seen


def test_client_capability_mismatch_and_cancel_before_dispatch(tmp_path):
    registry = _registry(tmp_path)
    token = uuid.uuid4().hex
    with pytest.raises(LocalModelError) as error:
        FastInterchangeLocalClient(
            model_name="family-evidence-small-r1",
            capability="drafting",
            registry=registry,
            allow_test_only=True,
            worker_token=token,
        )
    assert error.value.code == "fast_interchange_capability_mismatch"
    seen = []
    client = FastInterchangeLocalClient(
        model_name="family-evidence-small-r1",
        capability="evidence_review",
        registry=registry,
        allow_test_only=True,
        worker_token=token,
        opener=lambda *args, **kwargs: seen.append(args),
    )
    assert client.cancel()["status"] == "canceled"
    with pytest.raises(LocalModelError) as error:
        client.generate_response("Fictional source only.")
    assert error.value.code == "fast_interchange_generation_canceled" and not seen


def test_seven_capabilities_each_require_the_matching_release(tmp_path):
    from dataclasses import asdict

    from test_fast_interchange_worker import _file, _inventory
    from test_fast_interchange_worker import _release as release_row

    from legal.fast_interchange.admission import digest
    from legal.fast_interchange.fleet import FAST_INTERCHANGE_CAPABILITIES
    from legal.fast_interchange.worker import ArtifactBinding, HotSwapRegistry

    original = _registry(tmp_path)
    shared = next(iter(original.bindings.values()))
    releases, bindings = [], []
    for capability in FAST_INTERCHANGE_CAPABILITIES:
        adapter_dir = "adapters/" + capability
        adapter = _inventory(_file(tmp_path, adapter_dir + "/adapter.bin", capability.encode()))
        config = _file(
            tmp_path, adapter_dir + "/adapter_config.json", b"synthetic-not-model-config"
        )
        identity = "fictional-" + capability.replace("_", "-")
        binding = ArtifactBinding(
            identity,
            digest({"capability": capability}),
            "base",
            adapter_dir,
            shared.base_inventory,
            shared.tokenizer_inventory,
            adapter,
            config,
        )
        bindings.append(asdict(binding))
        # JSON's array representation is deliberately exercised by the registry.
        import json

        bindings[-1] = json.loads(json.dumps(bindings[-1]))
        releases.append(release_row(identity, identity, capability, binding))
    registry = HotSwapRegistry.from_dicts(
        root=tmp_path,
        releases={"schema": "fast_interchange_releases_v1", "releases": releases},
        artifacts={"schema": "fast_interchange_artifacts_v1", "bindings": bindings},
    )
    backend = _FakeBackend()
    manager = HotSwapManager(registry=registry, backend=backend, allow_test_only=True)
    try:
        for release in registry.releases.values():
            client = FastInterchangeLocalClient(
                model_name=release.model_id,
                capability=release.capability,
                registry=registry,
                allow_test_only=True,
                worker_token=uuid.uuid4().hex,
            )
            assert client.model_binding["capability"] == release.capability
            result = manager.complete(
                release=release, messages=[{"role": "user", "content": "Fictional source."}]
            )
            assert result["model"] == release.model_id
        assert manager.status()["switches"] == 7 and len(backend.activations) == 7
    finally:
        manager.close()

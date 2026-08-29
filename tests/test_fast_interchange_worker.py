from __future__ import annotations

import hashlib
import json
import socket
import time
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from fastapi.testclient import TestClient

from legal.agent_runtime import (
    ContextSource,
    FastInterchangeLocalClient,
    LocalAgentRunRequest,
    LocalAgentRuntime,
)
from legal.fast_interchange import FastInterchangeFleet
from legal.fast_interchange.worker import (
    ArtifactBinding,
    ArtifactFile,
    ArtifactInventory,
    FastInterchangeError,
    HotSwapManager,
    HotSwapRegistry,
    create_worker_app,
)


def _file(root: Path, relative: str, content: bytes) -> ArtifactFile:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return ArtifactFile(
        path=relative, sha256=hashlib.sha256(content).hexdigest(), bytes=len(content)
    )


def _inventory(*items: ArtifactFile) -> ArtifactInventory:
    return ArtifactInventory(files=tuple(sorted(items, key=lambda item: item.path)))


def _release(
    release_id: str, model_id: str, capability: str, binding: ArtifactBinding
) -> dict[str, object]:
    return {
        "release_id": release_id,
        "model_id": model_id,
        "capability": capability,
        "admission": "test_only",
        "release_fingerprint": binding.release_fingerprint,
        "base_inventory_sha256": binding.base_inventory.digest,
        "tokenizer_inventory_sha256": binding.tokenizer_inventory.digest,
        "adapter_inventory_sha256": binding.adapter_inventory.digest,
        "adapter_config_sha256": binding.adapter_config.sha256,
        "runtime_abi": "fast_interchange_hotswap_v1",
        "prompt_template_sha256": "b" * 64,
        "review_required": True,
        "promotion_authority": False,
    }


def _registry(root: Path) -> HotSwapRegistry:
    base = _inventory(_file(root, "base/model.bin", b"base"))
    tokenizer = _inventory(_file(root, "base/tokenizer.json", b"tokenizer"))
    adapter_one = _inventory(_file(root, "adapters/evidence/adapter.bin", b"evidence"))
    config_one = _file(root, "adapters/evidence/adapter_config.json", b"evidence-config")
    adapter_two = _inventory(_file(root, "adapters/authority/adapter.bin", b"authority"))
    config_two = _file(root, "adapters/authority/adapter_config.json", b"authority-config")
    first = ArtifactBinding(
        "family-evidence-small-r1",
        "a" * 64,
        "base",
        "adapters/evidence",
        base,
        tokenizer,
        adapter_one,
        config_one,
    )
    second = ArtifactBinding(
        "family-authority-small-r1",
        "c" * 64,
        "base",
        "adapters/authority",
        base,
        tokenizer,
        adapter_two,
        config_two,
    )
    releases = {
        "schema": "fast_interchange_releases_v1",
        "releases": [
            _release(first.release_id, "family-evidence-small-r1", "evidence_review", first),
            _release(second.release_id, "family-authority-small-r1", "authority_review", second),
        ],
    }
    artifacts = {
        "schema": "fast_interchange_artifacts_v1",
        "bindings": [
            {
                "release_id": first.release_id,
                "release_fingerprint": first.release_fingerprint,
                "base_dir": first.base_dir,
                "adapter_dir": first.adapter_dir,
                "base_inventory": {"files": [item.__dict__ for item in first.base_inventory.files]},
                "tokenizer_inventory": {
                    "files": [item.__dict__ for item in first.tokenizer_inventory.files]
                },
                "adapter_inventory": {
                    "files": [item.__dict__ for item in first.adapter_inventory.files]
                },
                "adapter_config": first.adapter_config.__dict__,
            },
            {
                "release_id": second.release_id,
                "release_fingerprint": second.release_fingerprint,
                "base_dir": second.base_dir,
                "adapter_dir": second.adapter_dir,
                "base_inventory": {
                    "files": [item.__dict__ for item in second.base_inventory.files]
                },
                "tokenizer_inventory": {
                    "files": [item.__dict__ for item in second.tokenizer_inventory.files]
                },
                "adapter_inventory": {
                    "files": [item.__dict__ for item in second.adapter_inventory.files]
                },
                "adapter_config": second.adapter_config.__dict__,
            },
        ],
    }
    return HotSwapRegistry.from_dicts(root=root, releases=releases, artifacts=artifacts)


class _FakeBackend:
    def __init__(self) -> None:
        self.activations: list[str] = []
        self.clears = 0
        self.closed = False

    def activate(self, *, root, binding, release):  # noqa: ANN001
        self.activations.append(release.release_id)
        return {
            "release_id": release.release_id,
            "model_id": release.model_id,
            "release_fingerprint": release.release_fingerprint,
        }

    def complete(self, *, release, messages):  # noqa: ANN001
        return {
            "model": release.model_id,
            "choices": [
                {"message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop"}
            ],
        }

    def clear_context(self) -> None:
        self.clears += 1

    def close(self) -> None:
        self.closed = True


def test_fleet_is_explicitly_untrained_and_model_empty():
    fleet = FastInterchangeFleet.load(Path("configs") / "fast_interchange_model_fleet.json")
    assert fleet.status == "specified_untrained_no_artifacts"
    assert len(fleet.slots) == 7
    assert len(fleet.fingerprint) == 64


def test_native_provenance_records_the_proprietary_and_artifact_boundary():
    provenance = json.loads(
        (Path("legal") / "fast_interchange" / "PROVENANCE.json").read_text(encoding="utf-8")
    )
    assert provenance["implementation_kind"] == "native_model_empty_implementation"
    assert provenance["source_files_copied"] is False
    assert {"Mainely Code source", "model weights", "credentials"} <= set(
        provenance["excluded_scope"]
    )


def test_shared_base_hotswap_clears_context_and_quarantines_on_tamper(tmp_path):
    registry = _registry(tmp_path)
    backend = _FakeBackend()
    manager = HotSwapManager(registry=registry, backend=backend, allow_test_only=True)
    first = registry.select("family-evidence-small-r1", allow_test_only=True)
    second = registry.select("family-authority-small-r1", allow_test_only=True)
    assert (
        manager.complete(release=first, messages=[{"role": "user", "content": "synthetic"}])[
            "model"
        ]
        == first.model_id
    )
    assert (
        manager.complete(release=second, messages=[{"role": "user", "content": "synthetic"}])[
            "model"
        ]
        == second.model_id
    )
    assert backend.activations == [first.release_id, second.release_id]
    assert backend.clears >= 6
    assert manager.status()["shared_matter_cache"] is False

    tampered_root = tmp_path / "tampered"
    tampered = _registry(tampered_root)
    (tampered_root / "adapters/evidence/adapter.bin").write_bytes(b"changed")
    tampered_manager = HotSwapManager(
        registry=tampered, backend=_FakeBackend(), allow_test_only=True
    )
    with pytest.raises(FastInterchangeError, match="artifact_mismatch"):
        tampered_manager.complete(
            release=tampered.select("family-evidence-small-r1", allow_test_only=True),
            messages=[{"role": "user", "content": "synthetic"}],
        )
    assert tampered_manager.status()["quarantined"] is True


def test_worker_accepts_only_authenticated_fixed_requests(tmp_path):
    registry = _registry(tmp_path)
    manager = HotSwapManager(registry=registry, backend=_FakeBackend(), allow_test_only=True)
    app = create_worker_app(
        manager=manager, registry=registry, worker_token="w" * 40, allow_test_only=True
    )
    client = TestClient(app)
    payload = {
        "model": "family-evidence-small-r1",
        "messages": [{"role": "user", "content": "synthetic"}],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 1024,
        "stream": False,
    }
    assert client.post("/v1/chat/completions", json=payload).status_code == 401
    response = client.post(
        "/v1/chat/completions", json=payload, headers={"Authorization": "Bearer " + "w" * 40}
    )
    assert response.status_code == 200
    assert response.json()["model"] == "family-evidence-small-r1"
    assert (
        client.post(
            "/v1/chat/completions",
            json={**payload, "temperature": 0.1},
            headers={"Authorization": "Bearer " + "w" * 40},
        ).status_code
        == 400
    )


def test_synthetic_host_to_native_worker_path_stays_review_required(tmp_path):
    """Exercise the host runtime over real loopback TCP with no legal model."""
    registry = _registry(tmp_path)
    manager = HotSwapManager(registry=registry, backend=_FakeBackend(), allow_test_only=True)
    app = create_worker_app(
        manager=manager,
        registry=registry,
        worker_token="w" * 40,
        allow_test_only=True,
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            access_log=False,
            log_level="error",
            timeout_keep_alive=1,
            timeout_graceful_shutdown=1,
        )
    )
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        client = FastInterchangeLocalClient(
            model_name="family-evidence-small-r1",
            endpoint=f"http://127.0.0.1:{port}",
            worker_token="w" * 40,
            timeout_seconds=5,
            registry=registry,
            capability="evidence_review",
            allow_test_only=True,
        )
        runtime = LocalAgentRuntime(client)
        source = ContextSource(
            source_id="synthetic-authority",
            lane="legal_authority",
            title="Synthetic source",
            text="Fictional source text for worker-transport verification only.",
            source_class="synthetic_fixture",
            authority_status="not_legal_authority",
            freshness_status="not_applicable",
        )
        manifest, _, _ = runtime.preview(
            question="Summarize the synthetic source.",
            sources=(source,),
            run_id="fast-interchange-synthetic-e2e",
        )
        result = runtime.run(
            LocalAgentRunRequest(
                question="Summarize the synthetic source.",
                sources=(source,),
                approved_manifest_sha256=manifest.manifest_sha256,
                run_id="fast-interchange-synthetic-e2e",
            )
        )
    finally:
        server.should_exit = True
        server.force_exit = True
        thread.join(timeout=5)

    assert not thread.is_alive()
    assert result.status == "completed_without_citations_review_required"
    assert result.review_required is True
    assert result.provenance_receipt.provider_id == "fast_interchange_local"
    assert result.provenance_receipt.model_id == "family-evidence-small-r1"
    assert manager.status()["requests"] == 1

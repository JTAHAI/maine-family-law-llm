"""Explicit fictional source-UI QA harness; never a real model/frozen-app certificate.

Uses the production application, parser, index, routes, and assets. Only the
generation client is synthetic. All runtime state lives in a new temp profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
import socket
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


class SyntheticTransportBackend:
    """Fictional spawn fixture, deliberately not model inference."""

    def __init__(self, **_options):
        pass

    def activate(self, *, release, **_kwargs):
        return {
            "release_id": release.release_id,
            "model_id": release.model_id,
            "release_fingerprint": release.release_fingerprint,
        }

    def complete(self, *, release, messages):
        prompt = messages[0]["content"]
        if "cancel-test" in prompt:
            time.sleep(20)  # Proves owned-child termination, not fetch abortion.
        if "missing attachment is a fictional school calendar" not in prompt:
            raise ValueError("fictional_verified_source_missing")
        return {
            "model": release.model_id,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "SYNTHETIC TRANSPORT TEST: The fictional record identifies a missing school-calendar attachment [1]. Review required. No real model inference was performed.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    def clear_context(self):
        pass  # This synthetic backend stores no context.

    def close(self):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=53681)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--model-packs", action="store_true", help="Explicit ephemeral test-key offline pack UI fixture; never real model admission.")
    parser.add_argument(
        "--worker-transport",
        action="store_true",
        help="Use actual authenticated worker HTTP and an owned synthetic inference subprocess.",
    )
    args = parser.parse_args()
    profile = Path(tempfile.mkdtemp(prefix="mfl-fictional-agent-ui-"))
    for key, child in {
        "LOCALAPPDATA": "local",
        "USERPROFILE": "user",
        "MFL_CASE_LIBRARY_PATH": "local/case-library.json",
        "MFL_RUNTIME_STATE_ROOT": "runtime",
        "MFL_IDEMPOTENCY_STATE_ROOT": "idempotency",
        "MFL_VAULT_KEY_ROOT": "vault",
        "MAINE_FAMILY_LAW_DATA_ROOT": "empty-authority",
        "MFL_AUTHORITY_DATA_ROOT": "empty-authority",
    }.items():
        os.environ[key] = str(profile / child)
    os.environ["MAINE_MATTER_STORE_KEY"] = "f" * 32
    os.environ["MFL_RUNTIME_MODE"] = "store"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.pop("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", None)

    from legal.agent_runtime import LocalModelResponse, LoopbackEndpointPolicy
    from maine_family_law_llm import api
    from maine_family_law_llm.case_library import register_case_root
    from maine_family_law_llm.local_corpus_index import rebuild_local_content_index

    matter = profile / "Fictional Family QA - No Real Records"
    record = matter / "02_PRIVATE_FORENSIC_MASTER" / "files" / "REC-1.txt"
    record.parent.mkdir(parents=True)
    text = (
        "Fictional family record: the missing attachment is a fictional school calendar. "
        "Review required."
    )
    record.write_text(text, encoding="utf-8")
    manifest = matter / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            [
                {
                    "evidence_id": "REC-1",
                    "source_path": str(record),
                    "source_type": "txt",
                    "private_copy_relpath": record.relative_to(matter).as_posix(),
                    "source_hash": hashlib.sha256(record.read_bytes()).hexdigest(),
                }
            ]
        ),
        encoding="utf-8",
    )
    rebuild_local_content_index(matter)
    register_case_root(matter)

    class SyntheticUIClient:
        provider_id = "ollama"
        model_name = "synthetic-ui-fixture-not-a-model"
        endpoint = LoopbackEndpointPolicy().validate("http://127.0.0.1:11434")

        def generate_response(self, prompt: str) -> LocalModelResponse:
            if text not in prompt:
                raise RuntimeError("fictional_verified_source_missing")
            return LocalModelResponse(
                text=(
                    "SYNTHETIC UI TEST: The fictional record identifies a missing "
                    "school-calendar attachment [1]. Review required. "
                    "No real model inference was performed."
                ),
                provider_id=self.provider_id,
                model_id=self.model_name,
                endpoint_class=self.endpoint.endpoint_class,
                usage={},
                finish_reason="stop",
            )

    import uvicorn

    worker_server = worker_thread = worker_socket = None
    worker_endpoint = None
    if args.worker_transport:
        from legal.agent_runtime.providers import FastInterchangeLocalClient, build_local_client
        from legal.fast_interchange.process_backend import IsolatedAdapterBackend
        from legal.fast_interchange.worker import HotSwapManager, create_worker_app

        # The explicitly requested QA fixture is never imported by the application.
        sys.path.insert(0, str(ROOT / "tests"))
        from test_fast_interchange_worker import _registry

        registry = _registry(profile / "synthetic-artifacts")
        worker_token = uuid.uuid4().hex + uuid.uuid4().hex
        worker_socket = socket.socket()
        worker_socket.bind(("127.0.0.1", 0))
        worker_endpoint = f"http://127.0.0.1:{worker_socket.getsockname()[1]}"
        backend = IsolatedAdapterBackend(
            factory=SyntheticTransportBackend, cancellation_grace_seconds=0.25
        )
        manager = HotSwapManager(registry=registry, backend=backend, allow_test_only=True)
        worker_server = uvicorn.Server(
            uvicorn.Config(
                create_worker_app(
                    manager=manager,
                    registry=registry,
                    worker_token=worker_token,
                    allow_test_only=True,
                ),
                log_level="warning",
                access_log=False,
            )
        )
        worker_thread = threading.Thread(
            target=worker_server.run, kwargs={"sockets": [worker_socket]}, daemon=True
        )
        worker_thread.start()

        def make_client(**kwargs):
            if kwargs["provider"] == "fast_interchange_local":
                return FastInterchangeLocalClient(
                    model_name=kwargs["model_name"],
                    endpoint=kwargs["endpoint"],
                    capability=kwargs.get("capability"),
                    registry=registry,
                    worker_token=worker_token,
                    allow_test_only=True,
                )
            return build_local_client(**kwargs)

        api.build_local_client = make_client
    else:
        api.build_local_client = lambda **_kwargs: SyntheticUIClient()

    pack_path = None
    if args.model_packs:
        import pytest
        from app.api import model_packs
        from app.services.model_pack_service import ModelPackService
        sys.path.insert(0, str(ROOT / "tests"))
        from test_fast_interchange_artifact_registry import admitted
        from test_fast_interchange_model_packs import structural_pack
        fixture = admitted.__wrapped__(profile / "fictional-pack-signing", pytest.MonkeyPatch())
        pack_path, _ = structural_pack(fixture, profile / "fictional-structural-test.model-pack.zip")
        pack_service = ModelPackService(profile / "fictional-pack-store", fixture["authority"])
        model_packs.configured_service = lambda _root: pack_service

    server = uvicorn.Server(
        uvicorn.Config(
            api.app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False
        )
    )
    timer = threading.Timer(
        max(30, min(args.max_seconds, 1800)), lambda: setattr(server, "should_exit", True)
    )
    timer.daemon = True
    timer.start()
    print(
        json.dumps(
            {
                "url": f"http://127.0.0.1:{args.port}",
                "profile": str(profile),
                "evidence_level": "production_source_UI_with_synthetic_generation",
                "worker_endpoint": worker_endpoint,
                "fictional_offline_pack": str(pack_path) if pack_path else None,
                "transport": "real_HTTP_owned_subprocess"
                if args.worker_transport
                else "in_process_synthetic_client",
            }
        ),
        flush=True,
    )
    try:
        server.run()
    finally:
        timer.cancel()
        if worker_server is not None:
            worker_server.should_exit = True
            worker_thread.join(timeout=10)
            worker_socket.close()


if __name__ == "__main__":
    main()

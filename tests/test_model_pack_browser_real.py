"""Opt-in shipped-page import; tiny synthetic signed tensors, NEVER model-quality proof."""

# ruff: noqa: F811
import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from starlette.responses import JSONResponse, Response
from test_fast_interchange_host_source_binding import preview
from test_fast_interchange_model_packs import admitted, bound_host, pack_store  # noqa: F401

from app.api import model_packs
from app.services.local_agent_context_service import LocalAgentAuditStore
from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"


@pytest.mark.skipif(
    os.environ.get("MFL_RUN_PACK_BROWSER_PROOF") != "1",
    reason="Opt-in actual browser: MFL_RUN_PACK_BROWSER_PROOF=1",
)
def test_shipped_model_pack_import(pack_store, bound_host, monkeypatch, tmp_path):
    run_id = os.environ.get("MFL_PACK_BROWSER_PROOF_ID", "01")
    assert re.fullmatch(r"[a-z0-9-]{1,20}", run_id)
    output = OUT / f"pack-browser-api-{run_id}.json"
    assert not output.exists(), "Preserve prior evidence"
    host, store = bound_host, pack_store["store"]
    host["headers"]["X-Tenant-Id"] = host["owner"]["tenant_id"] = "local-desktop"
    token_scope = api._record_capability_identity.set(host["owner"])
    try:
        token = api._record_open_token(host["root"], "REC-1", "REC-1.txt")
    finally:
        api._record_capability_identity.reset(token_scope)
    host["body"]["source_refs"][0]["record_token"] = token
    prepared = preview(host)
    monkeypatch.setattr(model_packs, "configured_service", lambda root: store)
    search = {
        "answer": "Fictional record for model-pack management QA. Review required.",
        "question": host["body"]["question"],
        "mode": "case",
        "review_required": True,
        "local_agent_available": True,
        "citations": prepared["source_cards"],
        "local_agent_task": "evidence_review",
        "local_agent_source_refs": prepared["source_refs"],
        "local_agent_matter_id": host["body"]["matter_id"],
        "failure_class": "none",
    }
    report = {
        "fictional_only": True,
        "test_signatures_only": True,
        "model_inference_tested": False,
        "production_admission_tested": False,
        "frozen_app_tested": False,
        "installed_package_tested": False,
        "ga_ready": False,
        "requests": [],
    }

    async def isolated_app(scope, receive, send):
        route, method = scope.get("path", ""), scope.get("method", "")
        if route in {"/", "/workbench", "/api/local-agent/preview"} or route.startswith(
            ("/ui-assets/", "/brand-assets/", "/api/model-packs")
        ):

            async def measured(message):
                if message["type"] == "http.response.start":
                    report["requests"].append(
                        {"route": route, "method": method, "status": message["status"]}
                    )
                await send(message)

            await api.app(scope, receive, measured)
        elif route == "/ask/stream":
            await Response(
                "event: accepted\ndata: {}\n\nevent: result\ndata: "
                + json.dumps({"payload": search, "duration_ms": 1})
                + "\n\n",
                media_type="text/event-stream",
            )(scope, receive, send)
        elif route == "/api/corpus-library":
            await JSONResponse(
                {
                    "active_case_id": host["body"]["matter_id"],
                    "active_case_label": "Fictional QA matter",
                    "cases": [
                        {
                            "case_id": host["body"]["matter_id"],
                            "label": "Fictional QA matter",
                            "indexed_records": 1,
                            "pdf_pages": 0,
                        }
                    ],
                }
            )(scope, receive, send)
        elif method == "GET":
            await JSONResponse(
                {
                    "status": "ok",
                    "models": [],
                    "items": [],
                    "records": [],
                    "case_id": host["body"]["matter_id"],
                    "active_case": "Fictional QA matter",
                }
            )(scope, receive, send)
        else:
            await JSONResponse(
                {"detail": "fictional_harness_unrelated_action_blocked"}, status_code=403
            )(scope, receive, send)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(isolated_app, log_level="critical", access_log=False, lifespan="off")
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    started = time.monotonic()
    try:
        thread.start()
        for _ in range(500):
            if server.started:
                break
            time.sleep(0.01)
        assert server.started
        config = tmp_path / "pack-browser-input.json"
        config.write_text(
            json.dumps(
                {
                    "base_url": f"http://127.0.0.1:{sock.getsockname()[1]}",
                    "run_id": run_id,
                    "question": host["body"]["question"],
                    "session": host["headers"]["X-MFLL-Client-Session"],
                    "pack_path": str(pack_store["path"]),
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                os.environ["MFL_PROOF_NODE"],
                str(ROOT / "scripts/verify_model_pack_flow.mjs"),
                str(config),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        )
        report.update(browser_exit_code=result.returncode, browser_stderr=result.stderr[-2000:])
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
        assert not host["worker"].prompts
        audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
        raw = audit.path.read_bytes()
        assert host["text"].encode() not in raw and str(store.root).encode() not in raw
        report["encrypted_audit_actions"] = [
            e["action"] for e in audit.encryptor.decrypt_json(json.loads(raw))["events"]
        ]
        assert "model_pack_verified" in report["encrypted_audit_actions"]
        assert (store.root / "active.json").is_file()
        assert pack_store["path"].is_file()
        report["assertions_passed"] = True
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        report.update(
            server_stopped=not thread.is_alive(),
            duration_seconds=round(time.monotonic() - started, 3),
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

"""Opt-in actual workbench comparison with fictional admitted-source fixtures."""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import test_v5150_authority_change_impact as fixtures
import uvicorn
from starlette.responses import JSONResponse

from legal.documents.workspace import create_document
from legal.review.authority_impact import AuthorityChangeImpactStore
from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"


@pytest.mark.skipif(
    os.environ.get("MFL_AUTHORITY_BROWSER") != "1", reason="Opt-in real authority comparison UI"
)
def test_production_authority_comparison_scope_and_drilldown(tmp_path, monkeypatch):
    fixtures.fictional_repository_boundary.__wrapped__(monkeypatch, tmp_path)
    authority, first, second = fixtures._publish_two_generations(tmp_path)
    case, other = tmp_path / "fictional-matter", tmp_path / "other-fictional-matter"
    case.mkdir()
    other.mkdir()
    doc = create_document(
        case,
        title="Fictional authority comparison",
        content="Fictional source-linked work.",
        source_refs=[{"source_id": "maine-title-19a"}],
    )
    current = [case]
    monkeypatch.setattr(api, "active_case_root", lambda: current[0])
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    output = OUT / ("authority-boundary-browser-" + os.environ["MFL_AUTHORITY_ID"] + ".json")
    assert not output.exists()
    report = {"fictional_only": True, "model_inference": False, "frozen_app": False, "requests": []}

    async def app(scope, receive, send):
        route, method = scope.get("path", ""), scope.get("method", "")
        if route in {"/", "/workbench"} or route.startswith(
            (
                "/ui-assets/",
                "/brand-assets/",
                "/api/document-workspace/",
                "/api/authority-change-impact/",
            )
        ):
            started = time.monotonic()

            async def capture(message):
                if message["type"] == "http.response.start":
                    report["requests"].append(
                        {
                            "route": route,
                            "method": method,
                            "status": message["status"],
                            "duration_ms": round((time.monotonic() - started) * 1000),
                        }
                    )
                await send(message)

            return await api.app(scope, receive, capture)
        if route == "/__qa/switch" and method == "POST":
            current[0] = other if current[0] == case else case
            response = JSONResponse({"switched": True})
        elif route == "/__qa/corrupt-packet" and method == "POST":
            store = AuthorityChangeImpactStore(
                case, data_root=authority, repo_root=tmp_path / "fictional-source-repository"
            )
            active = store.active(document_id=doc["document_id"])
            target = store.builds / active["build_id"] / "authority-change-impact.json"
            target.write_bytes(target.read_bytes() + b" ")
            response = JSONResponse({"fictional_packet_corrupted": True})
        elif route == "/api/corpus-library":
            response = JSONResponse(
                {
                    "active_case_id": api._case_id(case),
                    "active_case_label": "Fictional matter",
                    "cases": [
                        {
                            "case_id": api._case_id(case),
                            "label": "Fictional matter",
                            "indexed_records": 0,
                        }
                    ],
                }
            )
        elif method == "GET":
            response = JSONResponse(
                {
                    "status": "ok",
                    "items": [],
                    "models": [],
                    "records": [],
                    "case_id": api._case_id(case),
                }
            )
        else:
            response = JSONResponse({"detail": "unrelated_action_blocked"}, status_code=403)
        await response(scope, receive, send)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off")
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
        hashes = [
            json.loads(
                (
                    authority
                    / "authority_product/builds"
                    / build
                    / "authority_product_manifest.json"
                ).read_text()
            )["source_snapshots"][0]["sha256"]
            for build in (first, second)
        ]
        config = tmp_path / "browser-input.json"
        config.write_text(
            json.dumps(
                {
                    "base_url": f"http://127.0.0.1:{sock.getsockname()[1]}",
                    "output": str(output.with_suffix(".ui.json")),
                    "first": first,
                    "second": second,
                    "hashes": hashes,
                    "revision_id": doc["current_revision_id"],
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                os.environ["MFL_PROOF_NODE"],
                str(ROOT / "scripts/verify_authority_impact.mjs"),
                str(config),
            ],
            cwd=ROOT,
            env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=90,
        )
        report["browser_exit_code"] = result.returncode
        assert result.returncode == 0, result.stdout + result.stderr
        assert not (other / "19_DOCUMENT_WORKSPACE").exists()
        from app.services.local_agent_context_service import LocalAgentAuditStore

        audit = LocalAgentAuditStore(case, encryption_key=os.environ["MAINE_MATTER_STORE_KEY"])
        events = audit.encryptor.decrypt_json(json.loads(audit.path.read_bytes()))["events"]
        assert any(e["action"] == "authority_impact_document_analyze_completed" for e in events)
        assert b"Fictional" not in audit.path.read_bytes()
        report["encrypted_audit_verified"] = True
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
        report.update(
            server_stopped=not thread.is_alive(),
            duration_seconds=round(time.monotonic() - started, 3),
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

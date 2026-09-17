"""Opt-in shipped UI through canonical assignment API and encrypted storage."""

import base64
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from starlette.responses import JSONResponse
from test_filing_assignment_privacy import fixture as assignment_fixture

from legal.documents import storage
from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"


@pytest.mark.skipif(
    os.environ.get("MFL_ASSIGNMENT_BROWSER") != "1",
    reason="Opt-in real shipped-page assignment proof",
)
def test_assignment_ui_storage_reopen_and_scope(monkeypatch, tmp_path):
    case, doc, store, _ = assignment_fixture.__wrapped__(tmp_path)
    other = tmp_path / "other-fictional-matter"
    other.mkdir()
    current = [case]
    monkeypatch.setattr(api, "active_case_root", lambda: current[0])
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    output = OUT / ("assignment-browser-" + os.environ["MFL_ASSIGNMENT_ID"] + ".json")
    assert not output.exists()
    report = {"fictional_only": True, "model_inference": False, "frozen_app": False, "requests": []}

    async def app(scope, receive, send):
        route, method = scope.get("path", ""), scope.get("method", "")
        if route in {"/", "/workbench"} or route.startswith(
            (
                "/ui-assets/",
                "/brand-assets/",
                "/api/document-workspace/",
                "/api/reviewed-filing-packet/",
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
        elif route == "/__qa/legacy" and method == "POST":
            assert b"Fictional reviewer" not in store.assignments.read_bytes()
            report["assignment_encrypted_before_legacy_fixture"] = True
            original = storage.decode(store.assignments, store.assignments.read_bytes())
            assert len(original["events"]) == 1
            store.assignments.write_text(json.dumps(original["events"][0]) + "\n", encoding="utf-8")
            report["legacy_bytes"] = len(store.assignments.read_bytes())
            response = JSONResponse({"fictional_legacy_fixture": True})
        elif route == "/__qa/change-legacy" and method == "POST":
            assert store.assignments_for(doc["document_id"])["read_only"]
            store.assignments.write_bytes(store.assignments.read_bytes() + b"\n")
            report["legacy_original_base64"] = base64.b64encode(
                store.assignments.read_bytes()
            ).decode()
            response = JSONResponse({"fictional_legacy_changed": True})
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
        config = tmp_path / "input.json"
        config.write_text(
            json.dumps(
                {
                    "base_url": f"http://127.0.0.1:{sock.getsockname()[1]}",
                    "output": str(output.with_suffix(".ui.json")),
                    "revision_id": doc["current_revision_id"],
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                os.environ["MFL_PROOF_NODE"],
                str(ROOT / "scripts/verify_filing_assignment.mjs"),
                str(config),
            ],
            cwd=ROOT,
            env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
            capture_output=True,
            text=True,
            timeout=100,
        )
        report["browser_exit_code"] = result.returncode
        assert result.returncode == 0, result.stdout + result.stderr
        migrated = store.assignments_for(doc["document_id"])
        assert (
            not migrated["read_only"]
            and len(migrated["active"]) == 1
            and len(migrated["history"]) == 2
        )
        assert migrated["migration"]["status"] == "migrated"
        assert migrated["active"][0]["reviewer_label"] == "Fictional current reviewer"
        saved = storage.decode(store.assignments, store.assignments.read_bytes())
        assert saved["migration"]["original_base64"] == report.pop("legacy_original_base64")
        report["exact_legacy_original_verified"] = True
        assert b"Fictional" not in store.assignments.read_bytes()
        assert not (other / "19_DOCUMENT_WORKSPACE").exists()
        from app.services.local_agent_context_service import LocalAgentAuditStore

        audit = LocalAgentAuditStore(case, encryption_key=os.environ["MAINE_MATTER_STORE_KEY"])
        events = audit.encryptor.decrypt_json(json.loads(audit.path.read_bytes()))["events"]
        assert any(e["action"] == "filing_assignment_write_completed" for e in events)
        assert any(e["action"] == "filing_assignment_migrate_completed" for e in events)
        assert b"Fictional reviewer" not in audit.path.read_bytes()
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

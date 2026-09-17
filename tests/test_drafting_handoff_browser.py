"""Opt-in shipped-page save/reopen proof; deterministic model response, not inference."""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from starlette.responses import JSONResponse, Response
from test_drafting_output_boundary import SOURCE, _run

from legal.documents.workspace import get_document, list_documents, verify_audit_chain
from maine_family_law_llm import api

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"


@pytest.mark.skipif(
    os.environ.get("MFL_DRAFT_HANDOFF_BROWSER") != "1", reason="Opt-in shipped-page proof"
)
def test_shipped_draft_save_reopen_and_matter_change(monkeypatch, tmp_path):
    first, second = tmp_path / "fictional-first", tmp_path / "fictional-second"
    first.mkdir()
    second.mkdir()
    legacy = tmp_path / "fictional-legacy"
    legacy_revision = (
        legacy / "19_DOCUMENT_WORKSPACE/documents" / ("c" * 32) / "revisions" / ("d" * 32 + ".json")
    )
    legacy_revision.parent.mkdir(parents=True)
    from hashlib import sha256

    legacy_text = "Fictional legacy draft, preserved without migration."
    legacy_revision.write_text(
        json.dumps(
            {
                "document_id": "c" * 32,
                "revision_id": "d" * 32,
                "content": legacy_text,
                "content_sha256": sha256(legacy_text.encode()).hexdigest(),
                "status": "committed",
            }
        ),
        encoding="utf-8",
    )
    legacy_index = legacy / "19_DOCUMENT_WORKSPACE/document_index.json"
    legacy_index.write_text(
        json.dumps(
            {
                "schema_version": "document_workspace_v1",
                "documents": {
                    "c" * 32: {
                        "document_id": "c" * 32,
                        "current_revision_id": "d" * 32,
                        "title": "Fictional legacy draft",
                        "status": "review_required",
                        "review_required": True,
                        "filing_ready": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    legacy_before = (legacy_index.read_bytes(), legacy_revision.read_bytes())
    current = [first]
    from legal.review import integrity as review_integrity

    interrupt_review = [False]
    original_review_write = review_integrity._write

    def review_write(path, value):
        original_review_write(path, value)
        assert b"Fictional" not in path.read_bytes()
        if interrupt_review[0] and path.parent.name == "decisions":
            interrupt_review[0] = False
            raise OSError("Fictional interruption after durable decision")

    monkeypatch.setattr(review_integrity, "_write", review_write)
    monkeypatch.setattr(api, "active_case_root", lambda: current[0])
    monkeypatch.setattr(
        api.AuthorityProductService,
        "verify_output",
        lambda self, **kwargs: {
            "status": "blocked",
            "blockers": ["fictional_authority_unavailable"],
            "review_required": True,
        },
    )
    monkeypatch.setattr(
        api,
        "load_case_search_records",
        lambda root: [
            {
                "evidence_id": "fictional-notice-1",
                "source_hash": "c" * 64,
                "text": "Fictional notice supplied for review.",
                "title": "Fictional notice",
                "source_locator": "fictional-notice.txt",
            }
        ],
    )
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    # A model-response double exercises the actual runtime verifier/renderer.
    # This is deliberately NOT live model quality or production admission proof.
    result = _run(f'Unsupported assertion. "{SOURCE.text}" [1]').to_dict()
    result.update(
        local_agent_result=True,
        matter_id=api._case_id(first),
        citations=[],
        question="Fictional draft",
    )
    report = {
        "model_inference": False,
        "frozen_app": False,
        "installed_package": False,
        "ga_ready": False,
        "fictional_only": True,
        "authority_and_indexed_record_fixtures": True,
        "requests": [],
        "fixture_routes": [],
    }
    output = OUT / f"drafting-handoff-browser-{os.environ['MFL_DRAFT_HANDOFF_ID']}.json"
    assert not output.exists()

    async def app(scope, receive, send):
        route, method = scope.get("path", ""), scope.get("method", "")
        if route in {"/", "/workbench"} or route.startswith(
            ("/ui-assets/", "/brand-assets/", "/api/document-workspace/")
        ):
            request_started = time.monotonic()

            async def capture(message):
                if message["type"] == "http.response.start":
                    report["requests"].append(
                        {
                            "route": route,
                            "method": method,
                            "status": message["status"],
                            "duration_ms": round((time.monotonic() - request_started) * 1000, 2),
                        }
                    )
                await send(message)

            return await api.app(scope, receive, capture)
        report["fixture_routes"].append(route)
        if route == "/__qa/review-interrupt" and method == "POST":
            interrupt_review[0] = True
            response = JSONResponse({"interruption_armed": True})
        elif route == "/__qa/review-truncate" and method == "POST":
            from legal.review.review_ledger import list_review_history

            doc = list_documents(first)[0]
            history = list_review_history(first, doc["document_id"])
            assert history["decision_count"] == 2
            target = (
                first
                / "19_DOCUMENT_WORKSPACE/reviews"
                / doc["document_id"]
                / "decisions"
                / (history["latest"]["decision_id"] + ".json")
            )
            assert target.resolve().is_relative_to(first.resolve())
            target.unlink()  # Deliberate loss of one newly-created fictional QA record.
            response = JSONResponse({"fictional_tail_removed": True})
        elif route == "/__qa/switch" and method == "POST":
            current[0] = second if current[0] == first else first
            response = JSONResponse({"switched": True})
        elif route == "/__qa/legacy" and method == "POST":
            current[0] = legacy
            response = JSONResponse({"legacy_selected": True})
        elif route == "/ask/stream":
            response = Response(
                "event: accepted\ndata: {}\n\nevent: result\ndata: "
                + json.dumps({"payload": result, "duration_ms": 1})
                + "\n\n",
                media_type="text/event-stream",
            )
        elif route == "/api/corpus-library":
            response = JSONResponse(
                {
                    "active_case_id": api._case_id(first),
                    "active_case_label": "Fictional QA matter",
                    "cases": [
                        {
                            "case_id": api._case_id(first),
                            "label": "Fictional QA matter",
                            "indexed_records": 1,
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
                    "case_id": api._case_id(first),
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
                    "source_text": SOURCE.text,
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                os.environ["MFL_PROOF_NODE"],
                str(ROOT / "scripts/verify_drafting_handoff.mjs"),
                str(config),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=100,
            env={**os.environ, "TEMP": str(tmp_path), "TMP": str(tmp_path)},
        )
        report["browser_exit_code"] = completed.returncode
        report["browser_stderr"] = completed.stderr[-1500:]
        assert completed.returncode == 0, completed.stdout + completed.stderr
        docs = list_documents(first)
        assert len(docs) == 1
        saved = get_document(first, docs[0]["document_id"])
        assert SOURCE.text in saved["content"] and "Unsupported assertion" not in saved["content"]
        assert (
            "Facts, legal claims, relevance and current law are not verified"
            in saved["revisions"][0]["note"]
        )
        assert saved["filing_ready"] is False and saved["review_required"] is True
        assert not (second / "19_DOCUMENT_WORKSPACE").exists()
        assert verify_audit_chain(first)["valid"] is True
        report["saved_document_id"] = saved["document_id"]
        from legal.documents.workspace import workspace_paths

        paths = workspace_paths(first)
        encrypted_paths = [paths.index, *paths.documents.glob("*/revisions/*.json")]
        for path in encrypted_paths:
            raw = path.read_bytes()
            assert json.loads(raw)["storage_format"] == "document_workspace_encrypted_json_v1"
            assert SOURCE.text.encode() not in raw
        report["new_document_json_encryption_verified"] = True
        report["all_workspace_files_encrypted"] = False
        review_files = list((paths.root / "reviews").rglob("*.json"))
        assert len(review_files) == 4  # Two requests, retained first decision, encrypted head.
        for path in review_files:
            raw = path.read_bytes()
            assert json.loads(raw)["storage_format"] == "document_workspace_encrypted_json_v1"
            assert b"Fictional" not in raw
        from legal.review.review_ledger import list_review_history

        review = list_review_history(first, saved["document_id"])
        assert review["decisions"][0]["notes"] == "Fictional private reviewer note."
        assert not review["storage_authenticated"] and review["review_required"]
        assert review["latest"] is None and review["history_head"]["status"] == "mismatch"
        report["retained_head_detects_fictional_tail_removal"] = True
        report["review_packets_and_notes_encrypted_reopened"] = True
        from app.services.local_agent_context_service import LocalAgentAuditStore

        audit = LocalAgentAuditStore(first, encryption_key=os.environ["MAINE_MATTER_STORE_KEY"])
        events = audit.encryptor.decrypt_json(json.loads(audit.path.read_bytes()))["events"]
        assert any(e["action"] == "document_review_commit_completed" for e in events)
        assert any(e["action"] == "document_review_recovery_observed" for e in events)
        assert any(e["action"] == "document_review_integrity_blocked" for e in events)
        assert b"Fictional private reviewer note" not in audit.path.read_bytes()
        report["review_access_audit_encrypted"] = True
        from legal.documents.migration import original_snapshot

        recovery = original_snapshot(legacy)
        assert recovery["document_index.json"] == legacy_before[0]
        assert (
            recovery[legacy_revision.relative_to(legacy_index.parent).as_posix()]
            == legacy_before[1]
        )
        for path in (legacy_index, legacy_revision):
            assert (
                json.loads(path.read_bytes())["storage_format"]
                == "document_workspace_encrypted_json_v1"
            )
        assert get_document(legacy, "c" * 32)["content"] == legacy_text
        report["legacy_json_migrated_with_exact_recoverable_originals"] = True
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

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.runtime.context_cache import ContextCacheStore
from maine_family_law_llm import api as api_module

OLD_HASH = "a" * 64
NEW_HASH = "b" * 64


def _entry(cache_id: str = "cache_001"):
    return {
        "cache_id": cache_id,
        "kind": "retrieval",
        "scope": "matter",
        "source_refs": [
            {
                "source_id": "fictional_record",
                "content_sha256": OLD_HASH,
                "private_record": True,
                "source_token": "c" * 64,
            }
        ],
        "artifact": {"summary": "Fictional private retrieval result"},
    }


def test_pass105_encrypts_matter_cache_and_invalidates_changed_sources(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ContextCacheStore(root, encryption_key="fictional-test-key")
    created = store.put(_entry())

    assert created["entry"]["status"] == "valid_review_required"
    assert created["entry"]["review_required"] is True
    assert "Fictional private retrieval result" not in store.path.read_text(encoding="utf-8")
    assert store.get("cache_001")["entry"]["artifact"]["summary"] == "Fictional private retrieval result"
    assert store.source("cache_001", "fictional_record")["source_ref"]["source_token"] == "c" * 64

    unchanged = store.invalidate({"changes": [{"source_id": "fictional_record", "content_sha256": OLD_HASH}]})
    assert unchanged["invalidated_cache_ids"] == []
    changed = store.invalidate({"changes": [{"source_id": "fictional_record", "content_sha256": NEW_HASH}]})
    assert changed["invalidated_cache_ids"] == ["cache_001"]
    assert store.get("cache_001")["entry"]["status"] == "invalidated_review_required"


def test_pass105_public_cache_refuses_private_source_reference(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ContextCacheStore(root, encryption_key="fictional-test-key")
    payload = _entry("cache_002")
    payload["scope"] = "public_authority"
    with pytest.raises(IntakeWorkbenchError, match="context_cache_public_scope_private_source_refused"):
        store.put(payload)


def test_pass105_api_is_matter_scoped_and_shipped_assets_are_mirrored(monkeypatch, tmp_path: Path):
    first, second = tmp_path / "matter-one", tmp_path / "matter-two"
    first.mkdir()
    second.mkdir()
    active = {"root": first}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    response = client.post("/api/runtime/context-cache", json=_entry())
    assert response.status_code == 200
    assert response.json()["entry"]["cache_id"] == "cache_001"
    active["root"] = second
    assert client.get("/api/runtime/context-cache/cache_001").status_code == 404

    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Prompt-prefix and retrieval cache" in ui
    assert "/api/runtime/context-cache/invalidate" in ui

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_dockerfile_exists_and_uses_non_root_external_data_root_and_healthcheck():
    dockerfile = _read("Dockerfile")
    assert "FROM python:3.11-slim" in dockerfile
    assert "MAINE_FAMILY_LAW_DATA_ROOT=/data" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "scripts/container-healthcheck.py" in dockerfile
    assert "UVICORN_APP=maine_family_law_llm.api:app" in dockerfile
    assert "COPY --chown=app:app src ./src" in dockerfile
    assert "COPY --chown=app:app data ./data" in dockerfile


def test_dockerignore_blocks_external_data_sensitive_artifacts_and_runtime_state():
    dockerignore = _read(".dockerignore")
    required_patterns = [
        "ME_FM_LLM_data/",
        "official_authority_store/",
        "parsed_authority_store/",
        "embedding_store/",
        "eval_store/",
        "matter_store/",
        "model_store/",
        "model_registry/",
        "audit_store/",
        "ocr_cache/",
        "*.pdf",
        "*.docx",
        "*.safetensors",
        "*.gguf",
        "*.sqlite3",
        ".env",
        "*.pem",
        "uploads/",
        "runtime/",
    ]
    for pattern in required_patterns:
        assert pattern in dockerignore or f"/{pattern}" in dockerignore


def test_compose_mounts_external_data_as_data_and_exposes_api_locally_only():
    compose = _read("docker-compose.yml")
    assert "MAINE_FAMILY_LAW_DATA_ROOT: /data" in compose
    assert "target: /data" in compose
    assert "target: /app" in compose
    assert "read_only: true" in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert 'user: "10001:10001"' in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "container-healthcheck.py" in compose


def test_container_image_context_does_not_require_baked_official_authority_corpora():
    dockerfile = _read("Dockerfile")
    forbidden_copy_targets = [
        "official_authority_store",
        "parsed_authority_store",
        "embedding_store",
        "eval_store",
        "matter_store",
        "model_store",
        "model_registry",
        "audit_store",
        "ME_FM_LLM_data",
        "/data",
    ]
    copy_lines = [line for line in dockerfile.splitlines() if line.strip().upper().startswith("COPY")]
    assert copy_lines
    for line in copy_lines:
        for forbidden in forbidden_copy_targets:
            if forbidden == "/data" and " ./data" in line:
                continue
            assert forbidden not in line


def test_docker_helper_scripts_exist_for_windows_and_linux():
    for rel in [
        "scripts/docker-build.ps1",
        "scripts/docker-run-api.ps1",
        "scripts/docker-smoke-test.ps1",
        "scripts/docker-build.sh",
        "scripts/docker-run-api.sh",
        "scripts/docker-smoke-test.sh",
        "scripts/container-healthcheck.py",
    ]:
        assert (ROOT / rel).is_file(), rel


def test_pass_changes_is_the_only_running_txt_pass_log():
    ignored_parts = {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        ".proofs",
    }
    pass_logs = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.txt")
        if "pass" in path.name.lower()
        and not any(
            part in ignored_parts or part.endswith(".egg-info")
            for part in path.relative_to(ROOT).parts
        )
    )
    assert pass_logs == ["PASS_CHANGES.txt"]

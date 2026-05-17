from pathlib import Path


def test_ingest_script_refuses_default_inside_repo_policy_text():
    script = Path("scripts/ingest-maine-authority.py").read_text(encoding="utf-8")

    assert "Defaults outside the source repository" in script
    assert "Refusing to ingest official authority into the source repository" in script

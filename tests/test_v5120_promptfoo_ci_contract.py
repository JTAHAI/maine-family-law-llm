from pathlib import Path


def test_promptfoo_redteam_is_fixed_ci_only_and_contains_no_private_matter_fixture():
    config = Path("eval_data/promptfoo/maine_legal_redteam.yaml").read_text(encoding="utf-8")
    runner = Path("scripts/run-promptfoo-legal-redteam.py").read_text(encoding="utf-8")
    assert "127.0.0.1" in config
    assert "matter_context: \"\"" in config
    assert "filing-ready" in config
    assert "--approved" in runner
    assert "shutil.which(\"promptfoo\")" in runner
    assert "shell=True" not in runner
    assert "private matter" not in config.lower()

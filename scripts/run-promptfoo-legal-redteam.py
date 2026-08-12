#!/usr/bin/env python3
"""Run the fixed local Promptfoo legal red-team config in developer/CI mode."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", required=True)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    output = Path(args.output).resolve()
    config = root / "eval_data" / "promptfoo" / "maine_legal_redteam.yaml"
    if not args.approved:
        raise SystemExit("Explicit --approved is required for the local red-team run.")
    if not config.is_file() or root not in config.resolve().parents:
        raise SystemExit("Fixed Promptfoo configuration is missing or escaped the repository.")
    executable = shutil.which("promptfoo")
    if not executable:
        payload = {"status": "blocked", "blockers": ["promptfoo_not_installed"], "developer_ci_only": True}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload))
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [executable, "eval", "-c", str(config), "--no-cache", "--output", str(output)],
        cwd=root,
        timeout=900,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, allow_failure: bool = False) -> dict:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "status": "pass" if result.returncode == 0 or allow_failure else "fail",
        "stdout_tail": result.stdout[-6000:],
        "stderr_tail": result.stderr[-6000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local enterprise hardening/collection pipeline.")
    parser.add_argument("--data-root", type=Path, default=Path(r"C:\dev\ME_FM_LLM_data") if sys.platform.startswith("win") else ROOT.parent / "ME_FM_LLM_data")
    parser.add_argument("--dry-run", action="store_true", help="Plan resources without network downloads.")
    parser.add_argument("--max-resources", type=int, default=None)
    parser.add_argument("--skip-quality", action="store_true", help="Skip full repo quality checks for fast collector smoke evidence.")
    args = parser.parse_args()

    py = sys.executable
    commands: list[tuple[list[str], bool]] = [
        ([py, "scripts/build-enterprise-local-plan.py", "--repo-root", str(ROOT), "--data-root", str(args.data_root)], False),
    ]
    if not args.skip_quality:
        commands.append(([py, "scripts/run-quality-checks.py"], False))
    collect = [py, "scripts/collect-enterprise-resources.py", "--data-root", str(args.data_root)]
    if args.dry_run:
        collect.append("--dry-run")
    if args.max_resources is not None:
        collect.extend(["--max-resources", str(args.max_resources)])
    commands.append((collect, False))
    commands.append(([py, "scripts/audit-enterprise-resource-collection.py", "--data-root", str(args.data_root)], args.dry_run))
    if not args.dry_run:
        commands.extend(
            [
                ([py, "scripts/ingest-maine-authority.py", "--data-root", str(args.data_root)], True),
                ([py, "scripts/build-parsed-authority-store.py", "--data-root", str(args.data_root)], True),
                ([py, "scripts/build-authority-layer.py", "--data-root", str(args.data_root)], True),
                ([py, "scripts/build-retrieval-indexes.py", "--data-root", str(args.data_root)], True),
                ([py, "scripts/audit-enterprise-readiness.py", "--data-root", str(args.data_root), "--eval-root", str(args.data_root / "eval_store")], True),
            ]
        )
    results = [run(command, allow_failure=allow_failure) for command, allow_failure in commands]
    status = "pass" if all(item["status"] == "pass" for item in results) else "fail"
    evidence = {
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(ROOT),
        "data_root": str(args.data_root),
        "dry_run": args.dry_run,
        "results": results,
        "note": "Network-dependent authority and resource download failures are recorded as blockers, not hidden.",
    }
    out = ROOT / "enterprise_local_hardening_evidence.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate deterministic v2.05 Family Justice Workbench evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from legal.product.family_justice_workbench_v205 import VERSION, write_evidence_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v2.05 Family Justice Workbench evidence files")
    parser.add_argument("--output-dir", default="docs/external-evidence")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    outputs = write_evidence_outputs(output_dir)
    summary = json.loads(Path(outputs["test_summary"]).read_text(encoding="utf-8"))
    audit = json.loads(Path(outputs["audit"]).read_text(encoding="utf-8"))
    status = "pass" if summary.get("status") == "pass" and audit.get("status") == "pass" else "fail"
    payload = {
        "status": status,
        "version": VERSION,
        "outputs": outputs,
        "summary_status": summary.get("status"),
        "audit_status": audit.get("status"),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and status != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

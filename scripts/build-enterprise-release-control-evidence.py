#!/usr/bin/env python3
"""Generate deterministic v2.06 enterprise release control evidence."""

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

from legal.release.enterprise_release_control_v206 import VERSION, write_evidence_outputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v2.06 enterprise release control evidence files")
    parser.add_argument("--output-dir", default="docs/external-evidence")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    outputs = write_evidence_outputs(output_dir)
    audit = json.loads(Path(outputs["audit"]).read_text(encoding="utf-8"))
    summary = json.loads(Path(outputs["test_summary"]).read_text(encoding="utf-8"))
    status = "pass" if audit.get("status") == "pass" and summary.get("status") == "pass" else "fail"
    payload = {
        "status": status,
        "version": VERSION,
        "audit_status": audit.get("status"),
        "summary_status": summary.get("status"),
        "enterprise_ready": False,
        "production_legal_ready": False,
        "outputs": outputs,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and status != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

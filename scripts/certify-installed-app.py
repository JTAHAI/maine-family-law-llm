from __future__ import annotations

import argparse
from pathlib import Path

from legal.release.installed_certification import InstalledAppCertifier


def main() -> int:
    parser = argparse.ArgumentParser(description="Certify one immutable installed MSIX artifact.")
    parser.add_argument("--package", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = InstalledAppCertifier(args.package, args.evidence_root).write(args.output)
    print(f"Installed-app certification: {report['status']}")
    print(f"Report: {Path(args.output).resolve()}")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

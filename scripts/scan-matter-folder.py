#!/usr/bin/env python3
"""Read-only matter-folder inventory.

Adapted from the MIT-licensed scan_folder.py in zeweihan/A-market-ecm-lawyer-plugin.
The adaptation adds symlink blocking, path containment, optional SHA-256 hashing,
resource limits, English output, and integration with Maine Family Law LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from legal.matter.document_inventory import InventoryError, scan_matter_folder


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    result.add_argument("folder", type=Path)
    result.add_argument("--no-recursive", action="store_true")
    result.add_argument("--include-unsupported", action="store_true")
    result.add_argument("--hash", action="store_true", dest="hash_files")
    result.add_argument("--json", action="store_true", dest="as_json")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = scan_matter_folder(
            args.folder,
            recursive=not args.no_recursive,
            include_unsupported=args.include_unsupported,
            hash_files=args.hash_files,
        )
    except (InventoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(f"Root: {report.root}")
    print(f"Readable files: {len(report.files)}")
    print(f"Total bytes: {report.total_bytes:,}")
    print("By extension:")
    for extension, count in report.by_extension.items():
        print(f"  {extension:<8} {count}")
    large = [item for item in report.files if item.is_large]
    if large:
        print("Large files:")
        for item in sorted(large, key=lambda value: -value.size_bytes):
            print(f"  {item.size_bytes / 1024 / 1024:8.1f} MiB  {item.relative_path}")
    if report.blocked:
        print("Blocked entries:")
        for item in report.blocked:
            print(f"  {item.reason}: {item.relative_path}")
    print("Files:")
    for item in report.files:
        marker = " [large]" if item.is_large else ""
        hash_text = f" sha256={item.sha256}" if item.sha256 else f" hash={item.hash_status}"
        print(f"  {item.extension:<8} {item.relative_path}{marker}{hash_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

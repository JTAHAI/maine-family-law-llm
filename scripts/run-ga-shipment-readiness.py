#!/usr/bin/env python3
"""Inspect Pass 51 shipment-readiness status without mutating evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from legal.release.shipment_readiness_operations import GAShipmentReadinessStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--release-root', required=True)
    args = parser.parse_args()
    status = GAShipmentReadinessStore(Path(args.repo_root), Path(args.release_root)).status()
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status.get('status') == 'ready_for_external_pass51_gate' else 2


if __name__ == '__main__':
    raise SystemExit(main())

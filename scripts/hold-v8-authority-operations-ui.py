"""Temporarily host frozen Authority review controls against an external root.

This QA-only harness is read-only: it starts the supplied frozen runtime with a
temporary local profile and an existing external authority root, waits for
health, and emits safe connection metadata.  It never refreshes, stages,
activates, rolls back, imports, exports, or otherwise changes authority data.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--hold-seconds", type=int, default=240)
    args = parser.parse_args(argv)
    if not 10 <= args.hold_seconds <= 600:
        parser.error("hold_seconds_must_be_between_10_and_600")

    outline = _module(OUTLINE_RUNNER, "mfl_v8_outline_e2e")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    authority_root = args.authority_data_root.resolve(strict=True)
    outline.validate_runtime_pair(runtime, package)
    helper = outline.load_helper()

    with tempfile.TemporaryDirectory(prefix="mfl-v8-authority-operations-ui-") as temporary:
        temporary_root = Path(temporary)
        port = helper.free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = helper.start_runtime(
            runtime,
            port,
            localappdata=temporary_root / "localappdata",
            authority_data_root=authority_root,
        )
        monitor = helper.RuntimeNetworkMonitor(process.pid)
        monitor.start()
        try:
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            if health.get("status") != "ok":
                raise RuntimeError("frozen_runtime_health_failed")
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "base_url": base_url,
                        "fictional_matter_profile": True,
                        "authority_root_external_to_repository_and_msix": True,
                        "read_only_authority_operations": True,
                        "started_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(args.hold_seconds)
        finally:
            network = monitor.stop()
            outline.terminate(process)
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "external_connection_count": int(network.get("external_connection_count") or 0),
                        "network_samples": int(network.get("sample_count") or 0),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

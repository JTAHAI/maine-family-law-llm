"""Temporarily host a frozen production Authority UI over a fictional fixture.

This is a browser-verification harness, not an authority updater.  It creates
two fictional immutable external builds (one active, one staged), starts the
exact supplied frozen runtime on loopback, prints only safe connection/build
metadata, and stops automatically after the requested hold.  The temporary
external root is removed at shutdown.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_RUNNER = ROOT / "scripts" / "run-v8-authority-activation-rollback-e2e.py"
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
    parser.add_argument("--hold-seconds", type=int, default=180)
    args = parser.parse_args(argv)
    if not 10 <= args.hold_seconds <= 600:
        parser.error("hold_seconds_must_be_between_10_and_600")

    lifecycle = _module(LIFECYCLE_RUNNER, "mfl_v8_authority_lifecycle")
    outline = _module(OUTLINE_RUNNER, "mfl_v8_outline_e2e")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    outline.validate_runtime_pair(runtime, package)
    helper = outline.load_helper()

    import tempfile

    with tempfile.TemporaryDirectory(prefix="mfl-v8-authority-ui-") as temporary:
        temporary_root = Path(temporary)
        authority_root, active_build_id, staged_build_id = lifecycle._publish_staged_pair(temporary_root)
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
                        "active_build_id": active_build_id,
                        "staged_build_id": staged_build_id,
                        "fictional_data_only": True,
                        "expires_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
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
